"""
IPTV 搜索引擎 - 组播源 + 酒店源
==================================
核心流程：搜索(M3U/TXT) → 验证可用性 → 去重 → 导出 M3U + TXT
"""
import re
import aiohttp
import asyncio
from typing import Optional
from dataclasses import dataclass

# ============ 内置搜索目标 ============

MULTICAST_SOURCES = [
    {"name": "iptv-org/cn",  "url": "https://iptv-org.github.io/iptv/countries/cn.m3u"},
    {"name": "iptv-org/all", "url": "https://iptv-org.github.io/iptv/index.m3u"},
    {"name": "fanmingming",   "url": "https://live.fanmingming.com/tv/m3u/Global.m3u"},
    {"name": "fanmingming6",  "url": "https://live.fanmingming.com/tv/m3u/ipv6.m3u"},
    {"name": "Meroser/cn",   "url": "https://raw.githubusercontent.com/Meroser/iptv/main/cn.m3u"},
    {"name": "Meroser/all",  "url": "https://raw.githubusercontent.com/Meroser/iptv/main/all.m3u"},
]

HOTEL_SOURCES = [
    {"name": "iptv-org/hotel", "url": "https://iptv-org.github.io/iptv/categories/hotel.m3u"},
    {"name": "fanmingming/h",  "url": "https://live.fanmingming.com/tv/m3u/hotel.m3u"},
    {"name": "iptv-org/hotel-raw", "url": "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/hotel.m3u"},
]


@dataclass
class Entry:
    name: str
    url: str
    group: str = "未分组"
    source_name: str = ""
    source_type: str = "multicast"
    is_valid: bool = False
    response_time: int = 0  # ms


# ============ 解析 ============

_EXTINF_RE = re.compile(r'#EXTINF:(-?\d+)\s*(.*?)\s*,\s*(.*?)$', re.MULTILINE)
_TAG_RE = re.compile(r'([\w-]+)="([^"]*)"')


def parse_m3u(text: str) -> list[Entry]:
    entries, lines = [], text.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            name, url, group = "", "", "未分组"
            m = _EXTINF_RE.match(line)
            if m:
                name = m.group(3).strip()
                for tag in _TAG_RE.finditer(m.group(2)):
                    k, v = tag.groups()
                    if k.lower() == 'group-title': group = v
            else:
                c = line.find(',')
                if c > 0: name = line[c+1:].strip()
            if i + 1 < len(lines):
                nxt = lines[i+1].strip()
                if not nxt.startswith('#') and nxt: url = nxt; i += 1
            if url and name: entries.append(Entry(name=name, url=url, group=group))
        i += 1
    return entries


def parse_txt(text: str) -> list[Entry]:
    entries = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'): continue
        for sep in [',', '|', '\t']:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    url = parts[1].strip()
                    if url.startswith(('http://','https://','rtsp://','rtp://','udp://','mms://')):
                        entries.append(Entry(name=parts[0].strip() or "未知", url=url))
                break
        else:
            m = re.search(r'(rtsp://\S+|rtp://\S+|udp://\S+|https?://\S+)', line)
            if m:
                entries.append(Entry(name=line[:m.start()].strip() or "未知", url=m.group(1)))
    return entries


# ============ 搜索 ============

async def _fetch(url: str, timeout: int) -> str:
    h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept': '*/*'}
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
            return await r.text(encoding='utf-8', errors='replace')


async def search(source_type: str = "all", custom_urls: list[str] = None,
                  timeout: int = 15, concurrency: int = 5) -> list[Entry]:
    """从内置源或自定义 URL 搜索，返回去重后的播放列表"""
    targets = []
    if custom_urls:
        targets = [{"name": f"自定义-{u[:40]}", "url": u, "source_type": "custom"} for u in custom_urls]
    else:
        if source_type in ("multicast", "all"): targets.extend({**s, "source_type": "multicast"} for s in MULTICAST_SOURCES)
        if source_type in ("hotel", "all"):     targets.extend({**s, "source_type": "hotel"} for s in HOTEL_SOURCES)

    sem = asyncio.Semaphore(concurrency)

    async def _one(t):
        async with sem:
            try:
                text = await _fetch(t["url"], timeout)
                if '#EXTM3U' in text or '#EXTINF' in text:
                    entries = parse_m3u(text)
                else:
                    entries = parse_txt(text)
                for e in entries:
                    e.source_name = t["name"]
                    e.source_type = t.get("source_type", "multicast")
                return entries
            except:
                return []

    results = await asyncio.gather(*[_one(t) for t in targets])
    seen, all_entries = set(), []
    for r in results:
        for e in r:
            if e.url not in seen:
                seen.add(e.url)
                all_entries.append(e)
    return all_entries


# ============ 验证 ============

async def check_url(url: str, timeout: int = 5) -> dict:
    """检测播放地址可用性，HEAD→GET降级"""
    h = {'User-Agent': 'VLC/3.0.18 LibVLC/3.0.18', 'Accept': '*/*'}
    res = {"url": url, "valid": False, "status_code": 0, "response_time": 0, "error": ""}
    try:
        async with aiohttp.ClientSession() as s:
            try:
                r = await s.head(url, headers=h, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True)
                res["status_code"] = r.status
                if r.status < 400: res["valid"] = True
                else: res["error"] = f"HTTP {r.status}"
            except:
                r = await s.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True)
                res["status_code"] = r.status
                await r.content.read(1024)
                if r.status < 400: res["valid"] = True
                else: res["error"] = f"HTTP {r.status}"
    except asyncio.TimeoutError: res["error"] = "timeout"
    except Exception as e: res["error"] = str(e)[:100]
    return res


async def validate(entries: list[Entry], concurrency: int = 20, timeout: int = 5) -> list[Entry]:
    """并发验证，返回有效条目"""
    sem = asyncio.Semaphore(concurrency)

    async def _check(e):
        async with sem:
            r = await check_url(e.url, timeout)
            e.is_valid = r["valid"]
            e.response_time = r.get("response_time", 0)
            return e if r["valid"] else None

    results = await asyncio.gather(*[_check(e) for e in entries])
    return [r for r in results if r is not None]


# ============ 生成 ============

def gen_m3u(entries: list[Entry]) -> str:
    lines = ['#EXTM3U']
    for e in entries:
        lines.append(f'#EXTINF:-1 group-title="{e.group}",{e.name}')
        lines.append(e.url)
    return '\n'.join(lines)


def gen_txt(entries: list[Entry], sep: str = ",") -> str:
    return '\n'.join(f'{e.name}{sep}{e.url}' for e in entries)
