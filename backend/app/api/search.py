"""IPTV API v3 — 频道表 + 测速择优 + 定时更新"""
import asyncio
import time
import threading
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from app.core.searcher import (
    Channel, ScheduleConfig, PlayEntry,
    load_channels, save_channels,
    load_schedule, save_schedule,
    run_full_pipeline, load_result, save_result,
    gen_m3u, gen_txt, load_speed_cache,
    MAX_KEEP, DATA_DIR,
)

router = APIRouter()

# ============ 后台定时任务 ============
_scheduler_thread: Optional[threading.Thread] = None
_scheduler_running = False

def _scheduler_loop():
    """后台定时任务循环"""
    global _scheduler_running
    while _scheduler_running:
        cfg = load_schedule()
        if cfg.enabled:
            now = time.localtime()
            if now.tm_hour == cfg.hour and now.tm_min == cfg.minute:
                try:
                    channels = load_channels()
                    result = asyncio.run(run_full_pipeline(
                        channels=channels,
                        source_type=cfg.source_type,
                        ip_version=cfg.ip_version,
                        concurrency=cfg.concurrency,
                        timeout=cfg.timeout,
                        max_keep=cfg.max_keep,
                    ))
                    save_result(result["entries"])
                except Exception as e:
                    print(f"[scheduler] 定时更新失败: {e}")
                time.sleep(60)  # 同一分钟内不重复执行
            else:
                time.sleep(30)
        else:
            time.sleep(60)

def start_scheduler():
    global _scheduler_thread, _scheduler_running
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()

def stop_scheduler():
    global _scheduler_running
    _scheduler_running = False

# 启动时自动启停
cfg = load_schedule()
if cfg.enabled:
    start_scheduler()

# ============ Pydantic 模型 ============

class ChannelReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="频道名称")
    group: str = Field(default="未分组", description="分组")
    enabled: bool = Field(default=True, description="是否启用")
    max_results: int = Field(default=MAX_KEEP, ge=1, le=50, description="最大保留条数")

class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    group: Optional[str] = None
    enabled: Optional[bool] = None
    max_results: Optional[int] = Field(None, ge=1, le=50)

class ScheduleReq(BaseModel):
    enabled: bool = False
    hour: int = Field(default=3, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    source_type: str = Field(default="all")
    ip_version: str = Field(default="ipv4", description="ipv4/ipv6/both")
    concurrency: int = Field(default=20, ge=1, le=100)
    timeout: int = Field(default=5, ge=2, le=30)
    max_keep: int = Field(default=MAX_KEEP, ge=1, le=50)

class SearchReq(BaseModel):
    source_type: str = Field(default="all")
    ip_version: str = Field(default="ipv4")
    concurrency: int = Field(default=20, ge=1, le=100)
    timeout: int = Field(default=5, ge=2, le=30)
    search_timeout: int = Field(default=15, ge=5, le=60)
    max_keep: int = Field(default=MAX_KEEP, ge=1, le=50)

# ============ 频道表 CRUD ============

@router.get("/channels", summary="获取频道表")
async def list_channels():
    channels = load_channels()
    return {"code": 0, "message": "ok", "data": [
        {"id": ch.id, "name": ch.name, "group": ch.group,
         "enabled": ch.enabled, "max_results": ch.max_results}
        for ch in channels
    ]}

@router.post("/channels", summary="添加频道")
async def add_channel(req: ChannelReq):
    channels = load_channels()
    ch_id = f"ch_{int(time.time()*1000):012d}"
    ch = Channel(id=ch_id, name=req.name, group=req.group,
                 enabled=req.enabled, max_results=req.max_results)
    channels.append(ch)
    save_channels(channels)
    return {"code": 0, "message": "添加成功", "data": {"id": ch_id}}

@router.put("/channels/{ch_id}", summary="更新频道")
async def update_channel(ch_id: str, req: ChannelUpdate):
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

@router.delete("/channels/{ch_id}", summary="删除频道")
async def delete_channel(ch_id: str):
    channels = load_channels()
    new_list = [ch for ch in channels if ch.id != ch_id]
    if len(new_list) == len(channels):
        return {"code": 1, "message": "频道不存在", "data": None}
    save_channels(new_list)
    return {"code": 0, "message": "删除成功", "data": None}

@router.post("/channels/import", summary="批量导入频道")
async def import_channels(req: list[ChannelReq]):
    channels = load_channels()
    count = 0
    existing_names = {ch.name for ch in channels}
    for r in req:
        if r.name not in existing_names:
            ch_id = f"ch_{int(time.time()*1000)+count:012d}"
            channels.append(Channel(id=ch_id, name=r.name, group=r.group,
                                   enabled=r.enabled, max_results=r.max_results))
            count += 1
    save_channels(channels)
    return {"code": 0, "message": f"导入成功: {count} 条新增", "data": {"imported": count}}

@router.post("/channels/reset", summary="重置为默认频道表")
async def reset_channels():
    # 删除现有文件以触发重建
    import os
    f = os.path.join(DATA_DIR, "channels.json")
    if os.path.exists(f):
        os.remove(f)
    channels = load_channels()
    return {"code": 0, "message": f"已重置为默认 {len(channels)} 个频道", "data": None}

# ============ 定时任务 ============

@router.get("/schedule", summary="获取定时配置")
async def get_schedule():
    cfg = load_schedule()
    return {"code": 0, "message": "ok", "data": {
        "enabled": cfg.enabled, "hour": cfg.hour, "minute": cfg.minute,
        "source_type": cfg.source_type, "ip_version": cfg.ip_version,
        "concurrency": cfg.concurrency, "timeout": cfg.timeout, "max_keep": cfg.max_keep,
    }}

@router.post("/schedule", summary="更新定时配置")
async def update_schedule(req: ScheduleReq):
    cfg = ScheduleConfig(
        enabled=req.enabled, hour=req.hour, minute=req.minute,
        source_type=req.source_type, ip_version=req.ip_version,
        concurrency=req.concurrency, timeout=req.timeout, max_keep=req.max_keep,
    )
    save_schedule(cfg)
    if cfg.enabled:
        start_scheduler()
    else:
        stop_scheduler()
    return {"code": 0, "message": "保存成功", "data": None}

# ============ 搜索+测速完整流程 ============

@router.post("/run", summary="执行完整流程：搜索→测速→择优")
async def run_pipeline(req: SearchReq):
    channels = load_channels()
    if not channels:
        return {"code": 1, "message": "频道表为空，请先添加频道", "data": None}

    result = await run_full_pipeline(
        channels=channels,
        source_type=req.source_type,
        ip_version=req.ip_version,
        concurrency=req.concurrency,
        timeout=req.timeout,
        max_keep=req.max_keep,
        search_timeout=req.search_timeout,
    )

    save_result(result["entries"])

    entries_data = [{
        "name": e.name, "url": e.url, "group": e.group,
        "source_name": e.source_name, "source_type": e.source_type,
        "protocol": e.protocol, "response_time": e.response_time,
    } for e in result["entries"]]

    return {"code": 0, "message": "完成", "data": {
        "entries": entries_data,
        "stats": result["stats"],
        "channel_stats": result["channel_stats"],
    }}

# =-----------= 导出 ============

@router.get("/export/m3u", summary="导出 M3U")
async def export_m3u():
    entries = load_result()
    if not entries:
        return PlainTextResponse(content="#EXTM3U\n", media_type="audio/x-mpegurl")
    content = gen_m3u(entries)
    header = f"attachment; filename=iptv_{len(entries)}.m3u"
    return PlainTextResponse(content=content, media_type="audio/x-mpegurl",
                            headers={"Content-Disposition": header})

@router.get("/export/txt", summary="导出 TXT")
async def export_txt(sep: str = Query(default=",")):
    entries = load_result()
    if not entries:
        return PlainTextResponse(content="", media_type="text/plain")
    content = gen_txt(entries, sep=sep)
    header = f"attachment; filename=iptv_{len(entries)}.txt"
    return PlainTextResponse(content=content, media_type="text/plain",
                            headers={"Content-Disposition": header})

@router.get("/export/full", summary="一键搜索→测速→导出 M3U")
async def export_full(
    ip_version: str = Query(default="ipv4"),
    source_type: str = Query(default="all"),
    concurrency: int = Query(default=20),
    timeout: int = Query(default=5),
    search_timeout: int = Query(default=15),
):
    channels = load_channels()
    if not channels:
        return PlainTextResponse(content="#EXTM3U\n# 频道表为空\n", media_type="audio/x-mpegurl")
    result = await run_full_pipeline(channels=channels, source_type=source_type,
                                     ip_version=ip_version, concurrency=concurrency,
                                     timeout=timeout, search_timeout=search_timeout)
    save_result(result["entries"])
    if not result["entries"]:
        return PlainTextResponse(content="#EXTM3U\n# 没有验证通过的频道\n", media_type="audio/x-mpegurl")
    content = gen_m3u(result["entries"])
    header = f"attachment; filename=iptv_valid_{len(result['entries'])}.m3u"
    return PlainTextResponse(content=content, media_type="audio/x-mpegurl",
                            headers={"Content-Disposition": header})

# ============ 统计 ============

@router.get("/stats", summary="当前结果统计")
async def get_stats():
    entries = load_result()
    cache = load_speed_cache()
    groups = {}
    protocols = {}
    for e in entries:
        g = e.get("group", "未分组")
        groups.setdefault(g, 0)
        groups[g] += 1
        p = e.get("protocol", "unknown")
        protocols.setdefault(p, 0)
        protocols[p] += 1
    return {"code": 0, "message": "ok", "data": {
        "total": len(entries), "groups": groups, "protocols": protocols,
        "speed_cache_size": len(cache),
    }}

@router.get("/speed/cache", summary="测速缓存")
async def get_speed_cache(limit: int = Query(default=100, ge=1, le=1000)):
    cache = load_speed_cache()
    sorted_cache = sorted(cache.items(), key=lambda x: x[1].get("response_time", 99999))
    return {"code": 0, "message": "ok",
            "data": {k: v for k, v in sorted_cache[:limit]}}

@router.delete("/speed/cache", summary="清除测速缓存")
async def clear_speed_cache():
    import os
    f = os.path.join(DATA_DIR, "speed_cache.json")
    if os.path.exists(f):
        os.remove(f)
    return {"code": 0, "message": "已清除", "data": None}
