"""
IPTV 聚合器 - FastAPI 主应用入口
=====================================
提供 IPTV 频道聚合、搜索、导出等 API 服务。
支持 ARM64 架构（飞牛/群晖 NAS 部署）。
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ============================================================
# 数据库初始化
# ============================================================

from app.models.database import init_db


# ============================================================
# 应用生命周期管理
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期钩子。"""
    # 启动时初始化数据库
    init_db()
    print("[lifespan] 🚀 IPTV 聚合器启动完成")
    # 可以在这里启动后台定时任务
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
        print("[lifespan] ⏰ 定时任务调度器已启动")
    except ImportError:
        print("[lifespan] ⚠️  定时任务模块未找到，跳过")

    yield

    # 关闭时清理资源
    try:
        from app.services.scheduler import stop_scheduler
        stop_scheduler()
    except ImportError:
        pass
    print("[lifespan] 👋 IPTV 聚合器已关闭")


# ============================================================
# 创建 FastAPI 实例
# ============================================================

app = FastAPI(
    title="IPTV 聚合器",
    description="IPTV 频道聚合与管理平台 — 支持多源聚合、智能搜索、M3U/M3U8 导出",
    version="1.0.0",
    lifespan=lifespan,
)

# ============================================================
# CORS 中间件（允许所有来源）
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],          # 允许所有 HTTP 方法
    allow_headers=["*"],          # 允许所有请求头
)

# ============================================================
# 注册 API 路由
# ============================================================

from app.api import channels, sources, search, export

app.include_router(channels.router, prefix="/api/channels", tags=["频道管理"])
app.include_router(sources.router, prefix="/api/sources", tags=["源管理"])
app.include_router(search.router, prefix="/api/search", tags=["搜索"])
app.include_router(export.router, prefix="/api/export", tags=["导出"])

# ============================================================
# 健康检查端点
# ============================================================

@app.get("/api/health", tags=["系统"])
async def health_check():
    """
    健康检查接口。
    返回服务状态，可用于 Docker 健康检查和监控。
    """
    return {
        "status": "ok",
        "service": "iptv-aggregator",
        "version": "1.0.0",
    }


# ============================================================
# 静态文件服务（前端 dist）
# ============================================================

# 前端 dist 目录路径（相对于 backend 目录）
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if frontend_dist.is_dir() and (frontend_dist / "assets").is_dir():
    # 挂载静态资源目录
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """为所有未匹配的路由提供前端 SPA 入口文件。"""
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "前端尚未构建，请先运行 npm run build"}

    print(f"[static] ✅ 前端静态文件已挂载: {frontend_dist}")
else:
    print(f"[static] ⚠️  前端 dist 目录不存在: {frontend_dist}")
    print("[static]    请在前端目录运行 'npm run build' 构建后再部署")

    @app.get("/", include_in_schema=False)
    async def root():
        """根路径默认响应（前端未构建时）。"""
        return {
            "message": "IPTV 聚合器 API 服务正在运行",
            "docs": "/docs",
            "health": "/api/health",
        }
