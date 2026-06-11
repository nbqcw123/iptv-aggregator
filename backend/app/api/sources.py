"""
IPTV 数据源管理 v3
====================
功能：
- 数据源 CRUD（添加、编辑、删除、启用/禁用）
- 按类型分类（multicast/hotel/custom）
- 按地区分类（cn/hk/tw/overseas 等）
- 数据源测速（单个/批量）
- 搜索全网公开源（GitHub 爬取）
"""
import re
import aiohttp
import asyncio
import time
import json
import os
from typing import Optional
from dataclasses import dataclass, field, asdict
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.searcher import DATA_DIR

# ============ 文件路径 ============
SOURCES_FILE = os.path.join(DATA_DIR, "sources.json")       # 用户自定义数据源
SOURCES_CACHE_FILE = os.path.join(DATA_DIR, "sources_cache.json")  # 全网搜索缓存

# ============ 数据模型 ============

@dataclass
class Source:
    id: str = ""
    name: str = ""                 # 显示名称
    url: str = ""                  # 数据源 URL
    type: str = "multicast"        # multicast / hotel / custom
    region: str = "cn"             # cn / hk / tw / overseas / unknown
    enabled: bool = True           # 是否启用
    priority: int = 0              # 优先级（越小越优先）
    created_at: float = 0          # 创建时间
    updated_at: float = 0          # 更新时间
    last_check: float = 0          # 最后测速时间
    last_status: str = "unknown"   # unknown / ok / error
    last_response_ms: int = 0      # 上次响应时间 ms
    entry_count: int = 0           # 上次解析到的频道数
    note: str = ""                 # 备注

# 地区显示名
REGION_LABELS = {
    "cn": "中国大陆",
    "hk": "中国香港",
    "tw": "中国台湾",
    "kr": "韩国",
    "jp": "日本",
    "sg": "新加坡",
    "us": "美国",
    "uk": "英国",
    "overseas": "海外其他",
    "unknown": "未知",
}

# 类型显示名
TYPE_LABELS = {
    "multicast": "组播源",
    "hotel": "酒店源",
    "custom": "自定义",
}

# ============ 预置知名数据源（全网搜索的初始列表）============

PRESET_SOURCES = [
    # --- 组播源 ---
    {"name": "iptv-org/cn", "url": "https://iptv-org.github.io/iptv/countries/cn.m3u", "type": "multicast", "region": "cn"},
    {"name": "fanmingming/live", "url": "https://live.fanmingming.com/tv/m3u/ipv6.m3u", "type": "multicast", "region": "cn"},
    {"name": "Meroser/iptv", "url": "https://raw.githubusercontent.com/Meroser/iptv/main/cn.m3u", "type": "multicast", "region": "cn"},
    {"name": "iwangshushu/iptv", "url": "https://raw.githubusercontent.com/iwangshushu/iptv/main/cn.m3u", "type": "multicast", "region": "cn"},
    # --- 酒店源 ---
    {"name": "iptv-org/hotel", "url": "https://iptv-org.github.io/iptv/categories/hotel.m3u", "type": "hotel", "region": "cn"},
    {"name": "fanmingming/hotel", "url": "https://live.fanmingming.com/tv/m3u/hotel.m3u", "type": "hotel", "region": "cn"},
]

# ============ 数据源持久化 ============

def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def _load_json(path: str, default) -> any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default

def _save_json(path: str, data):
    _ensure_dir()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_sources() -> list[Source]:
    _ensure_dir()
    data = _load_json(SOURCES_FILE, None)
    if data is None:
        # 首次启动：从预置源初始化
        sources = []
        for i, ps in enumerate(PRESET_SOURCES):
            src = Source(
                id=f"src_{int(time.time()*1000)+i:012d}",
                name=ps["name"],
                url=ps["url"],
                type=ps["type"],
                region=ps["region"],
                enabled=True,
                priority=i,
                created_at=time.time(),
                updated_at=time.time(),
            )
            sources.append(src)
        save_sources(sources)
        return sources
    return [Source(**s) for s in data]

def save_sources(sources: list[Source]):
    _save_json(SOURCES_FILE, [asdict(s) for s in sources])

# ============ 地区自动检测 ============

def detect_region(name: str, url: str) -> str:
    """根据名称和 URL 自动检测地区"""
    text = (name + " " + url).lower()
    # 关键词匹配
    if any(k in text for k in ["hk", "hongkong", "hong kong", "香港"]):
        return "hk"
    if any(k in text for k in ["tw", "taiwan", "台湾", "台灣"]):
        return "tw"
    if any(k in text for k in ["kr", "korea", "韩国", "韓國"]):
        return "kr"
    if any(k in text for k in ["jp", "japan", "日本"]):
        return "jp"
    if any(k in text for k in ["sg", "singapore", "新加坡"]):
        return "sg"
    if any(k in text for k in ["us", "usa", "united states", "美国"]):
        return "us"
    if any(k in text for k in ["uk", "britain", "英國", "英国"]):
        return "uk"
    if any(k in text for k in ["cn", "china", "中国", "大陸", "大陆"]):
        return "cn"
    # 根据 URL 域名判断
    if "githubusercontent.com" in text or "github.io" in text:
        return "unknown"
    return "unknown"

# ============ 数据源测速 ============

_EXTINF_RE = re.compile(r'#EXTINF:', re.MULTILINE)

async def check_source(session, url: str, timeout: int = 10) -> dict:
    """测速单个数据源 URL，返回 {valid, status_code, response_ms, entry_count, error}"""
    res = {"valid": False, "status_code": 0, "response_ms": 0, "entry_count": 0, "error": ""}
    h = {'User-Agent': 'VLC/3.0.18', 'Accept': '*/*'}
    start = time.monotonic()
    try:
        async with session.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=timeout), ssl=False, allow_redirects=True) as r:
            elapsed = int((time.monotonic() - start) * 1000)
            res["status_code"] = r.status
            res["response_ms"] = elapsed
            if r.status < 400:
                text = await r.text(encoding='utf-8', errors='replace')
                res["valid"] = True
                # 统计频道数
                res["entry_count"] = len(_EXTINF_RE.findall(text))
            else:
                res["error"] = f"HTTP {r.status}"
    except asyncio.TimeoutError:
        res["response_ms"] = int((time.monotonic() - start) * 1000)
        res["error"] = "timeout"
    except Exception as e:
        res["response_ms"] = int((time.monotonic() - start) * 1000)
        res["error"] = str(e)[:100]
    return res

async def check_sources_batch(sources: list[Source], concurrency: int = 5, timeout: int = 10) -> list[dict]:
    """批量测速，并发执行"""
    sem = asyncio.Semaphore(max(1, concurrency))
    results = []

    async def _one(src: Source):
        async with sem:
            result = await check_source(session, src.url, timeout)
            # 更新源状态
            src.last_check = time.time()
            src.last_response_ms = result["response_ms"]
            src.entry_count = result["entry_count"]
            src.last_status = "ok" if result["valid"] else "error"
            src.updated_at = time.time()
            return {"id": src.id, **result}

    async with aiohttp.ClientSession() as session:
        tasks = [_one(s) for s in sources if s.enabled]
        results = await asyncio.gather(*tasks)

    return results

# ============ 全网搜索（GitHub）============

async def search_online_sources(timeout: int = 15) -> list[dict]:
    """
    搜索全网公开的 IPTV 数据源
    从 GitHub 搜索含 .m3u 的仓库
    """
    results = []
    cache = _load_json(SOURCES_CACHE_FILE, None)

    # 缓存有效期 6 小时
    if cache and cache.get("ts", 0) > time.time() - 21600:
        return cache.get("data", [])

    # GitHub 搜索：含 iptv m3u 的仓库文件
    search_queries = [
        "iptv m3u china",
        "iptv m3u hotel",
        "live tv m3u playlist",
        "iptv github playlist",
    ]

    h = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Accept': 'application/vnd.github.v3+json'
    }

    seen_urls = set()
    async with aiohttp.ClientSession() as session:
        # 方法1：GitHub API 搜索
        for q in search_queries[:2]:  # 只用前两个避免限速
            try:
                url = f"https://api.github.com/search/code?q={q.replace(' ', '+')}+in:file&per_page=10"
                async with session.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                    if r.status == 200:
                        data = await r.json()
                        for item in data.get("items", []):
                            dl_url = item.get("html_url", "").replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                            if dl_url and dl_url not in seen_urls and ".m3u" in dl_url.lower():
                                seen_urls.add(dl_url)
                                results.append({
                                    "name": item.get("repository", {}).get("full_name", "unknown"),
                                    "url": dl_url,
                                    "type": "multicast",
                                    "region": "unknown",
                                })
            except:
                pass

        # 方法2：知名仓库的已知文件列表
        known_repos = [
            ("iptv-org/iptv", "https://iptv-org.github.io/iptv/index.m3u"),
            ("iptv-org/iptv", "https://iptv-org.github.io/iptv/countries/cn.m3u"),
            ("iptv-org/iptv", "https://iptv-org.github.io/iptv/categories/hotel.m3u"),
            ("freearhey/iptv", "https://raw.githubusercontent.com/freearhey/iptv/master/index.m3u"),
            ("Kimentanm/iptv", "https://raw.githubusercontent.com/Kimentanm/iptv/master/cn.m3u"),
        ]
        for repo, url in known_repos:
            if url not in seen_urls:
                seen_urls.add(url)
                # 从 URL 推断类型和地区
                src_type = "hotel" if "hotel" in url.lower() else "multicast"
                region = detect_region(repo, url)
                results.append({
                    "name": repo + url.replace("https://", "/").rsplit("/", 1)[-1],
                    "url": url,
                    "type": src_type,
                    "region": region,
                })

    # 写入缓存
    _save_json(SOURCES_CACHE_FILE, {"ts": time.time(), "data": results})
    return results

# ============ API 路由 ============

router = APIRouter()

# --- Pydantic 模型 ---

class SourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=5, max_length=500)
    type: str = Field(default="multicast")
    region: str = Field(default="cn")
    enabled: bool = Field(default=True)
    priority: int = Field(default=0)
    note: str = Field(default="")

class SourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    type: Optional[str] = None
    region: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    note: Optional[str] = None

class SourceCheckReq(BaseModel):
    ids: Optional[list[str]] = None  # None = 测全部
    concurrency: int = Field(default=5, ge=1, le=20)
    timeout: int = Field(default=10, ge=3, le=30)

# --- CRUD ---

@router.get("/sources", summary="获取数据源列表")
async def list_sources(
    type: Optional[str] = Query(default=None, description="按类型筛选: multicast/hotel/custom"),
    region: Optional[str] = Query(default=None, description="按地区筛选: cn/hk/tw/overseas"),
    enabled_only: bool = Query(default=False),
    keyword: Optional[str] = Query(default=None),
):
    sources = load_sources()

    # 筛选
    if type:
        sources = [s for s in sources if s.type == type]
    if region:
        sources = [s for s in sources if s.region == region]
    if enabled_only:
        sources = [s for s in sources if s.enabled]
    if keyword:
        kw = keyword.lower()
        sources = [s for s in sources if kw in s.name.lower() or kw in s.url.lower()]

    return {"code": 0, "message": "ok", "data": {
        "sources": [asdict(s) for s in sources],
        "total": len(sources),
        "types": TYPE_LABELS,
        "regions": REGION_LABELS,
    }}

@router.post("/sources", summary="添加数据源")
async def add_source(req: SourceCreate):
    sources = load_sources()
    src_id = f"src_{int(time.time()*1000):012d}"
    src = Source(
        id=src_id,
        name=req.name,
        url=req.url,
        type=req.type,
        region=req.region if req.region != "unknown" else detect_region(req.name, req.url),
        enabled=req.enabled,
        priority=req.priority,
        created_at=time.time(),
        updated_at=time.time(),
        note=req.note,
    )
    sources.append(src)
    save_sources(sources)
    return {"code": 0, "message": "添加成功", "data": {"id": src_id}}

@router.put("/sources/{src_id}", summary="更新数据源")
async def update_source(src_id: str, req: SourceUpdate):
    sources = load_sources()
    for s in sources:
        if s.id == src_id:
            if req.name is not None: s.name = req.name
            if req.url is not None: s.url = req.url
            if req.type is not None: s.type = req.type
            if req.region is not None: s.region = req.region
            if req.enabled is not None: s.enabled = req.enabled
            if req.priority is not None: s.priority = req.priority
            if req.note is not None: s.note = req.note
            s.updated_at = time.time()
            save_sources(sources)
            return {"code": 0, "message": "更新成功", "data": None}
    return {"code": 1, "message": "数据源不存在", "data": None}

@router.delete("/sources/{src_id}", summary="删除数据源")
async def delete_source(src_id: str):
    sources = load_sources()
    new_list = [s for s in sources if s.id != src_id]
    if len(new_list) == len(sources):
        return {"code": 1, "message": "数据源不存在", "data": None}
    save_sources(new_list)
    return {"code": 0, "message": "删除成功", "data": None}

@router.post("/sources/import", summary="批量导入数据源")
async def import_sources(reqs: list[SourceCreate]):
    sources = load_sources()
    count = 0
    existing_urls = {s.url for s in sources}
    for r in reqs:
        if r.url not in existing_urls:
            src_id = f"src_{int(time.time()*1000)+count:012d}"
            sources.append(Source(
                id=src_id, name=r.name, url=r.url, type=r.type,
                region=r.region if r.region != "unknown" else detect_region(r.name, r.url),
                enabled=r.enabled, priority=r.priority,
                created_at=time.time(), updated_at=time.time(), note=r.note,
            ))
            count += 1
    save_sources(sources)
    return {"code": 0, "message": f"导入成功: {count} 条新增", "data": {"imported": count}}

@router.post("/sources/reset", summary="重置为默认数据源")
async def reset_sources():
    if os.path.exists(SOURCES_FILE):
        os.remove(SOURCES_FILE)
    sources = load_sources()
    return {"code": 0, "message": f"已重置为默认 {len(sources)} 个数据源", "data": None}

# --- 测速 ---

@router.post("/sources/check", summary="测速数据源")
async def check_sources(req: SourceCheckReq):
    sources = load_sources()
    if req.ids:
        to_check = [s for s in sources if s.id in req.ids]
    else:
        to_check = [s for s in sources if s.enabled]

    if not to_check:
        return {"code": 0, "message": "没有需要测速的数据源", "data": []}

    results = await check_sources_batch(to_check, concurrency=req.concurrency, timeout=req.timeout)
    save_sources(sources)  # 保存测速结果

    return {"code": 0, "message": f"完成 {len(results)} 个数据源测速", "data": results}

@router.post("/sources/check/{src_id}", summary="测速单个数据源")
async def check_single_source(src_id: str, timeout: int = Query(default=10, ge=3, le=30)):
    sources = load_sources()
    src = next((s for s in sources if s.id == src_id), None)
    if not src:
        return {"code": 1, "message": "数据源不存在", "data": None}

    async with aiohttp.ClientSession() as session:
        result = await check_source(session, src.url, timeout)

    src.last_check = time.time()
    src.last_response_ms = result["response_ms"]
    src.entry_count = result["entry_count"]
    src.last_status = "ok" if result["valid"] else "error"
    src.updated_at = time.time()
    save_sources(sources)

    return {"code": 0, "message": "ok", "data": {"id": src_id, **result}}

# --- 全网搜索 ---

@router.get("/sources/search-online", summary="搜索全网公开数据源")
async def search_online(timeout: int = Query(default=15, ge=5, le=30)):
    results = await search_online_sources(timeout=timeout)
    return {"code": 0, "message": f"搜索到 {len(results)} 个数据源", "data": results}

# --- 分类统计 ---

@router.get("/sources/stats", summary="数据源统计")
async def source_stats():
    sources = load_sources()
    type_stats = {}
    region_stats = {}
    status_stats = {"ok": 0, "error": 0, "unknown": 0}
    for s in sources:
        type_stats.setdefault(s.type, 0)
        type_stats[s.type] += 1
        region_stats.setdefault(s.region, 0)
        region_stats[s.region] += 1
        status_stats[s.last_status] = status_stats.get(s.last_status, 0) + 1

    return {"code": 0, "message": "ok", "data": {
        "total": len(sources),
        "enabled": sum(1 for s in sources if s.enabled),
        "by_type": type_stats,
        "by_region": region_stats,
        "by_status": status_stats,
        "type_labels": TYPE_LABELS,
        "region_labels": REGION_LABELS,
    }}
