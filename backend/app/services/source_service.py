"""IPTV 源服务层 - 提供源 CRUD、验证和频道导入功能"""
from typing import Optional
import asyncio
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Source, SourceChannel, Channel
from app.core.m3u import M3UParser
from app.core.validator import validate_source


def get_sources(
    db: Session,
    region: Optional[str] = None,
    operator: Optional[str] = None,
    is_valid: Optional[bool] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    获取 IPTV 源列表，支持筛选和分页。

    Args:
        db: 数据库会话
        region: 地区筛选
        operator: 运营商筛选
        is_valid: 是否有效筛选
        page: 页码
        page_size: 每页条数

    Returns:
        dict: {"items": [Source, ...], "total": int, "page": int, "page_size": int}
    """
    query = db.query(Source)

    if region:
        query = query.filter(Source.region.like(f"%{region}%"))
    if operator:
        query = query.filter(Source.operator.like(f"%{operator}%"))
    if is_valid is not None:
        query = query.filter(Source.is_valid == is_valid)  # noqa: E712

    total = query.count()
    items = (
        query.order_by(Source.priority.desc(), Source.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def create_source(db: Session, data: dict) -> Source:
    """
    创建新的 IPTV 源。

    Args:
        db: 数据库会话
        data: 源字段字典

    Returns:
        新创建的 Source 对象
    """
    source = Source(**data)
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def update_source(db: Session, source_id: int, data: dict) -> Optional[Source]:
    """
    更新 IPTV 源信息。

    Args:
        db: 数据库会话
        source_id: 源 ID
        data: 待更新的字段字典

    Returns:
        更新后的 Source 对象，源不存在时返回 None
    """
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        return None
    for key, value in data.items():
        if hasattr(source, key):
            setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return source


def delete_source(db: Session, source_id: int) -> bool:
    """
    删除 IPTV 源及其所有关联的 source_channels 记录。

    Args:
        db: 数据库会话
        source_id: 源 ID

    Returns:
        是否删除成功
    """
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        return False
    # 先删除关联的 source_channels
    db.query(SourceChannel).filter(SourceChannel.source_id == source_id).delete()
    db.delete(source)
    db.commit()
    return True


async def validate_source_db(db: Session, source_id: int) -> dict:
    """
    验证单个 IPTV 源（异步执行网络请求，更新数据库状态）。

    Args:
        db: 数据库会话
        source_id: 源 ID

    Returns:
        验证结果字典
    """
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        return {"valid": False, "error": "源不存在"}

    result = await validate_source(source.url, timeout=source.timeout or 10)

    source.is_valid = result.get("valid", False)
    source.last_check = datetime.utcnow()
    source.channel_count = result.get("channel_count", 0)

    if result.get("valid"):
        source.last_success = datetime.utcnow()
        source.fail_count = 0
    else:
        source.fail_count = (source.fail_count or 0) + 1

    db.commit()
    db.refresh(source)

    return result


async def validate_all_sources(db: Session) -> list[dict]:
    """
    验证数据库中所有启用的 IPTV 源（异步批量执行）。

    Args:
        db: 数据库会话

    Returns:
        每个源的验证结果列表
    """
    sources = db.query(Source).filter(Source.is_active == True).all()  # noqa: E712

    results = []
    for source in sources:
        result = await validate_source(source.url, timeout=source.timeout or 10)
        result["source_id"] = source.id
        result["source_name"] = source.name
        results.append(result)

        source.is_valid = result.get("valid", False)
        source.last_check = datetime.utcnow()
        source.channel_count = result.get("channel_count", 0)

        if result.get("valid"):
            source.last_success = datetime.utcnow()
            source.fail_count = 0
        else:
            source.fail_count = (source.fail_count or 0) + 1

    db.commit()
    return results


async def import_channels_from_source(db: Session, source_id: int) -> dict:
    """
    从 IPTV 源导入频道到数据库（异步获取 M3U 并解析入库）。

    逻辑：
    1. 验证源是否有效
    2. 解析 M3U 内容
    3. 将每个 M3UChannel 与 Channel 表关联（创建或更新 source_channels 记录）

    Args:
        db: 数据库会话
        source_id: 源 ID

    Returns:
        dict: {"imported": int, "updated": int, "total": int, "valid": bool}
    """
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        return {"imported": 0, "updated": 0, "total": 0, "valid": False, "error": "源不存在"}

    # 验证并获取频道列表
    result = await validate_source(source.url, timeout=source.timeout or 10)
    channels = result.get("channels", [])

    if not channels:
        return {"imported": 0, "updated": 0, "total": 0, "valid": result.get("valid", False)}

    imported = 0
    updated = 0

    for m3u_ch in channels:
        # 查找或创建 Channel 记录
        channel = db.query(Channel).filter(Channel.name == m3u_ch.name).first()
        if not channel:
            channel = Channel(
                name=m3u_ch.name,
                group_title=m3u_ch.group_title or "未分组",
                tvg_id=m3u_ch.tvg_id,
                tvg_name=m3u_ch.tvg_name,
                tvg_logo=m3u_ch.tvg_logo,
                region=source.region or m3u_ch.extra_tags.get("_region", ""),
                operator=source.operator or m3u_ch.extra_tags.get("_operator", ""),
            )
            db.add(channel)
            db.flush()  # 获取 channel.id

        # 关联 source_channel
        existing_sc = (
            db.query(SourceChannel)
            .filter(
                SourceChannel.source_id == source_id,
                SourceChannel.channel_id == channel.id,
                SourceChannel.stream_url == m3u_ch.url,
            )
            .first()
        )
        if not existing_sc:
            sc = SourceChannel(
                source_id=source_id,
                channel_id=channel.id,
                stream_url=m3u_ch.url,
                priority=source.priority,
            )
            db.add(sc)
            imported += 1
        else:
            existing_sc.is_working = True
            existing_sc.last_check = datetime.utcnow()
            updated += 1

    # 更新源的频道数
    source.channel_count = result.get("channel_count", 0)
    source.is_valid = result.get("valid", False)
    source.last_check = datetime.utcnow()

    db.commit()

    return {
        "imported": imported,
        "updated": updated,
        "total": len(channels),
        "valid": result.get("valid", False),
    }


def get_source_channels(db: Session, source_id: int) -> list[SourceChannel]:
    """
    获取指定 IPTV 源下的所有关联频道记录。

    Args:
        db: 数据库会话
        source_id: 源 ID

    Returns:
        SourceChannel 列表
    """
    return (
        db.query(SourceChannel)
        .filter(SourceChannel.source_id == source_id)
        .order_by(SourceChannel.priority.desc(), SourceChannel.id.asc())
        .all()
    )
