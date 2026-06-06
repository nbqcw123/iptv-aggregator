"""
IPTV 聚合器 - FastAPI 主应用
===============================
核心流程：搜索(组播源+酒店源) → 验证可用性 → 去重 → 导出 M3U + TXT
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


def init_db():
    """初始化数据库（当前版本使用内存缓存，不需要 DB）"""
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("🚀 IPTV 聚合器启动完成")
    yield
    print("👋 IPTV 聚合器已关闭")


app = FastAPI(
    title="IPTV 聚合器",
    description="IPTV 组播源+酒店源搜索聚合 → 验证可用性 → 导出 M3U+TXT",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.api import search
app.include_router(search.router, prefix="/api", tags=["IPTV 搜索导出"])


# 健康检查
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "iptv-aggregator", "version": "2.0.0"}


# 前端静态文件
frontend_dist = Path(__file__).resolve().parent / "app" / "static"

if frontend_dist.is_dir() and (frontend_dist / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/")
    async def serve_spa():
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "IPTV 聚合器 API 运行中", "docs": "/docs"}

    print(f"[static] 前端已挂载: {frontend_dist}")
else:
    @app.get("/")
    async def root():
        return {"message": "IPTV 聚合器 API 服务运行中", "docs": "/docs", "health": "/api/health"}
    print(f"[static] 前端未构建: {frontend_dist}")
