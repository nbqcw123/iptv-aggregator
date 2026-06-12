# IPTV 聚合器

IPTV 组播源 + 酒店源搜索聚合工具。搜索 → 验证可用性 → 去重 → 导出 M3U + TXT。

## 功能

- **搜索**：内置 6 个组播源 + 3 个酒店源，支持自定义 URL
- **验证**：并发检测播放地址可用性（HEAD → GET 降级）
- **导出**：M3U / TXT 格式，支持一键搜索→验证→导出
- **前端**：深色科技风 Web 界面

## 快速开始

### Docker 部署（推荐）

```bash
docker-compose up -d
```

访问 http://localhost:8080

### 本地开发

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# 前端
cd frontend
npm install
npm run dev
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/search | 搜索 IPTV 源 |
| POST | /api/validate | 验证所有地址 |
| GET | /api/validate/single?url= | 验证单个地址 |
| GET | /api/export/m3u | 导出 M3U |
| GET | /api/export/txt | 导出 TXT |
| GET | /api/export/m3u/full | 搜索→验证→导出 M3U |
| GET | /api/export/txt/full | 搜索→验证→导出 TXT |
| GET | /api/stats | 搜索统计 |
| GET | /api/sources/builtin | 内置源列表 |
| POST | /api/sources/builtin/add | 添加自定义源 |

## 项目结构

```
iptv-aggregator/
├── backend/app/
│   ├── main.py          # FastAPI 入口
│   ├── api/search.py    # 搜索/验证/导出 API
│   └── core/searcher.py # 搜索引擎 + 验证器
├── frontend/src/
│   ├── App.vue          # 主界面
│   └── api/search.js    # API 客户端
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 版本

- **v4.0.1** (2026-06-12) — 精简重构，专注搜索+验证+导出
- v1.0.0 (2026-06-06) — 初始版本
