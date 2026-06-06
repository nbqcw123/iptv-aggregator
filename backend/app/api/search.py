"""IPTV 搜索 API"""
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from app.core.searcher import search_all, search_custom, get_builtin_sources, add_builtin_source

router = APIRouter()


class AutoSearchRequest(BaseModel):
    max_sources: int = Field(default=50, ge=1, le=200, description="最大搜索源数")
    timeout: int = Field(default=15, ge=5, le=60, description="超时(秒)")
    concurrency: int = Field(default=5, ge=1, le=20, description="并发数")


class CustomSearchRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, description="自定义 M3U URL 列表")
    timeout: int = Field(default=15, ge=5, le=60)
    concurrency: int = Field(default=5, ge=1, le=20)


@router.post("/auto", summary="自动搜索所有内置源")
async def auto_search(data: AutoSearchRequest):
    """自动搜索所有内置 IPTV 源，返回聚合结果"""
    result = await search_all(
        max_sources=data.max_sources,
        timeout=data.timeout,
        concurrency=data.concurrency,
    )
    # 序列化 channels
    channels_data = []
    for ch in result.get("channels", []):
        channels_data.append({
            "name": ch.name, "url": ch.url,
            "group_title": ch.group_title,
            "tvg_id": ch.tvg_id, "tvg_name": ch.tvg_name,
            "tvg_logo": ch.tvg_logo,
        })
    return {"code": 0, "message": "ok", "data": {
        "total": result["total"],
        "valid": result["valid"],
        "total_channels": result["total_channels"],
        "valid_channels": result["valid_channels"],
        "sources": result["sources"],
        "channels": channels_data,
    }}


@router.post("/custom", summary="搜索自定义 URL")
async def custom_search(data: CustomSearchRequest):
    """搜索用户指定的 M3U URL 列表"""
    result = await search_custom(
        urls=data.urls,
        timeout=data.timeout,
        concurrency=data.concurrency,
    )
    channels_data = []
    for ch in result.get("channels", []):
        channels_data.append({
            "name": ch.name, "url": ch.url,
            "group_title": ch.group_title,
        })
    return {"code": 0, "message": "ok", "data": {
        "total": result["total"],
        "valid": result["valid"],
        "valid_channels": result["valid_channels"],
        "sources": result["sources"],
        "channels": channels_data,
    }}


@router.get("/builtins", summary="获取内置源列表")
async def list_builtins():
    """获取所有内置 IPTV 源"""
    sources = get_builtin_sources()
    return {"code": 0, "message": "ok", "data": sources}


@router.post("/builtins/add", summary="添加内置源")
async def add_builtin(
    key: str = Query(..., description="唯一标识"),
    name: str = Query(..., description="源名称"),
    url: str = Query(..., description="M3U URL"),
    region: str = Query(default="", description="地区"),
    operator: str = Query(default="", description="运营商"),
):
    """动态添加内置 IPTV 源"""
    add_builtin_source(key, name, url, region, operator)
    return {"code": 0, "message": "添加成功", "data": None}
