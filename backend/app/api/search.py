"""IPTV 搜索与导出 API"""
import asyncio
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from app.core.searcher import search, validate, check_url, gen_m3u, gen_txt, Entry

router = APIRouter()

# 内存缓存
_cache: dict = {"entries": [], "valid": [], "stats": {}}


class SearchReq(BaseModel):
    source_type: str = Field(default="all", description="multicast/hotel/all")
    custom_urls: list[str] = Field(default=[])
    timeout: int = Field(default=15, ge=5, le=60)
    concurrency: int = Field(default=5, ge=1, le=20)


class ValidateReq(BaseModel):
    concurrency: int = Field(default=20, ge=1, le=100)
    timeout: int = Field(default=5, ge=2, le=30)


def _to_dict(entries: list[Entry]) -> list[dict]:
    return [{"name": e.name, "url": e.url, "group": e.group,
             "source_name": e.source_name, "source_type": e.source_type,
             "response_time": e.response_time} for e in entries]


# ============ 搜索 ============

@router.post("/search", summary="搜索 IPTV 源")
async def do_search(req: SearchReq):
    entries = await search(source_type=req.source_type, custom_urls=req.custom_urls or None,
                           timeout=req.timeout, concurrency=req.concurrency)
    _cache["entries"] = entries
    _cache["valid"] = []
    _cache["stats"] = {"total": len(entries), "valid": 0, "invalid": 0}
    return {"code": 0, "message": f"搜索完成，发现 {len(entries)} 个地址（去重后）",
            "data": {"total": len(entries), "entries": _to_dict(entries[:200])}}


# ============ 验证 ============

@router.post("/validate", summary="验证所有地址可用性")
async def do_validate(req: ValidateReq):
    entries = _cache.get("entries", [])
    if not entries:
        return {"code": 1, "message": "请先搜索源", "data": None}
    valid = await validate(entries, concurrency=req.concurrency, timeout=req.timeout)
    _cache["valid"] = valid
    _cache["stats"] = {"total": len(entries), "valid": len(valid), "invalid": len(entries) - len(valid)}
    return {"code": 0, "message": f"验证完成: {len(valid)}/{len(entries)} 个有效",
            "data": {"total": len(entries), "valid": len(valid),
                     "invalid": len(entries) - len(valid), "entries": _to_dict(valid[:200])}}


@router.get("/validate/single", summary="验证单个地址")
async def validate_single(url: str = Query(...)):
    r = await check_url(url)
    return {"code": 0, "message": "ok", "data": r}


# ============ 导出 ============

def _get_entries(valid_first=True):
    if valid_first and _cache.get("valid"):
        return _cache["valid"]
    return _cache.get("entries", [])


@router.get("/export/m3u", summary="导出 M3U")
async def export_m3u():
    entries = _cache.get("valid", []) or _cache.get("entries", [])
    if not entries:
        return PlainTextResponse(content="#EXTM3U\n", media_type="audio/x-mpegurl")
    content = gen_m3u(entries)
    header = f"attachment; filename=iptv_{len(entries)}.m3u"
    return PlainTextResponse(content=content, media_type="audio/x-mpegurl",
                            headers={"Content-Disposition": header})


@router.get("/export/txt", summary="导出 TXT")
async def export_txt(sep: str = Query(default=",")):
    entries = _cache.get("valid", []) or _cache.get("entries", [])
    if not entries:
        return PlainTextResponse(content="", media_type="text/plain")
    content = gen_txt(entries, sep=sep)
    header = f"attachment; filename=iptv_{len(entries)}.txt"
    return PlainTextResponse(content=content, media_type="text/plain",
                            headers={"Content-Disposition": header})


@router.get("/export/m3u/full", summary="搜索→验证→导出 M3U（完整流程）")
async def export_m3u_full(
    source_type: str = Query(default="all"),
    timeout: int = Query(default=5, ge=2, le=15),
    concurrency: int = Query(default=20, ge=1, le=100),
):
    entries = await search(source_type=source_type, timeout=15, concurrency=5)
    if not entries:
        return PlainTextResponse(content="#EXTM3U\n", media_type="audio/x-mpegurl")
    valid = await validate(entries, concurrency=concurrency, timeout=timeout)
    _cache["entries"] = entries
    _cache["valid"] = valid
    if not valid:
        return PlainTextResponse(content="#EXTM3U\n# 没有验证通过的频道\n", media_type="audio/x-mpegurl")
    content = gen_m3u(valid)
    header = f"attachment; filename=iptv_valid_{len(valid)}.m3u"
    return PlainTextResponse(content=content, media_type="audio/x-mpegurl",
                            headers={"Content-Disposition": header})


@router.get("/export/txt/full", summary="搜索→验证→导出 TXT（完整流程）")
async def export_txt_full(
    source_type: str = Query(default="all"),
    timeout: int = Query(default=5, ge=2, le=15),
    concurrency: int = Query(default=20, ge=1, le=100),
    sep: str = Query(default=","),
):
    entries = await search(source_type=source_type, timeout=15, concurrency=5)
    if not entries:
        return PlainTextResponse(content="", media_type="text/plain")
    valid = await validate(entries, concurrency=concurrency, timeout=timeout)
    _cache["entries"] = entries
    _cache["valid"] = valid
    if not valid:
        return PlainTextResponse(content="# 没有验证通过的频道\n", media_type="text/plain")
    content = gen_txt(valid, sep=sep)
    header = f"attachment; filename=iptv_valid_{len(valid)}.txt"
    return PlainTextResponse(content=content, media_type="text/plain",
                            headers={"Content-Disposition": header})


# ============ 统计 ============

@router.get("/stats", summary="当前搜索统计")
async def get_stats():
    entries = _cache.get("entries", [])
    valid = _cache.get("valid", [])
    breakdown = {}
    for e in entries:
        t = e.source_type
        breakdown.setdefault(t, {"total": 0, "valid": 0})
        breakdown[t]["total"] += 1
    for e in valid:
        t = e.source_type
        if t in breakdown:
            breakdown[t]["valid"] += 1
    return {"code": 0, "message": "ok",
            "data": {"total_searched": len(entries), "total_valid": len(valid),
                     "total_invalid": len(entries) - len(valid), "source_breakdown": breakdown}}


# ============ 内置源列表 ============

@router.get("/sources/builtin", summary="获取内置搜索源列表")
async def list_builtins():
    from app.core.searcher import MULTICAST_SOURCES, HOTEL_SOURCES
    return {"code": 0, "message": "ok",
            "data": {"multicast": MULTICAST_SOURCES, "hotel": HOTEL_SOURCES}}


@router.post("/sources/builtin/add", summary="添加自定义搜索源")
async def add_builtin(name: str = Query(...), url: str = Query(...),
                      source_type: str = Query(default="multicast")):
    from app.core.searcher import MULTICAST_SOURCES, HOTEL_SOURCES
    target = {"name": name, "url": url}
    if source_type == "hotel":
        HOTEL_SOURCES.append(target)
    else:
        MULTICAST_SOURCES.append(target)
    return {"code": 0, "message": "添加成功", "data": None}
