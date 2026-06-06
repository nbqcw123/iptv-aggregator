"""IPTV 导出 API"""
import asyncio
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from app.models.database import get_db_context
from app.services.channel_service import get_channels, export_channels_m3u
from app.core.searcher import search_all

router = APIRouter()


@router.get("/m3u", summary="导出 M3U")
async def export_m3u(
    region: Optional[str] = Query(None, description="地区筛选"),
    operator: Optional[str] = Query(None, description="运营商筛选"),
    group: Optional[str] = Query(None, description="分组筛选"),
):
    """导出 M3U 播放列表（支持筛选）"""
    with get_db_context() as db:
        m3u_content = export_channels_m3u(db, region=region, operator=operator, group=group)
    return PlainTextResponse(
        content=m3u_content,
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": "attachment; filename=iptv.m3u"},
    )


@router.get("/m3u/auto", summary="自动搜索并导出 M3U")
async def export_m3u_auto():
    """自动搜索所有内置源，验证后导出有效频道的 M3U"""
    result = await search_all(max_sources=50, timeout=15, concurrency=5)
    from app.core.m3u import M3UGenerator
    channels = result.get("channels", [])
    m3u_content = M3UGenerator.generate(channels) if channels else "#EXTM3U\n"
    return PlainTextResponse(
        content=m3u_content,
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": "attachment; filename=iptv_auto.m3u"},
    )


@router.get("/txt", summary="导出 TXT")
async def export_txt(
    region: Optional[str] = Query(None),
    operator: Optional[str] = Query(None),
    group: Optional[str] = Query(None),
):
    """导出 TXT 格式（频道名,URL）"""
    with get_db_context() as db:
        result = get_channels(db, region=region, operator=operator, group=group, page=1, page_size=10000)
        lines = ["# IPTV 频道列表 - TXT 格式\n"]
        for ch in result["items"]:
            if ch.name and ch.url:
                lines.append(f"{ch.name},{ch.url}")
    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=iptv.txt"},
    )


@router.get("/json", summary="导出 JSON")
async def export_json(
    region: Optional[str] = Query(None),
    operator: Optional[str] = Query(None),
    group: Optional[str] = Query(None),
):
    """导出 JSON 格式"""
    with get_db_context() as db:
        result = get_channels(db, region=region, operator=operator, group=group, page=1, page_size=10000)
        channels = []
        for ch in result["items"]:
            channels.append({
                "name": ch.name, "url": ch.url,
                "group_title": ch.group_title,
                "tvg_id": ch.tvg_id, "tvg_name": ch.tvg_name,
                "tvg_logo": ch.tvg_logo,
                "region": ch.region, "operator": ch.operator,
            })
    return JSONResponse(content={"code": 0, "message": "ok", "data": {
        "total": len(channels), "channels": channels
    }})
