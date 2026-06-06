"""数据库管理 - 引擎、会话、初始化"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

DB_PATH = os.environ.get("DB_PATH", "/data/iptv.db")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """创建所有表（如果不存在）"""
    from app.models.models import Base
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DBContext:
    """同步上下文管理器，用于非请求上下文（如定时任务）"""
    def __init__(self):
        self.db = SessionLocal()
    def __enter__(self) -> Session:
        return self.db
    def __exit__(self, *args):
        self.db.close()


def get_db_context():
    return DBContext()
