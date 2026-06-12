"""
IPTV 采集器 — 组播/酒店源 API 抓取
=====================================
参考群晖 cqshushu/iptv-spider 的采集方式：
- 从公开 API 抓取组播/酒店源 IP
- 按日期过滤新 IP
- 并发校验可用性
- 支持增量采集 + 存量检测
"""
import asyncio
import aiohttp
import time
import json
import os
import re
import sqlite3
from typing import Optional
from dataclasses import dataclass, field, asdict

# ============ 配置 ============
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.expanduser("~/.iptv-data")))
DB_FILE = os.path.join(DATA_DIR, "iptv.db")
API_TIMEOUT = 15
CHECK_TIMEOUT = 5
MAX_RETRIES = 3  # 失效重试次数
AUTO_DAYS = 7    # 采集最近 N 天的数据
LOG_RETENTION_DAYS = 3  # 日志保留天数


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


# ============ SQLite 数据库 ============

def _get_db():
    _ensure_dir()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    
    # IP 表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            port INTEGER DEFAULT 0,
            url TEXT NOT NULL,
            source_type TEXT DEFAULT 'multicast',
            status TEXT DEFAULT 'active',
            fail_count INTEGER DEFAULT 0,
            check_count INTEGER DEFAULT 0,
            first_found_at TEXT NOT NULL,
            last_checked_at TEXT,
            response_time INTEGER DEFAULT 0,
            speed REAL DEFAULT 0.0,
            UNIQUE(url)
        )
    """)
    
    # 日志表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collect_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source_type TEXT DEFAULT '',
            found_count INTEGER DEFAULT 0,
            valid_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    return conn


class IpvDB:
    """IP 数据库操作"""
    
    def __init__(self):
        self.conn = _get_db()
    
    def upsert_ip(self, url: str, source_type: str = "multicast", 
                  response_time: int = 0, speed: float = 0.0):
        """插入或更新 IP"""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        ip, port = self._parse_url(url)
        
        existing = self.conn.execute(
            "SELECT id, status, fail_count FROM ips WHERE url = ?", (url,)
        ).fetchone()
        
        if existing:
            # 更新
            self.conn.execute("""
                UPDATE ips SET status=?, fail_count=0, last_checked_at=?, 
                response_time=?, speed=?, check_count=check_count+1
                WHERE url=?
            """, ("active", now, response_time, speed, url))
        else:
            # 新增
            self.conn.execute("""
                INSERT INTO ips (ip, port, url, source_type, status, first_found_at, last_checked_at, response_time, speed, check_count)
                VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, 1)
            """, (ip, port, url, source_type, now, now, response_time, speed))
        
        self.conn.commit()
    
    def mark_failed(self, url: str):
        """标记 IP 失效"""
        self.conn.execute("""
            UPDATE ips SET fail_count=fail_count+1, last_checked_at=?, check_count=check_count+1
            WHERE url=?
        """, (time.strftime("%Y-%m-%d %H:%M:%S"), url))
        
        # 超过阈值标记为暂时失效
        row = self.conn.execute("SELECT fail_count FROM ips WHERE url=?", (url,)).fetchone()
        if row and row["fail_count"] >= MAX_RETRIES:
            self.conn.execute("UPDATE ips SET status='temp_failed' WHERE url=?", (url,))
        
        self.conn.commit()
    
    def get_active_ips(self, source_type: str = "all") -> list:
        """获取有效 IP"""
        if source_type == "all":
            rows = self.conn.execute(
                "SELECT * FROM ips WHERE status='active' ORDER BY last_checked_at DESC"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM ips WHERE status='active' AND source_type=? ORDER BY last_checked_at DESC",
                (source_type,)
            ).fetchall()
        return [dict(r) for r in rows]
    
    def get_failed_ips(self) -> list:
        """获取暂时失效的 IP"""
        rows = self.conn.execute(
            "SELECT * FROM ips WHERE status='temp_failed'"
        ).fetchall()
        return [dict(r) for r in rows]
    
    def reset_failed_status(self, url: str):
        """重置失效状态（重试成功时）"""
        self.conn.execute("""
            UPDATE ips SET status='active', fail_count=0 WHERE url=?
        """, (url,))
        self.conn.commit()
    
    def get_existing_urls(self) -> set:
        """获取所有已存在的 URL"""
        rows = self.conn.execute("SELECT url FROM ips").fetchall()
        return {r["url"] for r in rows}
    
    def get_ip_count(self, status: str = "active") -> int:
        """获取 IP 数量"""
        if status == "all":
            row = self.conn.execute("SELECT COUNT(*) as cnt FROM ips").fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) as cnt FROM ips WHERE status=?", (status,)).fetchone()
        return row["cnt"] if row else 0
    
    def cleanup_old_logs(self, days: int = LOG_RETENTION_DAYS):
        """清理旧日志"""
        cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))
        self.conn.execute("DELETE FROM collect_log WHERE created_at < ?", (cutoff,))
        self.conn.commit()
    
    def log_collection(self, source_type: str, found: int, valid: int, fail: int):
        """记录采集日志"""
        self.conn.execute("""
            INSERT INTO collect_log (created_at, source_type, found_count, valid_count, fail_count)
            VALUES (?, ?, ?, ?, ?)
        """, (time.strftime("%Y-%m-%d %H:%M:%S"), source_type, found, valid, fail))
        self.conn.commit()
    
    @staticmethod
    def _parse_url(url: str) -> tuple:
        """解析 URL 获取 IP 和端口"""
        m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::(\d+))?', url)
        if m:
            return m.group(1), int(m.group(2)) if m.group(2) else 0
        return "", 0


# ============ API 源采集 ============

# 组播源 API（参考群晖 cqshushu/iptv-spider v2.1.1）
# 主 API: http://api.cqshushu.com/multicast.php
# 搜索接口: http://foodieguide.com/iptvsearch/getall.php?ip={ip_port}&c=&tk=&p=
MULTICAST_APIS = [
    # cqshushu 组播 API（需 token: cQshuShu88888888）
    "http://api.cqshushu.com/multicast.php",
    # 在线 M3U 源作为补充
    "https://iptv-org.github.io/iptv/countries/cn.m3u",
]

# 酒店源 API
# 主 API: http://api.cqshushu.com/hotel.php
HOTEL_APIS = [
    # cqshushu 酒店 API
    "http://api.cqshushu.com/hotel.php",
]

# cqshushu API 配置
CQSHUSHU_TOKEN = "cQshuShu88888888"
CQSHUSHU_BASE_URL = "http://api.cqshushu.com"
FOODIUGUIDE_SEARCH_URL = "http://foodieguide.com/iptvsearch/getall.php"

# 在线列表源（M3U/TXT）
ONLINE_M3U_SOURCES = [
    {"name": "iptv-org/cn", "url": "https://iptv-org.github.io/iptv/countries/cn.m3u"},
    {"name": "fanmingming", "url": "https://live.fanmingming.com/tv/m3u/ipv6.m3u"},
    {"name": "Meroser/cn", "url": "https://raw.githubusercontent.com/Meroser/iptv/main/cn.m3u"},
]

ONLINE_TXT_SOURCES = [
    {"name": "iptv-org/hotel", "url": "https://iptv-org.github.io/iptv/categories/hotel.m3u"},
]


@dataclass
class CollectResult:
    source_type: str
    found_count: int = 0
    valid_count: int = 0
    fail_count: int = 0
    new_count: int = 0
    urls: list = field(default_factory=list)


async def _fetch_json(session, url: str, timeout: int = API_TIMEOUT) -> dict:
    """获取 JSON API"""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), ssl=False) as r:
            return await r.json()
    except:
        return {}


async def _fetch_text(session, url: str, timeout: int = API_TIMEOUT) -> str:
    """获取文本内容"""
    try:
        headers = {'User-Agent': 'VLC/3.0.18', 'Accept': '*/*'}
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), 
                               ssl=False, headers=headers) as r:
            return await r.text(encoding='utf-8', errors='replace')
    except:
        return ""


def _parse_m3u(text: str) -> list:
    """解析 M3U 获取 URL 列表"""
    urls = []
    lines = text.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:') and i + 1 < len(lines):
            nxt = lines[i+1].strip()
            if not nxt.startswith('#') and nxt:
                urls.append(nxt)
                i += 1
        i += 1
    return urls


def _parse_txt(text: str) -> list:
    """解析 TXT 获取 URL 列表"""
    urls = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        for sep in [',', '|', '\t']:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    url = parts[1].strip()
                    if url.startswith(('http://', 'https://', 'rtsp://', 'rtp://', 'udp://')):
                        urls.append(url)
                break
    return urls


async def check_url(session, url: str, timeout: int = CHECK_TIMEOUT) -> tuple:
    """检测 URL 是否可用，返回 (valid, response_time, speed)"""
    start = time.monotonic()
    try:
        headers = {'User-Agent': 'VLC/3.0.18', 'Accept': '*/*', 'Range': 'bytes=0-4095'}
        # HEAD 优先
        try:
            async with session.head(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout), 
                                   ssl=False, allow_redirects=True) as r:
                elapsed = int((time.monotonic() - start) * 1000)
                if r.status < 400:
                    return True, elapsed, 0.0
        except:
            pass
        
        # GET 降级
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout), 
                               ssl=False, allow_redirects=True) as r:
            data = await r.content.read(1024)
            elapsed = int((time.monotonic() - start) * 1000)
            if r.status < 400:
                speed = round(len(data) / elapsed / 1000, 2) if elapsed > 0 else 0
                return True, elapsed, speed
    except:
        pass
    
    return False, int((time.monotonic() - start) * 1000), 0.0


async def collect_multicast(db: IpvDB, pages: int = 5, days: int = AUTO_DAYS,
                             concurrency: int = 20) -> CollectResult:
    """采集组播源（cqshushu API + 在线 M3U）"""
    result = CollectResult(source_type="multicast")
    existing_urls = db.get_existing_urls()
    
    async with aiohttp.ClientSession() as session:
        all_urls = []
        
        # 1. 从 cqshushu API 获取（翻页）
        for page in range(1, pages + 1):
            try:
                params = {
                    "token": CQSHUSHU_TOKEN,
                    "page": page,
                    "days": days,
                    "type": "multicast"
                }
                headers = {
                    "User-Agent": "okhttp/3.12.1",
                    "clientType": "3",
                    "appId": "ys7",
                }
                async with session.get(
                    f"{CQSHUSHU_BASE_URL}/multicast.php",
                    params=params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=API_TIMEOUT), ssl=False
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        if isinstance(data, list):
                            for item in data:
                                url = item.get("url", "") or item.get("stream", "")
                                if url:
                                    all_urls.append(url)
                        elif isinstance(data, dict):
                            items = data.get("data", []) or data.get("list", []) or data.get("result", [])
                            for item in items:
                                url = item.get("url", "") or item.get("stream", "")
                                if url:
                                    all_urls.append(url)
            except Exception as e:
                print(f"  cqshushu multicast page {page} error: {e}")
        
        # 2. 从在线 M3U 源获取（补充）
        for src in ONLINE_M3U_SOURCES:
            if src["url"].endswith(".m3u"):
                text = await _fetch_text(session, src["url"])
                if text:
                    urls = _parse_m3u(text)
                    all_urls.extend(urls)
        
        # 去重
        all_urls = list(set(all_urls))
        
        # 过滤已存在的
        new_urls = [u for u in all_urls if u not in existing_urls]
        result.found_count = len(all_urls)
        result.new_count = len(new_urls)
        
        # 并发校验
        sem = asyncio.Semaphore(concurrency)
        
        async def _check_url(url):
            async with sem:
                valid, rt, speed = await check_url(session, url)
                if valid:
                    db.upsert_ip(url, "multicast", rt, speed)
                    return True, url
                else:
                    db.mark_failed(url)
                    return False, url
        
        if new_urls:
            check_results = await asyncio.gather(*[_check_url(u) for u in new_urls[:pages * 10]])
            result.valid_count = sum(1 for v, _ in check_results if v)
            result.fail_count = sum(1 for v, _ in check_results if not v)
            result.urls = [u for v, u in check_results if v]
    
    db.log_collection("multicast", result.found_count, result.valid_count, result.fail_count)
    return result


async def collect_hotel(db: IpvDB, pages: int = 5, days: int = AUTO_DAYS,
                         concurrency: int = 20) -> CollectResult:
    """采集酒店源（cqshushu API + 在线 TXT）"""
    result = CollectResult(source_type="hotel")
    existing_urls = db.get_existing_urls()
    
    async with aiohttp.ClientSession() as session:
        all_urls = []
        
        # 1. 从 cqshushu API 获取（翻页）
        for page in range(1, pages + 1):
            try:
                params = {
                    "token": CQSHUSHU_TOKEN,
                    "page": page,
                    "days": days,
                    "type": "hotel"
                }
                headers = {
                    "User-Agent": "okhttp/3.12.1",
                    "clientType": "3",
                    "appId": "ys7",
                }
                async with session.get(
                    f"{CQSHUSHU_BASE_URL}/hotel.php",
                    params=params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=API_TIMEOUT), ssl=False
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        if isinstance(data, list):
                            for item in data:
                                url = item.get("url", "") or item.get("stream", "")
                                if url:
                                    all_urls.append(url)
                        elif isinstance(data, dict):
                            items = data.get("data", []) or data.get("list", []) or data.get("result", [])
                            for item in items:
                                url = item.get("url", "") or item.get("stream", "")
                                if url:
                                    all_urls.append(url)
            except Exception as e:
                print(f"  cqshushu hotel page {page} error: {e}")
        
        # 2. 从在线 TXT 源获取（补充）
        for src in ONLINE_TXT_SOURCES:
            text = await _fetch_text(session, src["url"])
            if text:
                urls = _parse_txt(text)
                all_urls.extend(urls)
        
        # 去重
        all_urls = list(set(all_urls))
        
        new_urls = [u for u in all_urls if u not in existing_urls]
        result.found_count = len(all_urls)
        result.new_count = len(new_urls)
        
        sem = asyncio.Semaphore(concurrency)
        
        async def _check_url(url):
            async with sem:
                valid, rt, speed = await check_url(session, url)
                if valid:
                    db.upsert_ip(url, "hotel", rt, speed)
                    return True, url
                else:
                    db.mark_failed(url)
                    return False, url
        
        if new_urls:
            check_results = await asyncio.gather(*[_check_url(u) for u in new_urls[:pages * 10]])
            result.valid_count = sum(1 for v, _ in check_results if v)
            result.fail_count = sum(1 for v, _ in check_results if not v)
            result.urls = [u for v, u in check_results if v]
    
    db.log_collection("hotel", result.found_count, result.valid_count, result.fail_count)
    return result


async def check_existing_ips(db: IpvDB, concurrency: int = 20, 
                              timeout: int = CHECK_TIMEOUT) -> dict:
    """
    存量 IP 检测（参考群晖逻辑）
    3轮重试，超过阈值标记为暂时失效
    """
    active_ips = db.get_active_ips()
    failed_ips = db.get_failed_ips()
    
    to_check = active_ips + failed_ips
    total = len(to_check)
    
    valid_count = 0
    fail_count = 0
    
    sem = asyncio.Semaphore(concurrency)
    
    async def _check_row(row):
        async with sem:
            valid, rt, speed = await check_url(aiohttp.ClientSession(), row["url"], timeout)
            if valid:
                db.reset_failed_status(row["url"])
                db.upsert_ip(row["url"], row.get("source_type", "multicast"), rt, speed)
                return True
            else:
                db.mark_failed(row["url"])
                return False
    
    async with aiohttp.ClientSession() as session:
        # 分批检测（避免一次性创建太多连接）
        batch_size = 50
        for i in range(0, len(to_check), batch_size):
            batch = to_check[i:i+batch_size]
            results = await asyncio.gather(*[_check_row(r) for r in batch])
            valid_count += sum(1 for v in results if v)
            fail_count += sum(1 for v in results if not v)
    
    return {
        "total_checked": total,
        "valid_count": valid_count,
        "fail_count": fail_count,
        "active_count": db.get_ip_count("active"),
        "failed_count": db.get_ip_count("temp_failed"),
    }


async def full_collection(pages: int = 5, days: int = AUTO_DAYS, 
                           concurrency: int = 20, source_type: str = "all") -> dict:
    """
    完整采集流程：
    1. 采集新源（组播/酒店）
    2. 存量 IP 检测（3轮重试）
    3. 清理旧日志
    """
    db = IpvDB()
    results = {}
    
    # 1. 新源采集
    if source_type in ("all", "multicast"):
        results["multicast"] = await collect_multicast(db, pages, days, concurrency)
    
    if source_type in ("all", "hotel"):
        results["hotel"] = await collect_hotel(db, pages, days, concurrency)
    
    # 2. 存量检测
    results["existing_check"] = await check_existing_ips(db, concurrency)
    
    # 3. 清理旧日志
    db.cleanup_old_logs()
    
    return results
