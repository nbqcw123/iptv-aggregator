"""IPTV 源管理 API"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.models.database import get_db
from app.services.source_service import (
    get_sources, create_source, update_source, delete_source,
    validate_source_db, validate_all_sources, import_channels_from_source, get_source_channels
)

router = APIRouter()


class SourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="源名称")
    url: str = Field(..., min_length=1, description="M3U/M3U8 URL")
    source_type: str = Field(default="auto", description="类型: auto/url/file")
    region: str = Field(default="", description="地区")
    operator: str = Field(default="", description="运营商")
    priority: int = Field(default=50, ge=0, le=100, description="优先级")
    check_interval: int = Field(default=3600, ge=60, description="检查间隔(秒)")
    timeout: int = Field(default=10, ge=1, le=60, description="超时(秒)")
    headers: str = Field(default="", description="自定义HTTP头(JSON)")
    remark: str = Field(default="", description="备注")


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    source_type: Optional[str] = None
    region: Optional[str] = None
    operator: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    check_interval: Optional[int] = None
    timeout: Optional[int] = None
    headers: Optional[str] = None
    remark: Optional[str] = None


@router.get("/", summary="获取源列表")
async def list_sources(
    region: Optional[str] = Query(None),
    operator: Optional[str] = Query(None),
    is_valid: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """获取 IPTV 源列表"""
    result = get_sources(db, region=region, operator=operator,
                         is_valid=is_valid, page=page, page_size=page_size)
    items = []
    for s in result["items"]:
        items.append({
            "id": s.id, "name": s.name, "url": s.url,
            "source_type": s.source_type, "region": s.region,
            "operator": s.operator, "priority": s.priority,
            "is_active": s.is_active, "is_valid": s.is_valid,
            "channel_count": s.channel_count, "fail_count": s.fail_count,
            "last_check": str(s.last_check) if s.last_check else None,
            "last_success": str(s.last_success) if s.last_success else None,
            "remark": s.remark,
        })
    return {"code": 0, "message": "ok", "data": {"list": items, "total": result["total"]}}


@router.post("/", summary="添加源")
async def add_source(data: SourceCreate, db: Session = Depends(get_db)):
    """添加新的 IPTV 源"""
    src = create_source(db, data.model_dump())
    return {"code": 0, "message": "添加成功", "data": {"id": src.id}}


@router.get("/{source_id}", summary="获取源详情")
async def get_source_detail(source_id: int, db: Session = Depends(get_db)):
    """获取单个源详情"""
    src = get_sources(db, page=1, page_size=1)
    # 直接查
    from app.models.models import Source
    src = db.query(Source).filter(Source.id == source_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="源不存在")
    return {"code": 0, "message": "ok", "data": {
        "id": src.id, "name": src.name, "url": src.url,
        "source_type": src.source_type, "region": src.region,
        "operator": src.operator, "priority": src.priority,
        "is_active": src.is_active, "is_valid": src.is_valid,
        "channel_count": src.channel_count, "fail_count": src.fail_count,
    }}


@router.put("/{source_id}", summary="更新源")
async def update_source_api(source_id: int, data: SourceUpdate, db: Session = Depends(get_db)):
    """更新源配置"""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    src = update_source(db, source_id, update_data)
    if not src:
        raise HTTPException(status_code=404, detail="源不存在")
    return {"code": 0, "message": "更新成功", "data": {"id": src.id}}


@router.delete("/{source_id}", summary="删除源")
async def delete_source_api(source_id: int, db: Session = Depends(get_db)):
    """删除源"""
    ok = delete_source(db, source_id)
    if not ok:
        raise HTTPException(status_code=404, detail="源不存在")
    return {"code": 0, "message": "删除成功", "data": None}


@router.get("/{source_id}/channels", summary="获取源的频道")
async def get_source_channels_api(source_id: int, db: Session = Depends(get_db)):
    """获取某个源下的所有频道"""
    channels = get_source_channels(db, source_id)
    return {"code": 0, "message": "ok", "data": channels}


@router.post("/{source_id}/validate", summary="验证单个源")
async def validate_source_api(source_id: int, db: Session = Depends(get_db)):
    """验证单个 IPTV 源是否可用"""
    result = await validate_source_db(db, source_id)
    return {"code": 0, "message": "ok", "data": result}


@router.post("/validate/all", summary="验证所有源")
async def validate_all_sources_api(db: Session = Depends(get_db)):
    """验证所有启用的 IPTV 源"""
    result = await validate_all_sources(db)
    return {"code": 0, "message": "ok", "data": result}


@router.post("/{source_id}/import", summary="从源导入频道")
async def import_from_source(source_id: int, db: Session = Depends(get_db)):
    """从 IPTV 源 URL 获取 M3U 并导入频道"""
    result = await import_channels_from_source(db, source_id)
    return {"code": 0, "message": f"导入完成: {result.get('imported', 0)} 条新增", "data": result}
