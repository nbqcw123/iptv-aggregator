"""IPTV 聚合器 v3 — FastAPI 主入口"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

async def lifespan(app: FastAPI):
    print("✅ 服务启动")
    from app.api.search import start_scheduler
    start_scheduler()
    yield
    from app.api.search import stop_scheduler
    stop_scheduler()

app = FastAPI(title="IPTV 聚合器 v4", version="4.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

from app.api.search import router as search_router
from app.api.sources import router as sources_router
from app.api.admin import router as admin_router
app.include_router(search_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
app.include_router(admin_router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "iptv-aggregator", "version": "3.0.0"}

# 前端静态文件
frontend_dist = Path(__file__).resolve().parent / "static"
if frontend_dist.is_dir() and (frontend_dist / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    
    # 后台管理页面
    admin_html = frontend_dist / "admin.html"
    if admin_html.exists():
        @app.get("/admin", include_in_schema=False)
        async def admin_page():
            return FileResponse(str(admin_html))
    
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve(full_path: str):
        # API 请求已经在前面匹配了，这里只处理前端路由
        idx = frontend_dist / "index.html"
        if idx.exists(): return FileResponse(str(idx))
        return {"message": "前端未构建"}
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {"message": "IPTV 聚合器 API v3", "docs": "/docs"}
