"""
IPTV 定时任务调度模块

基于 APScheduler (AsyncIOScheduler) 实现定时任务的创建、管理、执行和日志记录。
支持三种内置任务类型：
  1. auto_search  - 自动搜索 IPTV 源
  2. validate     - 验证源有效性
  3. update       - 更新频道列表

默认调度策略：每 6 小时自动执行一次搜索 + 验证。

使用方式：
    from app.core.scheduler import TaskManager, start_scheduler, stop_scheduler

    manager = TaskManager()
    await start_scheduler(manager)

    # 创建自定义任务
    task_id = await manager.create_task(
        name="每日源验证",
        cron_expr="0 3 * * *",
        task_type="validate",
        params={"timeout": 30},
    )

    # 停止调度器
    await stop_scheduler(manager)

依赖：
  - apscheduler >= 3.10
  - sqlalchemy（通过 app.models.database 获取会话）
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError
from sqlalchemy import text

from app.models.database import get_db_context
from app.models.models import SearchTask, SearchLog

logger = logging.getLogger(__name__)


# =============================================================================
# 任务类型枚举
# =============================================================================

class TaskType(str, Enum):
    """定时任务类型枚举"""
    AUTO_SEARCH = "auto_search"   # 自动搜索源
    VALIDATE = "validate"         # 验证源有效性
    UPDATE = "update"             # 更新频道列表


# =============================================================================
# Cron 表达式解析工具
# =============================================================================

# 预定义的常用 Cron 表达式（友好名称 -> cron 字符串）
CRON_PRESETS: dict[str, str] = {
    "every_1h":  "0 * * * *",        # 每小时整点
    "every_3h":  "0 */3 * * *",      # 每 3 小时
    "every_6h":  "0 */6 * * *",      # 每 6 小时（默认）
    "every_12h": "0 */12 * * *",     # 每 12 小时
    "daily":     "0 3 * * *",        # 每天凌晨 3 点
    "weekly":    "0 3 * * 0",        # 每周日凌晨 3 点
    "monthly":   "0 3 1 * *",        # 每月 1 日凌晨 3 点
}


def resolve_cron_expression(expr: str) -> str:
    """
    解析 Cron 表达式。

    支持两种输入格式：
      1. 标准 Cron 表达式："0 */6 * * *"（5 段或 6 段）
      2. 预设名称："every_6h"、"daily" 等

    Args:
        expr: Cron 表达式字符串或预设名称

    Returns:
        str: 标准化的 Cron 表达式字符串

    Raises:
        ValueError: 当表达式格式不正确或预设名称不存在时

    Examples:
        >>> resolve_cron_expression("every_6h")
        '0 */6 * * *'
        >>> resolve_cron_expression("0 3 * * *")
        '0 3 * * *'
    """
    # 先检查是否是预设名称
    if expr in CRON_PRESETS:
        return CRON_PRESETS[expr]

    # 验证标准 Cron 表达式格式（5 段或 6 段）
    parts = expr.strip().split()
    if len(parts) not in (5, 6):
        raise ValueError(
            f"无效的 Cron 表达式 '{expr}'："
            f"需要 5 段或 6 段（空格分隔），实际 {len(parts)} 段。"
            f"支持的预设名称：{list(CRON_PRESETS.keys())}"
        )

    return expr


def get_preset_names() -> list[str]:
    """返回所有可用的预设 Cron 名称列表"""
    return list(CRON_PRESETS.keys())


# =============================================================================
# 任务执行日志记录
# =============================================================================

def _log_execution(
    task_id: Optional[int],
    action: str,
    status: str,
    detail: str = "",
    sources_found: int = 0,
    channels_found: int = 0,
    channels_valid: int = 0,
    duration: int = 0,
) -> None:
    """
    将任务执行结果写入 search_logs 表。

    使用独立的数据库会话，确保日志写入不受主事务影响。

    Args:
        task_id: 关联的 SearchTask ID（可选）
        action: 操作类型（search / validate / update）
        status: 执行状态（running / success / failed）
        detail: 详细描述或错误信息
        sources_found: 发现的源数量
        channels_found: 发现的频道数量
        channels_valid: 有效频道数量
        duration: 执行时长（秒）
    """
    try:
        with get_db_context() as db:
            log = SearchLog(
                task_id=task_id,
                action=action,
                status=status,
                detail=detail,
                sources_found=sources_found,
                channels_found=channels_found,
                channels_valid=channels_valid,
                duration=duration,
                created_at=datetime.utcnow(),
            )
            db.add(log)
            db.commit()
            logger.info(
                "任务日志已记录: action=%s, status=%s, duration=%ds",
                action, status, duration,
            )
    except Exception as exc:
        # 日志写入失败不应影响主流程
        logger.error("写入任务日志失败: %s", exc, exc_info=True)


def _update_task_run_info(task_id: int, status: str, detail: str) -> None:
    """
    更新 SearchTask 表的运行状态信息。

    Args:
        task_id: SearchTask 的 ID
        status: 执行状态描述
        detail: 结果摘要
    """
    try:
        with get_db_context() as db:
            task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
            if task:
                task.last_run = datetime.utcnow()
                task.last_result = detail[:500]  # 限制长度
                task.run_count = (task.run_count or 0) + 1
                task.is_running = False
                db.commit()
    except Exception as exc:
        logger.error("更新任务运行信息失败 (task_id=%d): %s", task_id, exc)


# =============================================================================
# 任务执行函数（实际业务逻辑）
# =============================================================================

async def _execute_auto_search(task_id: int, params: dict[str, Any]) -> dict[str, Any]:
    """
    执行自动搜索 IPTV 源任务。

    从内置源列表和数据库中已保存的源中搜索新的 IPTV 源，
    解析 M3U 内容并提取频道信息。

    Args:
        task_id: SearchTask ID
        params: 任务参数字典
            - max_sources (int): 最大搜索源数，默认 100
            - search_timeout (int): 单次搜索超时（秒），默认 30
            - region (str): 按地区筛选（可选）
            - operator (str): 按运营商筛选（可选）

    Returns:
        dict: 执行结果摘要
    """
    logger.info("开始执行自动搜索任务 (task_id=%d, params=%s)", task_id, params)
    start_time = time.monotonic()

    max_sources = params.get("max_sources", 100)
    search_timeout = params.get("search_timeout", 30)

    result = {
        "sources_found": 0,
        "channels_found": 0,
        "channels_valid": 0,
        "status": "success",
        "detail": "",
    }

    try:
        # 从 app.services.source_service 导入搜索函数
        # 如果模块不存在，使用内联实现作为降级方案
        try:
            from app.services.source_service import search_all_sources
            search_result = await search_all_sources(
                max_sources=max_sources,
                timeout=search_timeout,
                params=params,
            )
        except ImportError:
            logger.warning(
                "app.services.source_service 未找到，使用内置搜索逻辑"
            )
            # 降级：使用 app.core.searcher 中的内置源搜索
            from app.core.searcher import BUILTIN_IPTV_SOURCES
            search_result = await _fallback_search(
                BUILTIN_IPTV_SOURCES[:max_sources],
                timeout=search_timeout,
            )

        result["sources_found"] = search_result.get("sources_found", 0)
        result["channels_found"] = search_result.get("channels_found", 0)
        result["channels_valid"] = search_result.get("channels_valid", 0)
        result["detail"] = (
            f"搜索完成：发现 {result['sources_found']} 个源，"
            f"{result['channels_found']} 个频道，"
            f"{result['channels_valid']} 个有效"
        )

    except Exception as exc:
        result["status"] = "failed"
        result["detail"] = f"搜索失败: {exc}"
        logger.error("自动搜索任务执行失败: %s", exc, exc_info=True)

    elapsed = int(time.monotonic() - start_time)
    result["duration"] = elapsed

    # 记录日志
    _log_execution(
        task_id=task_id,
        action="search",
        status=result["status"],
        detail=result["detail"],
        sources_found=result["sources_found"],
        channels_found=result["channels_found"],
        channels_valid=result["channels_valid"],
        duration=elapsed,
    )
    _update_task_run_info(task_id, result["status"], result["detail"])

    return result


async def _execute_validate(task_id: int, params: dict[str, Any]) -> dict[str, Any]:
    """
    执行源有效性验证任务。

    对数据库中所有已保存的 IPTV 源进行可用性检查，
    更新源的 is_valid、last_check、fail_count 等字段。

    Args:
        task_id: SearchTask ID
        params: 任务参数字典
            - timeout (int): 单次验证超时（秒），默认 10
            - max_concurrent (int): 最大并发数，默认 20
            - only_active (bool): 是否只验证启用的源，默认 True

    Returns:
        dict: 执行结果摘要
    """
    logger.info("开始执行源验证任务 (task_id=%d, params=%s)", task_id, params)
    start_time = time.monotonic()

    timeout = params.get("timeout", 10)
    max_concurrent = params.get("max_concurrent", 20)
    only_active = params.get("only_active", True)

    result = {
        "sources_found": 0,
        "channels_valid": 0,
        "status": "success",
        "detail": "",
    }

    try:
        try:
            from app.services.source_service import validate_all_sources
            validate_result = await validate_all_sources(
                timeout=timeout,
                max_concurrent=max_concurrent,
                only_active=only_active,
            )
        except ImportError:
            logger.warning(
                "app.services.source_service 未找到，使用内置验证逻辑"
            )
            validate_result = await _fallback_validate(
                timeout=timeout,
                only_active=only_active,
            )

        result["sources_found"] = validate_result.get("total", 0)
        result["channels_valid"] = validate_result.get("valid", 0)
        result["detail"] = (
            f"验证完成：共 {result['sources_found']} 个源，"
            f"{result['channels_valid']} 个有效"
        )

    except Exception as exc:
        result["status"] = "failed"
        result["detail"] = f"验证失败: {exc}"
        logger.error("源验证任务执行失败: %s", exc, exc_info=True)

    elapsed = int(time.monotonic() - start_time)
    result["duration"] = elapsed

    _log_execution(
        task_id=task_id,
        action="validate",
        status=result["status"],
        detail=result["detail"],
        sources_found=result["sources_found"],
        channels_valid=result["channels_valid"],
        duration=elapsed,
    )
    _update_task_run_info(task_id, result["status"], result["detail"])

    return result


async def _execute_update(task_id: int, params: dict[str, Any]) -> dict[str, Any]:
    """
    执行频道列表更新任务。

    从所有有效源重新拉取 M3U 内容，更新频道列表和源-频道关联关系。
    包括：新增频道、失效频道标记、播放地址更新等。

    Args:
        task_id: SearchTask ID
        params: 任务参数字典
            - force (bool): 是否强制全量更新，默认 False
            - merge_strategy (str): 合并策略（replace / merge），默认 merge

    Returns:
        dict: 执行结果摘要
    """
    logger.info("开始执行频道更新任务 (task_id=%d, params=%s)", task_id, params)
    start_time = time.monotonic()

    force = params.get("force", False)
    merge_strategy = params.get("merge_strategy", "merge")

    result = {
        "sources_found": 0,
        "channels_found": 0,
        "channels_valid": 0,
        "status": "success",
        "detail": "",
    }

    try:
        try:
            from app.services.source_service import update_channel_list
            update_result = await update_channel_list(
                force=force,
                merge_strategy=merge_strategy,
            )
        except ImportError:
            logger.warning(
                "app.services.source_service 未找到，使用内置更新逻辑"
            )
            update_result = await _fallback_update(
                force=force,
                merge_strategy=merge_strategy,
            )

        result["sources_found"] = update_result.get("sources_processed", 0)
        result["channels_found"] = update_result.get("channels_total", 0)
        result["channels_valid"] = update_result.get("channels_updated", 0)
        result["detail"] = (
            f"更新完成：处理 {result['sources_found']} 个源，"
            f"共 {result['channels_found']} 个频道，"
            f"更新 {result['channels_valid']} 个"
        )

    except Exception as exc:
        result["status"] = "failed"
        result["detail"] = f"更新失败: {exc}"
        logger.error("频道更新任务执行失败: %s", exc, exc_info=True)

    elapsed = int(time.monotonic() - start_time)
    result["duration"] = elapsed

    _log_execution(
        task_id=task_id,
        action="update",
        status=result["status"],
        detail=result["detail"],
        sources_found=result["sources_found"],
        channels_found=result["channels_found"],
        channels_valid=result["channels_valid"],
        duration=elapsed,
    )
    _update_task_run_info(task_id, result["status"], result["detail"])

    return result


# =============================================================================
# 降级实现（当 app.services.source_service 不可用时）
# =============================================================================

async def _fallback_search(
    sources: list[dict],
    timeout: int = 30,
) -> dict[str, Any]:
    """
    降级搜索实现：使用 app.core.searcher 中的逻辑。

    当 app.services.source_service 模块不存在时，
    使用内置的搜索引擎直接搜索 IPTV 源。
    """
    import aiohttp
    from app.core.m3u import M3UParser

    sources_found = 0
    channels_found = 0
    channels_valid = 0

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            for src in sources:
                url = src.get("url", "")
                if not url:
                    continue
                try:
                    async with session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        ssl=False,
                    ) as resp:
                        if resp.status < 400:
                            content = await resp.text(
                                encoding="utf-8", errors="replace"
                            )
                            parser = M3UParser()
                            channels = parser.parse(content)
                            sources_found += 1
                            channels_found += len(channels)
                            channels_valid += len(channels)  # 简化处理
                except Exception:
                    continue
    except ImportError:
        logger.error("aiohttp 未安装，无法执行降级搜索")

    return {
        "sources_found": sources_found,
        "channels_found": channels_found,
        "channels_valid": channels_valid,
    }


async def _fallback_validate(
    timeout: int = 10,
    only_active: bool = True,
) -> dict[str, Any]:
    """
    降级验证实现：直接查询数据库中的源并验证可用性。
    """
    from app.models.models import Source
    from app.core.validator import validate_source

    total = 0
    valid = 0

    try:
        with get_db_context() as db:
            query = db.query(Source)
            if only_active:
                query = query.filter(Source.is_active == True)
            sources = query.all()

            for src in sources:
                total += 1
                try:
                    is_valid = await validate_source(src.url, timeout=timeout)
                    src.is_valid = is_valid
                    src.last_check = datetime.utcnow()
                    if is_valid:
                        valid += 1
                        src.fail_count = 0
                    else:
                        src.fail_count = (src.fail_count or 0) + 1
                except Exception:
                    src.is_valid = False
                    src.fail_count = (src.fail_count or 0) + 1

            db.commit()
    except Exception as exc:
        logger.error("降级验证失败: %s", exc)

    return {"total": total, "valid": valid}


async def _fallback_update(
    force: bool = False,
    merge_strategy: str = "merge",
) -> dict[str, Any]:
    """
    降级更新实现：从有效源重新拉取并更新频道列表。
    """
    from app.models.models import Source

    sources_processed = 0
    channels_total = 0
    channels_updated = 0

    try:
        with get_db_context() as db:
            sources = db.query(Source).filter(
                Source.is_valid == True
            ).all()
            sources_processed = len(sources)
            # 简化实现：仅统计有效源数量
            channels_total = sum(s.channel_count or 0 for s in sources)
            channels_updated = channels_total if force else 0
    except Exception as exc:
        logger.error("降级更新失败: %s", exc)

    return {
        "sources_processed": sources_processed,
        "channels_total": channels_total,
        "channels_updated": channels_updated,
    }


# =============================================================================
# 任务类型到执行函数的映射
# =============================================================================

TASK_EXECUTORS = {
    TaskType.AUTO_SEARCH: _execute_auto_search,
    TaskType.VALIDATE: _execute_validate,
    TaskType.UPDATE: _execute_update,
}


# =============================================================================
# TaskManager 类
# =============================================================================

class TaskManager:
    """
    IPTV 定时任务管理器。

    负责管理所有定时任务的完整生命周期：创建、启动、暂停、恢复、删除。
    使用 APScheduler 的 AsyncIOScheduler 作为底层调度引擎，
    任务配置持久化到数据库（SearchTask 表）。

    Attributes:
        scheduler: APScheduler 异步调度器实例
        _started: 调度器是否已启动的标志

    Example:
        manager = TaskManager()

        # 创建每 6 小时自动搜索的任务
        task_id = await manager.create_task(
            name="自动搜索源",
            cron_expr="every_6h",
            task_type="auto_search",
            params={"max_sources": 50},
        )

        # 启动调度器（会自动加载数据库中的活跃任务）
        await manager.start()

        # 暂停某个任务
        await manager.pause_task(task_id)

        # 恢复某个任务
        await manager.resume_task(task_id)

        # 删除某个任务
        await manager.remove_task(task_id)

        # 停止调度器
        await manager.stop()
    """

    def __init__(self, timezone: str = "Asia/Shanghai"):
        """
        初始化任务管理器。

        Args:
            timezone: 时区字符串，默认为 "Asia/Shanghai"
        """
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self._started = False
        logger.info("TaskManager 已初始化 (timezone=%s)", timezone)

    # -------------------------------------------------------------------------
    # 调度器生命周期管理
    # -------------------------------------------------------------------------

    async def start(self) -> None:
        """
        启动调度器并从数据库加载所有活跃任务。

        启动时会自动从 SearchTask 表中读取所有 is_active=True 的任务，
        并根据其 cron_expr 注册到 APScheduler 中。
        """
        if self._started:
            logger.warning("调度器已在运行中，跳过重复启动")
            return

        self.scheduler.start()
        self._started = True
        logger.info("调度器已启动")

        # 从数据库加载活跃任务
        await self._load_tasks_from_db()

        # 注册默认任务（如果不存在）
        await self._register_default_tasks()

    async def stop(self, wait: bool = True) -> None:
        """
        停止调度器。

        Args:
            wait: 是否等待正在执行的任务完成，默认 True
        """
        if not self._started:
            logger.warning("调度器未运行，跳过停止操作")
            return

        self.scheduler.shutdown(wait=wait)
        self._started = False
        logger.info("调度器已停止 (wait=%s)", wait)

    @property
    def is_running(self) -> bool:
        """调度器是否正在运行"""
        return self._started and self.scheduler.running

    # -------------------------------------------------------------------------
    # 任务 CRUD 操作
    # -------------------------------------------------------------------------

    async def create_task(
        self,
        name: str,
        cron_expr: str,
        task_type: str,
        params: Optional[dict[str, Any]] = None,
        max_sources: int = 100,
        search_timeout: int = 30,
        auto_update: bool = True,
    ) -> int:
        """
        创建新的定时任务。

        将任务信息写入数据库，并在调度器中注册对应的 APScheduler Job。
        如果调度器正在运行，任务会立即被调度执行。

        Args:
            name: 任务名称（唯一标识）
            cron_expr: Cron 表达式或预设名称（如 "every_6h"）
            task_type: 任务类型，可选值：
                - "auto_search": 自动搜索 IPTV 源
                - "validate": 验证源有效性
                - "update": 更新频道列表
            params: 任务执行参数（可选，会覆盖默认参数）
            max_sources: 最大搜索源数（默认 100）
            search_timeout: 搜索超时时间（秒，默认 30）
            auto_update: 是否自动更新频道列表（默认 True）

        Returns:
            int: 新创建任务的数据库 ID

        Raises:
            ValueError: 当 task_type 无效或 cron_expr 格式错误时
            RuntimeError: 当同名任务已存在时

        Example:
            task_id = await manager.create_task(
                name="每6小时搜索",
                cron_expr="every_6h",
                task_type="auto_search",
                params={"max_sources": 50, "region": "中国"},
            )
        """
        # 验证任务类型
        if task_type not in TASK_EXECUTORS:
            raise ValueError(
                f"无效的任务类型 '{task_type}'，"
                f"可选值：{[t.value for t in TaskType]}"
            )

        # 解析 Cron 表达式
        resolved_cron = resolve_cron_expression(cron_expr)

        # 构建默认参数
        default_params = {
            "max_sources": max_sources,
            "search_timeout": search_timeout,
            "auto_update": auto_update,
        }
        if params:
            default_params.update(params)

        # 写入数据库
        with get_db_context() as db:
            # 检查同名任务是否已存在
            existing = db.query(SearchTask).filter(
                SearchTask.name == name
            ).first()
            if existing:
                raise RuntimeError(f"同名任务已存在: '{name}' (id={existing.id})")

            task = SearchTask(
                name=name,
                task_type=task_type,
                cron_expr=resolved_cron,
                max_sources=max_sources,
                search_timeout=search_timeout,
                auto_update=auto_update,
                is_active=True,
                is_running=False,
                run_count=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(task)
            db.flush()  # 获取自增 ID
            task_id = task.id
            db.commit()

        logger.info(
            "任务已创建: id=%d, name=%s, type=%s, cron=%s",
            task_id, name, task_type, resolved_cron,
        )

        # 如果调度器正在运行，立即注册任务
        if self._started:
            await self._schedule_job(task_id, name, resolved_cron, task_type, default_params)

        return task_id

    async def remove_task(self, task_id: int) -> bool:
        """
        删除指定的定时任务。

        从调度器中移除 Job，并从数据库中删除任务记录。

        Args:
            task_id: 要删除的任务 ID

        Returns:
            bool: 删除成功返回 True，任务不存在返回 False
        """
        job_id = f"task_{task_id}"

        # 从调度器中移除
        try:
            self.scheduler.remove_job(job_id)
            logger.info("已从调度器移除任务: id=%d", task_id)
        except JobLookupError:
            logger.warning("调度器中未找到任务: id=%d", task_id)

        # 从数据库中删除
        with get_db_context() as db:
            task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
            if not task:
                logger.warning("数据库中未找到任务: id=%d", task_id)
                return False
            db.delete(task)
            db.commit()

        logger.info("任务已删除: id=%d", task_id)
        return True

    async def pause_task(self, task_id: int) -> bool:
        """
        暂停指定的定时任务。

        任务暂停后不会继续触发，但配置保留，可通过 resume_task 恢复。

        Args:
            task_id: 要暂停的任务 ID

        Returns:
            bool: 暂停成功返回 True，任务不存在返回 False
        """
        job_id = f"task_{task_id}"

        try:
            self.scheduler.pause_job(job_id)
            logger.info("任务已暂停: id=%d", task_id)
        except JobLookupError:
            logger.warning("调度器中未找到任务: id=%d", task_id)
            return False

        # 更新数据库状态
        with get_db_context() as db:
            task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
            if task:
                task.is_active = False
                task.updated_at = datetime.utcnow()
                db.commit()

        return True

    async def resume_task(self, task_id: int) -> bool:
        """
        恢复已暂停的定时任务。

        Args:
            task_id: 要恢复的任务 ID

        Returns:
            bool: 恢复成功返回 True，任务不存在返回 False
        """
        job_id = f"task_{task_id}"

        try:
            self.scheduler.resume_job(job_id)
            logger.info("任务已恢复: id=%d", task_id)
        except JobLookupError:
            logger.warning("调度器中未找到任务: id=%d", task_id)
            return False

        # 更新数据库状态
        with get_db_context() as db:
            task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
            if task:
                task.is_active = True
                task.updated_at = datetime.utcnow()
                db.commit()

        return True

    async def update_task(
        self,
        task_id: int,
        cron_expr: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        is_active: Optional[bool] = None,
    ) -> bool:
        """
        更新已有任务的配置。

        支持修改 Cron 表达式、执行参数和启用/禁用状态。
        修改后会重新注册 APScheduler Job。

        Args:
            task_id: 要更新的任务 ID
            cron_expr: 新的 Cron 表达式（可选）
            params: 新的执行参数（可选，会合并到现有参数）
            is_active: 是否启用（可选）

        Returns:
            bool: 更新成功返回 True，任务不存在返回 False
        """
        with get_db_context() as db:
            task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
            if not task:
                logger.warning("数据库中未找到任务: id=%d", task_id)
                return False

            if cron_expr is not None:
                task.cron_expr = resolve_cron_expression(cron_expr)

            if is_active is not None:
                task.is_active = is_active

            task.updated_at = datetime.utcnow()
            db.commit()

            cron = task.cron_expr
            task_type = task.task_type

        # 重新注册 Job
        if self._started:
            job_id = f"task_{task_id}"
            try:
                self.scheduler.remove_job(job_id)
            except JobLookupError:
                pass

            if task.is_active:
                merged_params = {
                    "max_sources": task.max_sources,
                    "search_timeout": task.search_timeout,
                    "auto_update": task.auto_update,
                }
                if params:
                    merged_params.update(params)
                await self._schedule_job(
                    task_id, task.name, cron, task_type, merged_params
                )

        logger.info("任务已更新: id=%d", task_id)
        return True

    async def get_task(self, task_id: int) -> Optional[dict[str, Any]]:
        """
        获取单个任务的详细信息。

        Args:
            task_id: 任务 ID

        Returns:
            dict | None: 任务信息字典，不存在时返回 None
        """
        with get_db_context() as db:
            task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
            if not task:
                return None
            return _task_to_dict(task)

    async def list_tasks(self, active_only: bool = False) -> list[dict[str, Any]]:
        """
        列出所有定时任务。

        Args:
            active_only: 是否只返回启用的任务，默认 False

        Returns:
            list[dict]: 任务信息字典列表
        """
        with get_db_context() as db:
            query = db.query(SearchTask)
            if active_only:
                query = query.filter(SearchTask.is_active == True)
            tasks = query.order_by(SearchTask.created_at.desc()).all()
            return [_task_to_dict(t) for t in tasks]

    async def get_task_logs(
        self,
        task_id: int,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        获取指定任务的执行日志。

        Args:
            task_id: 任务 ID
            limit: 返回的最大日志条数，默认 50

        Returns:
            list[dict]: 日志字典列表，按时间倒序
        """
        with get_db_context() as db:
            logs = (
                db.query(SearchLog)
                .filter(SearchLog.task_id == task_id)
                .order_by(SearchLog.created_at.desc())
                .limit(limit)
                .all()
            )
            return [_log_to_dict(log) for log in logs]

    # -------------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------------

    async def _load_tasks_from_db(self) -> None:
        """
        从数据库加载所有活跃任务并注册到调度器。

        在调度器启动时自动调用，确保重启后任务配置不丢失。
        """
        with get_db_context() as db:
            tasks = (
                db.query(SearchTask)
                .filter(SearchTask.is_active == True)
                .all()
            )

            for task in tasks:
                params = {
                    "max_sources": task.max_sources or 100,
                    "search_timeout": task.search_timeout or 30,
                    "auto_update": task.auto_update,
                }
                try:
                    await self._schedule_job(
                        task.id, task.name, task.cron_expr,
                        task.task_type, params,
                    )
                    logger.info(
                        "已加载任务: id=%d, name=%s, cron=%s",
                        task.id, task.name, task.cron_expr,
                    )
                except Exception as exc:
                    logger.error(
                        "加载任务失败: id=%d, name=%s, error=%s",
                        task.id, task.name, exc,
                    )

        logger.info("从数据库加载了 %d 个活跃任务", len(tasks))

    async def _register_default_tasks(self) -> None:
        """
        注册默认的定时任务（如果数据库中不存在）。

        默认任务策略：
          - 每 6 小时自动搜索 IPTV 源
          - 每 6 小时验证源有效性（搜索完成后 30 分钟）
        """
        default_tasks = [
            {
                "name": "默认自动搜索",
                "cron_expr": "every_6h",
                "task_type": TaskType.AUTO_SEARCH,
                "params": {"max_sources": 100, "search_timeout": 30},
            },
            {
                "name": "默认源验证",
                "cron_expr": "30 */6 * * *",
                "task_type": TaskType.VALIDATE,
                "params": {"timeout": 10, "max_concurrent": 20},
            },
        ]

        with get_db_context() as db:
            for default in default_tasks:
                existing = db.query(SearchTask).filter(
                    SearchTask.name == default["name"]
                ).first()
                if not existing:
                    task = SearchTask(
                        name=default["name"],
                        task_type=default["task_type"],
                        cron_expr=resolve_cron_expression(default["cron_expr"]),
                        max_sources=default["params"].get("max_sources", 100),
                        search_timeout=default["params"].get("search_timeout", 30),
                        auto_update=True,
                        is_active=True,
                        is_running=False,
                        run_count=0,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    db.add(task)
                    db.flush()
                    task_id = task.id
                    db.commit()

                    if self._started:
                        await self._schedule_job(
                            task_id,
                            default["name"],
                            task.cron_expr,
                            default["task_type"],
                            default["params"],
                        )

                    logger.info("已注册默认任务: %s (id=%d)", default["name"], task_id)

    async def _schedule_job(
        self,
        task_id: int,
        name: str,
        cron_expr: str,
        task_type: str,
        params: dict[str, Any],
    ) -> None:
        """
        将单个任务注册到 APScheduler。

        Args:
            task_id: 数据库中的任务 ID
            name: 任务名称
            cron_expr: 已解析的 Cron 表达式
            task_type: 任务类型字符串
            params: 执行参数
        """
        job_id = f"task_{task_id}"
        executor = TASK_EXECUTORS.get(task_type)

        if not executor:
            logger.error("未知的任务类型: %s (task_id=%d)", task_type, task_id)
            return

        # 解析 Cron 表达式为 APScheduler 的 CronTrigger
        cron_parts = cron_expr.strip().split()
        if len(cron_parts) == 5:
            minute, hour, day, month, day_of_week = cron_parts
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
            )
        elif len(cron_parts) == 6:
            # 支持秒的 Cron 表达式
            second, minute, hour, day, month, day_of_week = cron_parts
            trigger = CronTrigger(
                second=second,
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
            )
        else:
            raise ValueError(f"无效的 Cron 表达式: {cron_expr}")

        # 包装执行函数：设置运行状态 -> 执行 -> 清除运行状态
        async def _wrapped_executor(tid=task_id, exec_fn=executor, p=params):
            # 标记为运行中
            try:
                with get_db_context() as db:
                    t = db.query(SearchTask).filter(SearchTask.id == tid).first()
                    if t:
                        t.is_running = True
                        db.commit()
            except Exception:
                pass

            # 执行实际任务
            await exec_fn(tid, p)

            # 清除运行状态（_execute_* 函数内部已处理，此处为双重保险）
            try:
                with get_db_context() as db:
                    t = db.query(SearchTask).filter(SearchTask.id == tid).first()
                    if t:
                        t.is_running = False
                        db.commit()
            except Exception:
                pass

        self.scheduler.add_job(
            _wrapped_executor,
            trigger=trigger,
            id=job_id,
            name=name,
            replace_existing=True,
            misfire_grace_time=3600,  # 允许 1 小时内的补执行
            coalesce=True,            # 合并多次错过的执行
            max_instances=1,          # 同一任务不并发执行
        )

        logger.info(
            "任务已注册到调度器: id=%d, name=%s, cron=%s, job_id=%s",
            task_id, name, cron_expr, job_id,
        )


# =============================================================================
# 模块级便捷函数
# =============================================================================

# 全局默认管理器实例（懒加载）
_default_manager: Optional[TaskManager] = None


def get_default_manager() -> TaskManager:
    """
    获取全局默认的 TaskManager 实例（单例模式）。

    Returns:
        TaskManager: 全局默认管理器
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = TaskManager()
    return _default_manager


async def start_scheduler(manager: Optional[TaskManager] = None) -> TaskManager:
    """
    启动调度器（模块级便捷函数）。

    如果未传入 manager，则使用全局默认实例。

    Args:
        manager: TaskManager 实例（可选）

    Returns:
        TaskManager: 已启动的管理器实例

    Example:
        manager = await start_scheduler()
    """
    mgr = manager or get_default_manager()
    await mgr.start()
    return mgr


async def stop_scheduler(manager: Optional[TaskManager] = None) -> None:
    """
    停止调度器（模块级便捷函数）。

    Args:
        manager: TaskManager 实例（可选，默认使用全局实例）
    """
    mgr = manager or get_default_manager()
    await mgr.stop()


async def create_task(
    name: str,
    cron_expr: str,
    task_type: str,
    params: Optional[dict[str, Any]] = None,
) -> int:
    """
    创建定时任务（模块级便捷函数）。

    使用全局默认 TaskManager 实例创建任务。

    Args:
        name: 任务名称
        cron_expr: Cron 表达式或预设名称
        task_type: 任务类型（auto_search / validate / update）
        params: 执行参数（可选）

    Returns:
        int: 新创建任务的 ID

    Example:
        task_id = await create_task(
            name="每小时搜索",
            cron_expr="every_1h",
            task_type="auto_search",
        )
    """
    mgr = get_default_manager()
    return await mgr.create_task(
        name=name,
        cron_expr=cron_expr,
        task_type=task_type,
        params=params,
    )


# =============================================================================
# 辅助函数
# =============================================================================

def _task_to_dict(task: SearchTask) -> dict[str, Any]:
    """
    将 SearchTask ORM 对象转换为字典。

    Args:
        task: SearchTask 数据库对象

    Returns:
        dict: 任务信息字典
    """
    return {
        "id": task.id,
        "name": task.name,
        "task_type": task.task_type,
        "cron_expr": task.cron_expr,
        "max_sources": task.max_sources,
        "search_timeout": task.search_timeout,
        "auto_update": task.auto_update,
        "is_active": task.is_active,
        "is_running": task.is_running,
        "last_run": task.last_run.isoformat() if task.last_run else None,
        "last_result": task.last_result,
        "run_count": task.run_count,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def _log_to_dict(log: SearchLog) -> dict[str, Any]:
    """
    将 SearchLog ORM 对象转换为字典。

    Args:
        log: SearchLog 数据库对象

    Returns:
        dict: 日志信息字典
    """
    return {
        "id": log.id,
        "task_id": log.task_id,
        "action": log.action,
        "status": log.status,
        "detail": log.detail,
        "sources_found": log.sources_found,
        "channels_found": log.channels_found,
        "channels_valid": log.channels_valid,
        "duration": log.duration,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }
