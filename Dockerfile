# ============================================================
# IPTV 聚合器 - Docker 构建文件
# ============================================================
# 多阶段构建：
#   阶段1 - 构建前端（Node.js + npm）
#   阶段2 - 运行后端（Python 3.11 + FastAPI）
# 支持架构：linux/amd64, linux/arm64（飞牛/群晖 NAS）
# ============================================================

# ------------------------------------------
# 阶段 1: 前端构建
# ------------------------------------------
FROM node:20-alpine AS frontend-builder

# 工作目录
WORKDIR /app/frontend

# 复制前端依赖文件（利用 Docker 缓存层）
COPY frontend/package*.json ./

# 安装前端依赖
RUN npm ci --prefer-offline --no-audit --progress=false

# 复制前端源码
COPY frontend/ ./

# 构建前端（生成 dist 目录）
RUN npm run build

# ------------------------------------------
# 阶段 2: 后端运行环境
# ------------------------------------------
FROM python:3.11-slim AS backend-runtime

# 安装系统依赖（支持 ARM64 平台）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存层
COPY backend/requirements.txt ./

# 安装 Python 依赖
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# 复制后端代码
COPY backend/app/ ./app/

# 从阶段1拷贝构建好的前端文件（vite 构建到 backend/app/static）
COPY --from=frontend-builder /app/backend/app/static ./app/static

# ------------------------------------------
# 环境变量
# ------------------------------------------
# 数据库路径（镜像内默认值，可通过 -e 覆盖）
ENV DB_PATH=/data/iptv.db
ENV DATA_DIR=/data
# Python 环境优化
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ------------------------------------------
# 数据卷
# ------------------------------------------
# /data 目录用于持久化 SQLite 数据库
# 部署时建议挂载宿主机目录到 /data
VOLUME ["/data"]

# ------------------------------------------
# 暴露端口
# ------------------------------------------
EXPOSE 8080

# ------------------------------------------
# 健康检查
# ------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# ------------------------------------------
# 启动命令
# ------------------------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
