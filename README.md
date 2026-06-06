# IPTV 聚合器

<div align="center">

**一个轻量级的 IPTV 频道聚合与管理平台**

支持多源聚合、智能搜索、M3U/M3U8 导出，专为 NAS 部署优化。

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green?logo=fastapi)
![License](https://img.shields.io/badge/License-MIT-yellow)
![ARM64](https://img.shields.io/badge/ARM64-Supported-orange)

</div>

## ✨ 特性

- 📡 **多源聚合** — 支持从多个 M3U/M3U8 URL 或本地文件聚合频道
- 🔍 **智能搜索** — 支持频道名称搜索和分类过滤
- 📤 **灵活导出** — 导出 M3U/M3U8/JSON 格式，兼容 VLC、Kodi、TiviMate 等播放器
- ⏰ **定时同步** — 自动定时同步 IPTV 源，保持频道列表最新
- 🐳 **Docker 部署** — 一键 Docker 部署，支持 x86_64 和 ARM64
- 🏠 **NAS 友好** — 完美适配飞牛 NAS (fnOS) 和群晖 NAS
- 📦 **轻量低耗** — 内存占用 < 128MB，适合 NAS 长期运行

## 🏗️ 架构

```
iptv-aggregator/
├── backend/                    # Python 后端（FastAPI）
│   ├── app/
│   │   ├── main.py             # 应用入口
│   │   ├── api/                # API 路由
│   │   │   ├── channels.py     # 频道管理
│   │   │   ├── sources.py      # 源管理
│   │   │   ├── search.py       # 搜索
│   │   │   └── export.py       # 导出
│   │   ├── models/             # 数据模型
│   │   │   └── database.py     # SQLAlchemy 模型
│   │   └── services/           # 业务服务
│   │       └── scheduler.py    # 定时任务
│   └── requirements.txt        # Python 依赖
├── frontend/                   # 前端（待实现）
│   └── dist/                   # 构建输出
├── Dockerfile                  # Docker 多阶段构建
├── docker-compose.yml          # Docker Compose 配置
├── docker-compose.fnos.yml     # 飞牛 NAS 专用配置
└── README.md                   # 本文件
```

## 🚀 快速开始

### docker compose (推荐)

```bash
# 克隆项目
git clone <repository-url>
cd iptv-aggregator

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f
```

服务启动后访问 `http://<服务器IP>:8080`

### Docker 单容器运行

```bash
docker run -d \
  --name iptv-aggregator \
  -p 8080:8080 \
  -v ./data:/data \
  -e DB_PATH=/data/iptv.db \
  --restart unless-stopped \
  iptv-aggregator:latest
```

### 飞牛 NAS 部署

在飞牛 NAS 终端执行：

```bash
cd /vol1/docker/iptv-aggregator
docker compose -f docker-compose.fnos.yml up -d
```

## 🔌 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/channels` | 获取频道列表 |
| POST | `/api/channels` | 添加频道 |
| DELETE | `/api/channels/{id}` | 删除频道 |
| GET | `/api/sources` | 获取源列表 |
| POST | `/api/sources` | 添加源 |
| POST | `/api/sources/{id}/sync` | 同步源 |
| GET | `/api/search` | 搜索频道 |
| GET | `/api/search/categories` | 获取分类 |
| GET | `/api/export/m3u` | 导出 M3U |
| GET | `/api/export/m3u8` | 导出 M3U8 |
| GET | `/api/export/json` | 导出 JSON |

API 文档（Swagger UI）：`http://<服务器IP>:8080/docs`

## ⚙️ 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_PATH` | `/data/iptv.db` | SQLite 数据库路径 |
| `TZ` | `Asia/Shanghai` | 时区（飞牛 NAS） |

### 端口

- **8080** — Web UI 和 API 服务

### 数据持久化

- `/data` 目录存储 SQLite 数据库 (`iptv.db`)
- 建议通过 Docker Volume 挂载到宿主机

## 🏗️ Docker 镜像构建

Dockerfile 使用多阶段构建：

1. **阶段 1** (`frontend-builder`) — 使用 Node.js 构建前端
2. **阶段 2** (`backend-runtime`) — 基于 `python:3.11-slim` 部署后端

支持多架构（`linux/amd64`, `linux/arm64`），适配飞牛/群晖 NAS。

```bash
# 构建镜像
docker build -t iptv-aggregator:latest .

# 多架构构建（需要 buildx）
docker buildx build --platform linux/amd64,linux/arm64 -t iptv-aggregator:latest .
```

## 📋 开发

### 后端开发

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 运行开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 前端开发

```bash
cd frontend
npm install
npm run dev      # 开发模式
npm run build    # 构建（输出到 dist/）
```

## 🏗️ 系统要求

- **CPU**: x86_64 或 ARM64（1 核即可）
- **内存**: 最低 128MB，推荐 256MB+
- **磁盘**: 至少 100MB 可用空间
- **Docker**: 20.10+ （Docker Compose V2）

## 📄 License

MIT License
