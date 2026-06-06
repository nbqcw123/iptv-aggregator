"""数据模型"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Channel(Base):
    """频道实体"""
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)          # 频道名称
    url = Column(Text, default="")                                    # 播放地址（M3U stream URL）
    group_title = Column(String(255), default="未分组")              # 分组（央视/卫视/地方/国际等）
    tvg_id = Column(String(255), default="")                         # EPG ID
    tvg_name = Column(String(255), default="")                       # EPG 名称
    tvg_logo = Column(String(500), default="")                       # Logo URL
    region = Column(String(100), default="", index=True)             # 地区
    operator = Column(String(100), default="", index=True)           # 运营商
    language = Column(String(50), default="zh")                      # 语言
    is_active = Column(Boolean, default=True)                        # 是否有效
    sort_order = Column(Integer, default=0)                          # 排序
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Source(Base):
    """IPTV 源"""
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)                       # 源名称
    url = Column(Text, nullable=False)                                # 源 URL（M3U/M3U8 地址）
    source_type = Column(String(50), default="auto")                 # 类型：auto/url/file/file_upload
    region = Column(String(100), default="", index=True)             # 地区
    operator = Column(String(100), default="", index=True)           # 运营商
    priority = Column(Integer, default=50)                           # 优先级（越高越优先）
    is_active = Column(Boolean, default=True)                        # 是否启用
    is_valid = Column(Boolean, default=True)                         # 最近一次验证是否有效
    check_interval = Column(Integer, default=3600)                   # 检查间隔（秒）
    last_check = Column(DateTime, nullable=True)                     # 最近验证时间
    last_success = Column(DateTime, nullable=True)                   # 最近成功时间
    channel_count = Column(Integer, default=0)                       # 最近解析频道数
    fail_count = Column(Integer, default=0)                          # 连续失败次数
    timeout = Column(Integer, default=10)                            # 请求超时（秒）
    headers = Column(Text, default="")                               # 自定义 HTTP 头（JSON）
    remark = Column(Text, default="")                                # 备注
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("url", name="uq_source_url"),
    )


class SourceChannel(Base):
    """源-频道关联（同一频道可能有多个源）"""
    __tablename__ = "source_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, nullable=False, index=True)
    channel_id = Column(Integer, nullable=False, index=True)
    stream_url = Column(Text, nullable=False)                        # 实际播放地址
    quality = Column(String(50), default="")                         # 画质（SD/HD/4K）
    is_working = Column(Boolean, default=True)                       # 最近是否可用
    response_time = Column(Integer, default=0)                       # 响应时间（ms）
    last_check = Column(DateTime, nullable=True)
    priority = Column(Integer, default=50)                           # 该源中此频道的优先级
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("source_id", "channel_id", "stream_url", name="uq_source_channel_url"),
   )


class SearchTask(Base):
    """搜索任务"""
    __tablename__ = "search_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    task_type = Column(String(50), default="auto")                   # auto/custom
    cron_expr = Column(String(100), default="0 */6 * * *")           # Cron 表达式
    max_sources = Column(Integer, default=100)                        # 最大搜索源数
    search_timeout = Column(Integer, default=30)                      # 单次搜索超时
    auto_update = Column(Boolean, default=True)                       # 是否自动更新
    is_running = Column(Boolean, default=False)                       # 是否正在运行
    is_active = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    last_result = Column(Text, default="")                            # 最近执行结果摘要
    run_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Region(Base):
    """地区"""
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)          # 地区名称
    code = Column(String(20), default="")                            # 地区编码
    sort_order = Column(Integer, default=0)


class Operator(Base):
    """运营商"""
    __tablename__ = "operators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)          # 运营商名称
    code = Column(String(20), default="")
    sort_order = Column(Integer, default=0)


class SearchLog(Base):
    """搜索日志"""
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, nullable=True, index=True)
    action = Column(String(50), nullable=False)                      # search/check/update/export
    status = Column(String(20), default="running")                   # running/success/failed
    detail = Column(Text, default="")
    sources_found = Column(Integer, default=0)
    channels_found = Column(Integer, default=0)
    channels_valid = Column(Integer, default=0)
    duration = Column(Integer, default=0)                            # 执行时长（秒）
    created_at = Column(DateTime, default=datetime.utcnow)
