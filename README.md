# IPTV 聚合器

IPTV 组播源 + 酒店源搜索聚合工具。搜索 → 验证可用性 → 去重 → 导出 M3U + TXT。

## 功能

- **搜索**：数据源管理（添加/编辑/删除/启用/禁用），支持按类型（组播/酒店/自定义）和地区分类
- **测速**：数据源可用性检测，显示响应时间和频道数
- **全网搜索**：自动发现 GitHub 上的公开 IPTV 源
- **验证**：并发检测播放地址可用性（HEAD → GET 降级）
- **导出**：M3U / TXT 格式，支持一键搜索→验证→导出
- **前端**：深色科技风 Web 界面，三标签页（搜索/数据源/频道表）

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
| GET | /api/sources/stats | 数据源统计 |
| POST | /api/sources/check | 批量测速 |
| POST | /api/sources/check/{id} | 单个测速 |
| GET | /api/sources/search-online | 全网搜索 |
| GET | /api/stats | 搜索统计 |

## 项目结构

```
iptv-aggregator/
├── backend/app/
│   ├── main.py          # FastAPI 入口
│   ├── api/search.py    # 搜索/验证/导出 API
│   ├── api/sources.py   # 数据源管理 API
│   └── core/searcher.py # 搜索引擎 + 验证器
├── frontend/src/
│   ├── App.vue          # 主界面
│   └── api/search.js    # API 客户端
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 版本

- **v3.1.0** (2026-06-11) — 数据源管理：CRUD + 分类（类型×地区）+ 测速 + 全网搜索 + 三标签页前端
- **v3.0.1** (2026-06-11) — 修复：移除未使用的 database 模块，清理依赖，修正版本号
- **v3.0.0** (2026-06-06) — 频道表 + 测速择优 + 定时更新
