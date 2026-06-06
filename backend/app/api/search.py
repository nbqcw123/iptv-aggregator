"""IPTV 搜索与导出 API"""
import asyncio
import os
import json
from typing import Optional
from fastapi import APIRouter, Query, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel, Field
from app.core.searcher import (
    search_sources, validate_entries, generate_m3u, generate_txt,
    PlaylistEntry, check_url
)

router = APIRouter()

# 内存中保存最近搜索结果（生产环境应入 DB）
_search_cache: dict = {"entries": [], "valid_entries": [], "stats": {}}


class SearchRequest(BaseModel):
    source_type: str = Field(default="all", description="multicast/hotel/all")
    custom_urls: list[str] = Field(default=[], description="自定义 URL 列表")
    timeout: int = Field(default=15, ge=5, le=60)
    concurrency: int = Field(default=5, ge=1, le=20)


class ValidateRequest(BaseModel):
    concurrency: int = Field(default=20, ge=1, le=100)
    timeout: int = Field(default=5, ge=2, le=30)


# ============ 搜索 ============

@router.post("/search", summary="搜索 IPTV 源")
async def do_search(req: SearchRequest):
    """
    从网上搜索组播源和/或酒店源。
    source_type: multicast(组播源) | hotel(酒店源) | all(全部)
    """
    entries = await search_sources(
        urls=req.custom_urls or None,
        source_type=req.source_type,
        timeout=req.timeout,
        concurrency=req.concurrency,
    )
    _search_cache["entries"] = entries
    _search_cache["valid_entries"] = []
    _search_cache["stats"] = {
        "total": len(entries),
        "valid": 0,
        "invalid": 0,
    }

    return {
        "code": 0,
        "message": f"搜索完成，发现 {len(entries)} 个播放地址（去重后）",
        "data": {
            "total": len(entries),
            "entries": [
                {"name": e.name, "url": e.url, "group": e.group,
                 "source_name": e.source_name, "source_type": e.source_type}
                for e in entries[:200]  # 最多返回 200 条预览
            ],
            "preview_count": min(len(entries), 200),
        },
    }


# ============ 验证 ============

@router.post("/validate", summary="验证所有地址可用性")
async def do_validate(req: ValidateRequest):
    """
    并发验证搜索到的所有播放地址，去掉不可用的。
    返回验证后的有效地址列表。
    """
    entries = _search_cache.get("entries", [])
    if not entries:
        return {"code": 1, "message": "请先搜索源", "data": None}

    total = len(entries)
    checked = [0]
    valid_count = [0]

    def progress(current, total):
        checked[0] = current

    valid_entries = await validate_entries(
        entries,
        concurrency=req.concurrency,
        timeout=req.timeout,
        progress_callback=progress,
    )

    _search_cache["valid_entries"] = valid_entries
    _search_cache["stats"] = {
        "total": total,
        "valid": len(valid_entries),
        "invalid": total - len(valid_entries),
    }

    return {
        "code": 0,
        "message": f"验证完成: {len(valid_entries)}/{total} 个有效",
        "data": {
            "total": total,
            "valid": len(valid_entries),
            "invalid": total - len(valid_entries),
            "entries": [
                {"name": e.name, "url": e.url, "group": e.group,
                 "source_type": e.source_type, "response_time": e.response_time}
                for e in valid_entries[:200]
            ],
        },
    }


@router.get("/validate/single", summary="验证单个地址")
async def validate_single(url: str = Query(..., description="播放地址")):
    """验证单个播放地址是否可用"""
    result = await check_url(url)
    return {"code": 0, "message": "ok", "data": result}


# ============ 导出 ============

@router.get("/export/m3u", summary="导出 M3U (验证后)")
async def export_m3u():
    """导出验证后的有效频道为 M3U 格式"""
    entries = _search_cache.get("valid_entries", [])
    if not entries:
        # 如果没有验证过，用搜索到的全部
        entries = _search_cache.get("entries", [])
    if not entries:
        return PlainTextResponse(content="#EXTM3U\n", media_type="audio/x-mpegurl")

    content = generate_m3u(entries)
    return PlainTextResponse(
        content=content,
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": "attachment; filename=iptv.m3u"},
    )


@router.get("/export/txt", summary="导出 TXT (验证后)")
async def export_txt(sep: str = Query(default=",", description="分隔符: , 或 |")):
    """导出验证后的有效频道为 TXT 格式 (频道名,URL)"""
    entries = _search_cache.get("valid_entries", [])
    if not entries:
        entries = _search_cache.get("entries", [])
    if not entries:
        return PlainTextResponse(content="", media_type="text/plain")

    fmt = f"name{sep}url"
    content = generate_txt(entries, format_type=fmt)
    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=iptv.txt"},
    )


@router.get("/export/m3u/search", summary="搜索并直接导出 M3U")
async def export_m3u_direct(
    source_type: str = Query(default="all"),
    timeout: int = Query(default=15),
):
    """搜索 → 合并去重 → 导出 M3U（不验证）"""
    entries = await search_sources(source_type=source_type, timeout=timeout)
    if not entries:
        return PlainTextResponse(content="#EXTM3U\n", media_type="audio/x-mpegurl")
    content = generate_m3u(entries)
    return PlainTextResponse(
        content=content,
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": "attachment; filename=iptv_search.m3u"},
    )


@router.get("/export/m3u/full", summary="搜索→验证→导出 M3U（完整流程）")
async def export_m3u_full(
    source_type: str = Query(default="all"),
    timeout: int = Query(default=5),
    concurrency: int = Query(default=20),
):
    """
    完整流程：搜索 → 验证可用性 → 去重 → 导出 M3U
    只包含验证通过的地址
    """
    # 1. 搜索
    entries = await search_sources(source_type=source_type, timeout=15)
    if not entries:
        return PlainTextResponse(content="#EXTM3U\n", media_type="audio/x-mpegurl")

    # 2. 验证
    valid = await validate_entries(entries, concurrency=concurrency, timeout=timeout)

    if not valid:
        return PlainTextResponse(
            content="#EXTM3U\n# 没有验证通过的频道\n",
            media_type="audio/x-mpegurl",
        )

    # 3. 生成 M3U
    content = generate_m3u(valid)
    return PlainTextResponse(
        content=content,
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": f"attachment; filename=iptv_valid_{len(valid)}.m3u"},
    )


@router.get("/export/txt/full", summary="搜索→验证→导出 TXT（完整流程）")
async def export_txt_full(
    source_type: str = Query(default="all"),
    timeout: int = Query(default=5),
    concurrency: int = Query(default=20),
    sep: str = Query(default=","),
):
    """完整流程：搜索 → 验证 → 导出 TXT"""
    entries = await search_sources(source_type=source_type, timeout=15)
    if not entries:
        return PlainTextResponse(content="", media_type="text/plain")

    valid = await validate_entries(entries, concurrency=concurrency, timeout=timeout)
    if not valid:
        return PlainTextResponse(content="# 没有验证通过的频道\n", media_type="text/plain")

    fmt = f"name{sep}url"
    content = generate_txt(valid, format_type=fmt)
    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=iptv_valid_{len(valid)}.txt"},
    )


# ============ 统计 ============

@router.get("/stats", summary="当前搜索统计")
async def get_stats():
    """获取当前搜索/验证统计"""
    stats = _search_cache.get("stats", {})
    entries = _search_cache.get("entries", [])
    valid = _search_cache.get("valid_entries", [])

    # 按来源分组统计
    source_stats = {}
    for e in entries:
        t = e.source_type
        if t not in source_stats:
            source_stats[t] = {"total": 0, "valid": 0}
        source_stats[t]["total"] += 1
    for e in valid:
        t = e.source_type
        if t in source_stats:
            source_stats[t]["valid"] += 1

    return {"code": 0, "message": "ok", "data": {
        "total_searched": len(entries),
        "total_valid": len(valid),
        "total_invalid": len(entries) - len(valid),
        "source_breakdown": source_stats,
    }}


# ============ 内置源列表 ============

@router.get("/sources/builtin", summary="获取内置搜索源列表")
async def list_builtin_sources():
    """返回所有内置的组播源和酒店源 URL"""
    from app.core.searcher import MULTICAST_SEARCH_URLS, HOTEL_SEARCH_URLS
    return {"code": 0, "message": "ok", "data": {
        "multicast": MULTICAST_SEARCH_URLS,
        "hotel": HOTEL_SEARCH_URLS,
    }}


@router.post("/sources/builtin/add", summary="添加自定义搜索源")
async def add_builtin_source(
    name: str = Query(...),
    url: str = Query(...),
    source_type: str = Query(default="multicast"),
):
    """添加自定义搜索源 URL"""
    from app.core.searcher import MULTICAST_SEARCH_URLS, HOTEL_SEARCH_URLS
    target = {"name": name, "url": url, "type": "auto", "source_type": source_type}
    if source_type == "hotel":
        HOTEL_SEARCH_URLS.append(target)
    else:
        MULTICAST_SEARCH_URLS.append(target)
    return {"code": 0, "message": "添加成功", "data": None}
