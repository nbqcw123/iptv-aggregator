"""
IPTV 聚合器 — 后端管理 API
============================
管理功能：
1. 频道管理（CRUD + 批量导入/导出）
2. 搜索结果管理（查看/编辑/删除/手动添加）
3. 输出配置（M3U/TXT 格式自定义）
4. 系统设置（采集参数、定时任务、数据库维护）
"""
import os
import json
import time
from typing import Optional
from fastapi import APIRouter, Query, Body
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.core.searcher import (
    Channel, ScheduleConfig, PlayEntry,
    load_channels, save_channels,
    load_schedule, save_schedule,
    load_result, save_result,
    gen_m3u_from_result, gen_txt_from_result,
    load_speed_cache, DATA_DIR, MAX_KEEP,
    CHANNEL_CATEGORIES,
)
from app.core.collector import IpvDB

router = APIRouter()

# ============ 数据模型 ============

class ChannelCreateReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    group: str = Field(default="未分组")
    enabled: bool = Field(default=True)
    max_results: int = Field(default=MAX_KEEP, ge=1, le=50)

class ChannelEditReq(BaseModel):
    name: Optional[str] = None
    group: Optional[str] = None
    enabled: Optional[bool] = None
    max_results: Optional[int] = Field(None, ge=1, le=50)

class SearchResultEditReq(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    group: Optional[str] = None
    source_name: Optional[str] = None

class OutputConfigReq(BaseModel):
    m3u_header: Optional[str] = None
    txt_separator: Optional[str] = None
    include_group: Optional[bool] = None
    include_logo: Optional[bool] = None
    include_epg: Optional[bool] = None
    sort_by: Optional[str] = None  # name/response_time/group
    sort_order: Optional[str] = None  # asc/desc
    filter_protocol: Optional[str] = None  # ipv4/ipv6/all
    filter_max_response: Optional[int] = None  # ms, 0=不限
    group_emoji: Optional[bool] = None

class SystemSettingsReq(BaseModel):
    auto_cleanup_days: Optional[int] = None
    max_log_entries: Optional[int] = None
    default_concurrency: Optional[int] = None
    default_timeout: Optional[int] = None
    default_max_keep: Optional[int] = None
    api_timeout: Optional[int] = None


# ============ 1. 频道管理 ============

@router.get("/admin/channels", summary="管理-获取频道列表（含统计）")
async def admin_list_channels(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    group_filter: str = Query(default=""),
    enabled_filter: str = Query(default=""),  # true/false/空
    keyword: str = Query(default=""),
):
    channels = load_channels()
    
    # 过滤
    if group_filter:
        channels = [c for c in channels if c.group == group_filter]
    if enabled_filter == "true":
        channels = [c for c in channels if c.enabled]
    elif enabled_filter == "false":
        channels = [c for c in channels if not c.enabled]
    if keyword:
        kw = keyword.lower()
        channels = [c for c in channels if kw in c.name.lower() or kw in c.group.lower()]
    
    total = len(channels)
    start = (page - 1) * page_size
    end = start + page_size
    page_data = channels[start:end]
    
    # 获取所有分组
    all_groups = list(set(c.group for c in load_channels()))
    
    return {"code": 0, "message": "ok", "data": {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "groups": all_groups,
        "channels": [
            {"id": c.id, "name": c.name, "group": c.group,
             "enabled": c.enabled, "max_results": c.max_results}
            for c in page_data
        ],
    }}


@router.post("/admin/channels", summary="管理-添加频道")
async def admin_create_channel(req: ChannelCreateReq):
    channels = load_channels()
    ch_id = f"ch_{int(time.time()*1000):012d}"
    ch = Channel(id=ch_id, name=req.name, group=req.group,
                 enabled=req.enabled, max_results=req.max_results)
    channels.append(ch)
    save_channels(channels)
    return {"code": 0, "message": "添加成功", "data": {"id": ch_id}}


@router.put("/admin/channels/{ch_id}", summary="管理-编辑频道")
async def admin_update_channel(ch_id: str, req: ChannelEditReq):
    channels = load_channels()
    for ch in channels:
        if ch.id == ch_id:
            if req.name is not None: ch.name = req.name
            if req.group is not None: ch.group = req.group
            if req.enabled is not None: ch.enabled = req.enabled
            if req.max_results is not None: ch.max_results = req.max_results
            save_channels(channels)
            return {"code": 0, "message": "更新成功", "data": None}
    return {"code": 1, "message": "频道不存在", "data": None}


@router.delete("/admin/channels/{ch_id}", summary="管理-删除频道")
async def admin_delete_channel(ch_id: str):
    channels = load_channels()
    new_list = [c for c in channels if c.id != ch_id]
    if len(new_list) == len(channels):
        return {"code": 1, "message": "频道不存在", "data": None}
    save_channels(new_list)
    return {"code": 0, "message": "删除成功", "data": None}


@router.post("/admin/channels/batch", summary="管理-批量操作")
async def admin_batch_channels(
    action: str = Query(..., description="delete/disable/enable/change_group"),
    ids: list[str] = Body(default=[]),
    group: str = Body(default=""),
):
    channels = load_channels()
    count = 0
    
    if action == "delete":
        new_list = [c for c in channels if c.id not in ids]
        count = len(channels) - len(new_list)
        save_channels(new_list)
    elif action == "disable":
        for c in channels:
            if c.id in ids:
                c.enabled = False
                count += 1
        save_channels(channels)
    elif action == "enable":
        for c in channels:
            if c.id in ids:
                c.enabled = True
                count += 1
        save_channels(channels)
    elif action == "change_group":
        for c in channels:
            if c.id in ids:
                c.group = group
                count += 1
        save_channels(channels)
    
    return {"code": 0, "message": f"操作完成: {count} 条受影响", "data": {"affected": count}}


@router.get("/admin/channels/export", summary="管理-导出频道表")
async def admin_export_channels(format: str = Query(default="json")):
    channels = load_channels()
    if format == "json":
        data = json.dumps([{"name": c.name, "group": c.group, "enabled": c.enabled, "max_results": c.max_results} for c in channels], ensure_ascii=False, indent=2)
        return PlainTextResponse(content=data, media_type="application/json",
                                headers={"Content-Disposition": "attachment; filename=channels.json"})
    elif format == "txt":
        lines = []
        for c in channels:
            status = "启用" if c.enabled else "禁用"
            lines.append(f"{c.name}\t{c.group}\t{status}\t{c.max_results}")
        return PlainTextResponse(content="\n".join(lines), media_type="text/plain",
                                headers={"Content-Disposition": "attachment; filename=channels.txt"})
    return {"code": 1, "message": "不支持的格式"}


@router.get("/admin/channels/categories", summary="管理-获取分类模板")
async def admin_get_categories():
    return {"code": 0, "message": "ok", "data": CHANNEL_CATEGORIES}


# ============ 2. 搜索结果管理 ============

@router.get("/admin/results", summary="管理-获取搜索结果")
async def admin_list_results(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    group_filter: str = Query(default=""),
    keyword: str = Query(default=""),
    sort_by: str = Query(default="name"),  # name/response_time/group
    sort_order: str = Query(default="asc"),  # asc/desc
):
    entries = load_result()
    
    # 过滤
    if group_filter:
        entries = [e for e in entries if e.get("group", "") == group_filter]
    if keyword:
        kw = keyword.lower()
        entries = [e for e in entries if kw in e.get("name", "").lower() or kw in e.get("url", "").lower()]
    
    # 排序
    reverse = sort_order == "desc"
    if sort_by == "response_time":
        entries.sort(key=lambda x: x.get("response_time", 0), reverse=reverse)
    elif sort_by == "group":
        entries.sort(key=lambda x: x.get("group", ""), reverse=reverse)
    else:
        entries.sort(key=lambda x: x.get("name", ""), reverse=reverse)
    
    total = len(entries)
    start = (page - 1) * page_size
    end = start + page_size
    
    # 获取所有分组
    all_groups = list(set(e.get("group", "未分组") for e in load_result()))
    
    return {"code": 0, "message": "ok", "data": {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "groups": all_groups,
        "results": entries[start:end],
    }}


@router.put("/admin/results/{idx}", summary="管理-编辑搜索结果")
async def admin_update_result(idx: int, req: SearchResultEditReq):
    entries = load_result()
    if idx < 0 or idx >= len(entries):
        return {"code": 1, "message": "索引越界", "data": None}
    if req.name is not None: entries[idx]["name"] = req.name
    if req.url is not None: entries[idx]["url"] = req.url
    if req.group is not None: entries[idx]["group"] = req.group
    if req.source_name is not None: entries[idx]["source_name"] = req.source_name
    save_result(entries)
    return {"code": 0, "message": "更新成功", "data": None}


@router.delete("/admin/results/{idx}", summary="管理-删除搜索结果")
async def admin_delete_result(idx: int):
    entries = load_result()
    if idx < 0 or idx >= len(entries):
        return {"code": 1, "message": "索引越界", "data": None}
    entries.pop(idx)
    save_result(entries)
    return {"code": 0, "message": "删除成功", "data": None}


@router.post("/admin/results", summary="管理-手动添加搜索结果")
async def admin_add_result(req: dict = Body(...)):
    entries = load_result()
    entry = {
        "name": req.get("name", "未命名"),
        "url": req.get("url", ""),
        "group": req.get("group", "未分组"),
        "source_name": req.get("source_name", "手动添加"),
        "source_type": req.get("source_type", "custom"),
        "protocol": req.get("protocol", "ipv4"),
        "response_time": req.get("response_time", 0),
    }
    if not entry["url"]:
        return {"code": 1, "message": "URL 不能为空", "data": None}
    entries.append(entry)
    save_result(entries)
    return {"code": 0, "message": "添加成功", "data": {"index": len(entries) - 1}}


@router.delete("/admin/results", summary="管理-清空搜索结果")
async def admin_clear_results():
    save_result([])
    return {"code": 0, "message": "已清空", "data": None}


# ============ 3. 输出配置 ============

@router.get("/admin/output-config", summary="管理-获取输出配置")
async def admin_get_output_config():
    config_file = os.path.join(DATA_DIR, "output_config.json")
    default_config = {
        "m3u_header": "#EXTM3U",
        "txt_separator": ",",
        "include_group": True,
        "include_logo": True,
        "include_epg": True,
        "sort_by": "name",
        "sort_order": "asc",
        "filter_protocol": "all",
        "filter_max_response": 0,
        "group_emoji": True,
    }
    if os.path.exists(config_file):
        with open(config_file) as f:
            saved = json.load(f)
        default_config.update(saved)
    return {"code": 0, "message": "ok", "data": default_config}


@router.post("/admin/output-config", summary="管理-保存输出配置")
async def admin_save_output_config(req: OutputConfigReq):
    config_file = os.path.join(DATA_DIR, "output_config.json")
    current = {}
    if os.path.exists(config_file):
        with open(config_file) as f:
            current = json.load(f)
    
    update_data = {k: v for k, v in req.dict().items() if v is not None}
    current.update(update_data)
    
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(config_file, "w") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    
    return {"code": 0, "message": "保存成功", "data": current}


@router.get("/admin/preview/m3u", summary="管理-预览 M3U 输出")
async def admin_preview_m3u():
    content = gen_m3u_from_result()
    if not content:
        content = "#EXTM3U\n# 暂无数据\n"
    return PlainTextResponse(content=content, media_type="audio/x-mpegurl")


@router.get("/admin/preview/txt", summary="管理-预览 TXT 输出")
async def admin_preview_txt():
    content = gen_txt_from_result()
    if not content:
        content = "# 暂无数据\n"
    return PlainTextResponse(content=content, media_type="text/plain")


# ============ 4. 系统设置 ============

@router.get("/admin/settings", summary="管理-获取系统设置")
async def admin_get_settings():
    config_file = os.path.join(DATA_DIR, "system_settings.json")
    default_settings = {
        "auto_cleanup_days": 7,
        "max_log_entries": 100,
        "default_concurrency": 20,
        "default_timeout": 5,
        "default_max_keep": 10,
        "api_timeout": 30,
    }
    if os.path.exists(config_file):
        with open(config_file) as f:
            saved = json.load(f)
        default_settings.update(saved)
    
    # 获取定时任务配置
    schedule = load_schedule()
    
    return {"code": 0, "message": "ok", "data": {
        "settings": default_settings,
        "schedule": {
            "enabled": schedule.enabled,
            "hour": schedule.hour,
            "minute": schedule.minute,
            "source_type": schedule.source_type,
            "ip_version": schedule.ip_version,
            "concurrency": schedule.concurrency,
            "timeout": schedule.timeout,
            "max_keep": schedule.max_keep,
        },
        "data_dir": DATA_DIR,
    }}


@router.post("/admin/settings", summary="管理-保存系统设置")
async def admin_save_settings(req: SystemSettingsReq):
    config_file = os.path.join(DATA_DIR, "system_settings.json")
    current = {}
    if os.path.exists(config_file):
        with open(config_file) as f:
            current = json.load(f)
    
    update_data = {k: v for k, v in req.dict().items() if v is not None}
    current.update(update_data)
    
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(config_file, "w") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    
    return {"code": 0, "message": "保存成功", "data": current}


@router.post("/admin/schedule", summary="管理-保存定时任务")
async def admin_save_schedule(req: dict = Body(...)):
    cfg = ScheduleConfig(
        enabled=req.get("enabled", False),
        hour=req.get("hour", 3),
        minute=req.get("minute", 0),
        source_type=req.get("source_type", "all"),
        ip_version=req.get("ip_version", "ipv4"),
        concurrency=req.get("concurrency", 20),
        timeout=req.get("timeout", 5),
        max_keep=req.get("max_keep", 10),
    )
    save_schedule(cfg)
    return {"code": 0, "message": "保存成功", "data": None}


# ============ 5. 数据库维护 ============

@router.get("/admin/db/stats", summary="管理-数据库统计")
async def admin_db_stats():
    db = IpvDB()
    return {"code": 0, "message": "ok", "data": {
        "active_ips": db.get_ip_count("active"),
        "temp_failed_ips": db.get_ip_count("temp_failed"),
        "total_ips": db.get_ip_count("all"),
        "db_size_mb": round(os.path.getsize(os.path.join(DATA_DIR, "iptv.db")) / 1024 / 1024, 2) if os.path.exists(os.path.join(DATA_DIR, "iptv.db")) else 0,
    }}


@router.get("/admin/db/logs", summary="管理-采集日志")
async def admin_db_logs(limit: int = Query(default=20, ge=1, le=100)):
    db = IpvDB()
    rows = db.conn.execute(
        "SELECT * FROM collect_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return {"code": 0, "message": "ok", "data": [dict(r) for r in rows]}


@router.post("/admin/db/cleanup", summary="管理-清理数据库")
async def admin_db_cleanup(
    clear_failed: bool = Query(default=False),
    clear_logs: bool = Query(default=False),
    clear_speed_cache: bool = Query(default=False),
):
    db = IpvDB()
    result = {"cleared": []}
    
    if clear_failed:
        db.conn.execute("DELETE FROM ips WHERE status='temp_failed'")
        db.conn.commit()
        result["cleared"].append("temp_failed_ips")
    
    if clear_logs:
        db.conn.execute("DELETE FROM collect_log")
        db.conn.commit()
        result["cleared"].append("collect_logs")
    
    if clear_speed_cache:
        cache_file = os.path.join(DATA_DIR, "speed_cache.json")
        if os.path.exists(cache_file):
            os.remove(cache_file)
        result["cleared"].append("speed_cache")
    
    return {"code": 0, "message": "清理完成", "data": result}


@router.post("/admin/db/reset", summary="管理-重置所有数据")
async def admin_db_reset():
    """重置所有数据（谨慎操作）"""
    db = IpvDB()
    db.conn.execute("DELETE FROM ips")
    db.conn.execute("DELETE FROM collect_log")
    db.conn.commit()
    
    # 清除缓存文件
    for f in ["speed_cache.json", "result_cache.json"]:
        fp = os.path.join(DATA_DIR, f)
        if os.path.exists(fp):
            os.remove(fp)
    
    return {"code": 0, "message": "已重置所有数据", "data": None}
