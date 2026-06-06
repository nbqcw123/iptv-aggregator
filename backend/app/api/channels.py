"""IPTV 频道管理 API"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.models.database import get_db
from app.services.channel_service import (
    get_channels, get_channel, create_channel, update_channel, delete_channel,
    get_groups, get_regions, get_operators, bulk_import_channels, export_channels_m3u
)

router = APIRouter()


# ============ Pydantic 模型 ============

class ChannelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="频道名称")
    url: str = Field(default="", description="播放地址")
    group_title: str = Field(default="未分组", description="分组")
    tvg_id: str = Field(default="", description="EPG ID")
    tvg_name: str = Field(default="", description="EPG 名称")
    tvg_logo: str = Field(default="", description="Logo URL")
    region: str = Field(default="", description="地区")
    operator: str = Field(default="", description="运营商")
    language: str = Field(default="zh", description="语言")
    sort_order: int = Field(default=0, description="排序")


class ChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = None
    group_title: Optional[str] = None
    tvg_id: Optional[str] = None
    tvg_name: Optional[str] = None
    tvg_logo: Optional[str] = None
    region: Optional[str] = None
    operator: Optional[str] = None
    language: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class BatchDeleteRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, description="要删除的频道 ID 列表")


# ============ API 端点 ============

@router.get("/", summary="获取频道列表")
async def list_channels(
    region: Optional[str] = Query(None, description="地区筛选"),
    operator: Optional[str] = Query(None, description="运营商筛选"),
    group: Optional[str] = Query(None, description="分组筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    db: Session = Depends(get_db),
):
    """搜索筛选频道列表，支持分页"""
    result = get_channels(db, region=region, operator=operator, group=group,
                          keyword=keyword, page=page, page_size=page_size)
    # 序列化
    items = []
    for ch in result["items"]:
        items.append({
            "id": ch.id, "name": ch.name, "url": ch.url,
            "group_title": ch.group_title, "tvg_id": ch.tvg_id,
            "tvg_name": ch.tvg_name, "tvg_logo": ch.tvg_logo,
            "region": ch.region, "operator": ch.operator,
            "language": ch.language, "is_active": ch.is_active,
            "sort_order": ch.sort_order,
            "created_at": str(ch.created_at) if ch.created_at else None,
        })
    return {"code": 0, "message": "ok", "data": {"list": items, "total": result["total"],
                                                   "page": result["page"], "page_size": result["page_size"]}}


@router.get("/{channel_id}", summary="获取频道详情")
async def get_channel_detail(channel_id: int, db: Session = Depends(get_db)):
    """获取单个频道详情"""
    ch = get_channel(db, channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="频道不存在")
    return {"code": 0, "message": "ok", "data": {
        "id": ch.id, "name": ch.name, "url": ch.url,
        "group_title": ch.group_title, "tvg_id": ch.tvg_id,
        "tvg_name": ch.tvg_name, "tvg_logo": ch.tvg_logo,
        "region": ch.region, "operator": ch.operator,
        "language": ch.language, "is_active": ch.is_active,
        "sort_order": ch.sort_order,
    }}


@router.post("/", summary="创建频道")
async def add_channel(data: ChannelCreate, db: Session = Depends(get_db)):
    """手动创建单个频道"""
    ch = create_channel(db, data.model_dump())
    return {"code": 0, "message": "创建成功", "data": {"id": ch.id}}


@router.put("/{channel_id}", summary="更新频道")
async def update_channel_api(channel_id: int, data: ChannelUpdate, db: Session = Depends(get_db)):
    """更新频道信息"""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    ch = update_channel(db, channel_id, update_data)
    if not ch:
        raise HTTPException(status_code=404, detail="频道不存在")
    return {"code": 0, "message": "更新成功", "data": {"id": ch.id}}


@router.delete("/{channel_id}", summary="删除频道")
async def delete_channel_api(channel_id: int, db: Session = Depends(get_db)):
    """删除频道"""
    ok = delete_channel(db, channel_id)
    if not ok:
        raise HTTPException(status_code=404, detail="频道不存在")
    return {"code": 0, "message": "删除成功", "data": None}


@router.delete("/batch", summary="批量删除")
async def batch_delete(data: BatchDeleteRequest, db: Session = Depends(get_db)):
    """批量删除频道"""
    count = 0
    for cid in data.ids:
        if delete_channel(db, cid):
            count += 1
    return {"code": 0, "message": f"已删除 {count} 个频道", "data": {"deleted": count}}


@router.get("/meta/groups", summary="获取所有分组")
async def list_groups(db: Session = Depends(get_db)):
    """获取所有不重复的分组名称"""
    groups = get_groups(db)
    return {"code": 0, "message": "ok", "data": groups}


@router.get("/meta/regions", summary="获取所有地区")
async def list_regions(db: Session = Depends(get_db)):
    """获取所有不重复的地区名称"""
    regions = get_regions(db)
    return {"code": 0, "message": "ok", "data": regions}


@router.get("/meta/operators", summary="获取所有运营商")
async def list_operators(db: Session = Depends(get_db)):
    """获取所有不重复的运营商名称"""
    operators = get_operators(db)
    return {"code": 0, "message": "ok", "data": operators}


@router.post("/import", summary="批量导入频道")
async def import_channels(channels: list[dict], db: Session = Depends(get_db)):
    """批量导入频道（从搜索结果等）"""
    result = bulk_import_channels(db, channels)
    return {"code": 0, "message": f"导入完成: {result['imported']} 条新增, {result['skipped']} 条跳过", "data": result}
