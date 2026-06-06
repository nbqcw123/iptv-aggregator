"""数据库初始化 — SQLite，持久化频道表和结果"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.expanduser("~"), ".iptv-data"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "iptv.db"))
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()

def init_db():
    Base.metadata.create_all(engine)
