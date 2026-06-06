"""频道服务层 - 提供频道 CRUD、批量操作和导出功能"""
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Channel
from app.core.m3u import M3UGenerator


def get_channels(
    db: Session,
    region: Optional[str] = None,
    operator: Optional[str] = None,
    group: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    搜索筛选频道列表，支持分页。

    Args:
        db: 数据库会话
        region: 地区筛选（模糊匹配）
        operator: 运营商筛选（模糊匹配）
        group: 分组名称筛选（模糊匹配）
        keyword: 关键词搜索（匹配频道名称、tvg_id、tvg_name）
        page: 页码（从 1 开始）
        page_size: 每页条数

    Returns:
        dict: {"items": [Channel, ...], "total": int, "page": int, "page_size": int}
    """
    query = db.query(Channel)

    if region:
        query = query.filter(Channel.region.like(f"%{region}%"))
    if operator:
        query = query.filter(Channel.operator.like(f"%{operator}%"))
    if group:
        query = query.filter(Channel.group_title.like(f"%{group}%"))
    if keyword:
        query = query.filter(
            Channel.name.like(f"%{keyword}%")
            | Channel.tvg_id.like(f"%{keyword}%")
            | Channel.tvg_name.like(f"%{keyword}%")
        )

    total = query.count()
    items = (
        query.order_by(Channel.sort_order.asc(), Channel.id.asc())
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


def get_channel(db: Session, channel_id: int) -> Optional[Channel]:
    """
    获取单个频道详情。

    Args:
        db: 数据库会话
        channel_id: 频道 ID

    Returns:
        Channel 对象，未找到时返回 None
    """
    return db.query(Channel).filter(Channel.id == channel_id).first()


def create_channel(db: Session, data: dict) -> Channel:
    """
    创建新频道。

    Args:
        db: 数据库会话
        data: 频道字段字典

    Returns:
        新创建的 Channel 对象
    """
    channel = Channel(**data)
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def update_channel(db: Session, channel_id: int, data: dict) -> Optional[Channel]:
    """
    更新频道信息。

    Args:
        db: 数据库会话
        channel_id: 频道 ID
        data: 待更新的字段字典

    Returns:
        更新后的 Channel 对象，频道不存在时返回 None
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        return None
    for key, value in data.items():
        if hasattr(channel, key):
            setattr(channel, key, value)
    db.commit()
    db.refresh(channel)
    return channel


def delete_channel(db: Session, channel_id: int) -> bool:
    """
    删除频道。

    Args:
        db: 数据库会话
        channel_id: 频道 ID

    Returns:
        是否删除成功
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        return False
    db.delete(channel)
    db.commit()
    return True


def get_groups(db: Session) -> list[str]:
    """
    获取所有不重复的分组名称。

    Args:
        db: 数据库会话

    Returns:
        分组名称列表（按字母排序）
    """
    results = (
        db.query(Channel.group_title)
        .distinct()
        .filter(Channel.group_title.isnot(None))
        .filter(Channel.group_title != "")
        .order_by(Channel.group_title.asc())
        .all()
    )
    return [r[0] for r in results]


def get_regions(db: Session) -> list[str]:
    """
    获取所有不重复的地区名称。

    Args:
        db: 数据库会话

    Returns:
        地区名称列表（按字母排序）
    """
    results = (
        db.query(Channel.region)
        .distinct()
        .filter(Channel.region.isnot(None))
        .filter(Channel.region != "")
        .order_by(Channel.region.asc())
        .all()
    )
    return [r[0] for r in results]


def get_operators(db: Session) -> list[str]:
    """
    获取所有不重复的运营商名称。

    Args:
        db: 数据库会话

    Returns:
        运营商名称列表（按字母排序）
    """
    results = (
        db.query(Channel.operator)
        .distinct()
        .filter(Channel.operator.isnot(None))
        .filter(Channel.operator != "")
        .order_by(Channel.operator.asc())
        .all()
    )
    return [r[0] for r in results]


def bulk_import_channels(db: Session, channels: list[dict]) -> dict:
    """
    批量导入频道，跳过已存在记录（按名称 + region + operator 判重）。

    Args:
        db: 数据库会话
        channels: 频道字典列表，每个字典至少包含 name 和 url 字段（url 存入 tvg_id）

    Returns:
        dict: {"imported": int, "skipped": int, "total": int}
    """
    imported = 0
    skipped = 0

    for ch_data in channels:
        name = ch_data.get("name", "")
        if not name:
            skipped += 1
            continue

        # 检查是否已存在（同名 + 同地区 + 同运营商）
        existing = (
            db.query(Channel)
            .filter(
                Channel.name == name,
                Channel.region == ch_data.get("region", ""),
                Channel.operator == ch_data.get("operator", ""),
            )
            .first()
        )
        if existing:
            skipped += 1
            continue

        channel = Channel(**ch_data)
        db.add(channel)
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped, "total": len(channels)}


def export_channels_m3u(
    db: Session,
    region: Optional[str] = None,
    operator: Optional[str] = None,
    group: Optional[str] = None,
) -> str:
    """
    导出频道为 M3U 格式字符串。

    Args:
        db: 数据库会话
        region: 地区筛选
        operator: 运营商筛选
        group: 分组筛选

    Returns:
        M3U 格式文本
    """
    query = db.query(Channel).filter(Channel.is_active == True)  # noqa: E712

    if region:
        query = query.filter(Channel.region.like(f"%{region}%"))
    if operator:
        query = query.filter(Channel.operator.like(f"%{operator}%"))
    if group:
        query = query.filter(Channel.group_title.like(f"%{group}%"))

    channels = query.order_by(Channel.id.asc()).all()

    return M3UGenerator.generate_simple(
        [
            {
                "name": ch.name,
                "url": ch.url or ch.tvg_id or "",
                "group_title": ch.group_title,
                "tvg_id": ch.tvg_id,
                "tvg_name": ch.tvg_name,
                "tvg_logo": ch.tvg_logo,
            }
            for ch in channels
            if ch.name
        ]
    )
