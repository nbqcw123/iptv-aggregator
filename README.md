# IPTV 聚合器

IPTV 组播源 + 酒店源搜索聚合工具。数据源管理 → 搜索 → 测速验证 → 择优 → 导出 M3U + TXT。

## 功能

- **数据源管理**：添加/编辑/删除/启用/禁用数据源，支持按类型（组播/酒店/自定义）和地区分类
- **数据源测速**：检测数据源可用性，显示响应时间和频道数，支持单个/批量/按分类测速
- **全网搜索**：自动从 GitHub 发现公开 IPTV 源，勾选批量导入
- **频道搜索**：从启用的数据源搜索频道，按频道表匹配
- **测速验证**：并发检测播放地址可用性（HEAD → GET 降级），IPv4/IPv6 过滤
- **择优导出**：同一频道保留最快的 N 条，导出 M3U / TXT 格式
- **定时更新**：后台定时自动搜索+测速+更新
- **前端**：深色科技风 Web 界面，三标签页（搜索测速 / 数据源管理 / 频道表）

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

### 数据源管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/sources | 获取数据源列表（支持 ?type=&region=&keyword=&enabled_only= 筛选） |
| POST | /api/sources | 添加数据源 |
| PUT | /api/sources/{id} | 更新数据源 |
| DELETE | /api/sources/{id} | 删除数据源 |
| POST | /api/sources/import | 批量导入数据源 |
| POST | /api/sources/reset | 重置为默认数据源 |
| GET | /api/sources/stats | 数据源统计（按类型/地区/状态） |
| POST | /api/sources/check | 批量测速（支持 ?ids= 指定，默认测全部启用源） |
| POST | /api/sources/check/{id} | 测速单个数据源 |
| GET | /api/sources/search-online | 搜索全网公开数据源（GitHub） |

### 频道表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/channels | 获取频道表 |
| POST | /api/channels | 添加频道 |
| PUT | /api/channels/{id} | 更新频道 |
| DELETE | /api/channels/{id} | 删除频道 |
| POST | /api/channels/import | 批量导入频道 |
| POST | /api/channels/reset | 重置为默认频道表 |

### 搜索与导出

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/run | 执行完整流程：搜索→测速→择优 |
| GET | /api/export/m3u | 导出 M3U |
| GET | /api/export/txt | 导出 TXT |
| GET | /api/export/full | 一键搜索→测速→导出 M3U |
| GET | /api/stats | 当前结果统计 |
| GET | /api/speed/cache | 测速缓存 |
| DELETE | /api/speed/cache | 清除测速缓存 |

### 定时任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/schedule | 获取定时配置 |
| POST | /api/schedule | 更新定时配置 |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /docs | Swagger API 文档 |

## 数据源类型

- **multicast** — 组播源（各地广电组播）
- **hotel** — 酒店源（酒店 IPTV）
- **custom** — 自定义源

## 地区分类

| 代码 | 地区 |
|------|------|
| cn | 中国大陆 |
| hk | 中国香港 |
| tw | 中国台湾 |
| kr | 韩国 |
| jp | 日本 |
| sg | 新加坡 |
| us | 美国 |
| uk | 英国 |
| overseas | 海外其他 |
| unknown | 未知（自动检测） |

## 项目结构

```
iptv-aggregator/
├── backend/app/
│   ├── main.py          # FastAPI 入口
│   ├── api/
│   │   ├── search.py    # 搜索/验证/导出/定时 API
│   │   └── sources.py   # 数据源管理 API（CRUD + 测速 + 全网搜索）
│   ├── core/
│   │   └── searcher.py  # 搜索引擎 + 测速器 + 频道匹配
│   └── static/          # 前端构建产物
├── frontend/src/
│   ├── App.vue          # 主界面（三标签页）
│   └── api/request.js   # API 客户端
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 版本

- **v3.1.0** (2026-06-11) — 数据源管理：CRUD + 分类（类型×地区）+ 测速 + 全网搜索 + 三标签页前端
- **v3.0.1** (2026-06-11) — 修复：移除未使用的 database 模块，清理依赖
- **v3.0.0** (2026-06-06) — 频道表 + 测速择优 + 定时更新
