"""
IPTV 搜索引擎 v3
==================
核心功能：
- 自定义频道表（用户编辑频道列表）
- IPv4 / IPv6 测速择优
- 同一频道保留最快的 MAX_KEEP 条（默认10）
- 定时更新调度
"""
import re
import aiohttp
import asyncio
import time
import json
import os
from typing import Optional
from dataclasses import dataclass, field, asdict

# ============ 配置 ============
MAX_KEEP = 10          # 同一频道保留最大条数
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.expanduser("~"), ".iptv-data"))
CHANNEL_FILE = os.path.join(DATA_DIR, "channels.json")       # 自定义频道表
SCHEDULE_FILE = os.path.join(DATA_DIR, "schedule.json")      # 定时任务配置
RESULT_FILE = os.path.join(DATA_DIR, "result_cache.json")    # 结果缓存
SPEEDTEST_FILE = os.path.join(DATA_DIR, "speed_cache.json")  # 测速缓存

# ============ 数据模型 ============

@dataclass
class Channel:
    id: str = ""
    name: str = ""               # 频道名称（搜索关键词）
    group: str = "未分组"         # 分组
    enabled: bool = True         # 是否启用
    max_results: int = MAX_KEEP  # 最大保留条数

@dataclass
class PlayEntry:
    name: str = ""
    url: str = ""
    group: str = "未分组"
    source_name: str = ""
    source_type: str = "multicast"  # multicast/hotel/custom
    protocol: str = ""              # ipv4/ipv6/auto
    response_time: int = 0          # 响应时间 ms
    status_code: int = 0
    valid: bool = False

@dataclass
class ScheduleConfig:
    enabled: bool = False
    hour: int = 3           # 默认凌晨3点
    minute: int = 0
    source_type: str = "all"
    ip_version: str = "ipv4"  # ipv4/ipv6/both
    concurrency: int = 20
    timeout: int = 5
    max_keep: int = MAX_KEEP

# ============ 内置搜索源 ============

MULTICAST_IPV4 = [
    {"name": "iptv-org/cn", "url": "https://iptv-org.github.io/iptv/countries/cn.m3u"},
    {"name": "fanmingming", "url": "https://live.fanmingming.com/tv/m3u/ipv6.m3u"},
    {"name": "Meroser/cn", "url": "https://raw.githubusercontent.com/Meroser/iptv/main/cn.m3u"},
]

MULTICAST_IPV6 = [
    {"name": "fanmingming6", "url": "https://live.fanmingming.com/tv/m3u/ipv6.m3u"},
]

HOTEL_SOURCES = [
    {"name": "iptv-org/hotel", "url": "https://iptv-org.github.io/iptv/categories/hotel.m3u"},
    {"name": "fanmingming/h", "url": "https://live.fanmingming.com/tv/m3u/hotel.m3u"},
]

# ============ 频道表管理 ============

def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_channels() -> list[Channel]:
    """加载自定义频道表"""
    _ensure_dir()
    if not os.path.exists(CHANNEL_FILE):
        return _default_channels()
    try:
        with open(CHANNEL_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [Channel(**ch) for ch in data]
    except:
        return _default_channels()

def save_channels(channels: list[Channel]):
    """保存自定义频道表"""
    _ensure_dir()
    with open(CHANNEL_FILE, 'w', encoding='utf-8') as f:
        json.dump([asdict(ch) for ch in channels], f, ensure_ascii=False, indent=2)

def _default_channels() -> list[Channel]:
    """默认频道表"""
    defaults = [
        ("CCTV-1 综合", "央视"),
        ("CCTV-2 财经", "央视"),
        ("CCTV-3 综艺", "央视"),
        ("CCTV-4 中文国际", "央视"),
        ("CCTV-5 体育", "央视"),
        ("CCTV-6 电影", "央视"),
        ("CCTV-7 国防军事", "央视"),
        ("CCTV-8 电视剧", "央视"),
        ("CCTV-9 纪录", "央视"),
        ("CCTV-10 科教", "央视"),
        ("CCTV-11 戏曲", "央视"),
        ("CCTV-12 社会与法", "央视"),
        ("CCTV-13 新闻", "央视"),
        ("CCTV-14 少儿", "央视"),
        ("CCTV-15 音乐", "央视"),
        ("CCTV-17 农业农村", "央视"),
        ("湖南卫视", "卫视"),
        ("浙江卫视", "卫视"),
        ("江苏卫视", "卫视"),
        ("东方卫视", "卫视"),
        ("北京卫视", "卫视"),
        ("广东卫视", "卫视"),
        ("深圳卫视", "卫视"),
        ("山东卫视", "卫视"),
        ("东南卫视", "卫视"),
        ("安徽卫视", "卫视"),
        ("江西卫视", "卫视"),
        ("四川卫视", "卫视"),
        ("重庆卫视", "卫视"),
        ("天津卫视", "卫视"),
        ("辽宁卫视", "卫视"),
        ("湖北卫视", "卫视"),
        ("河南卫视", "卫视"),
        ("河北卫视", "卫视"),
        ("贵州卫视", "卫视"),
        ("云南卫视", "卫视"),
        ("广西卫视", "卫视"),
        ("陕西卫视", "卫视"),
        ("吉林卫视", "卫视"),
        ("甘肃卫视", "卫视"),
        ("黑龙江卫视", "卫视"),
    ]
    channels = []
    for i, (name, group) in enumerate(defaults):
        channels.append(Channel(id=f"ch_{i:03d}", name=name, group=group))
    save_channels(channels)
    return channels

# ============ 定时任务配置 ============

def load_schedule() -> ScheduleConfig:
    _ensure_dir()
    if not os.path.exists(SCHEDULE_FILE):
        return ScheduleConfig()
    try:
        with open(SCHEDULE_FILE, 'r') as f:
            d = json.load(f)
        return ScheduleConfig(**d)
    except:
        return ScheduleConfig()

def save_schedule(cfg: ScheduleConfig):
    _ensure_dir()
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)

# ============ 测速缓存 ============

def load_speed_cache() -> dict:
    """加载测速缓存 {url: {response_time, status_code, valid, timestamp}}"""
    if not os.path.exists(SPEEDTEST_FILE):
        return {}
    try:
        with open(SPEEDTEST_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_speed_cache(cache: dict):
    _ensure_dir()
    with open(SPEEDTEST_FILE, 'w') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

# ============ M3U/TXT 解析 ============

_EXTINF_RE = re.compile(r'#EXTINF:(-?\d+)\s*(.*?)\s*,\s*(.*?)$', re.MULTILINE)
_TAG_RE = re.compile(r'([\w-]+)="([^"]*)"')

def parse_m3u(text: str) -> list[dict]:
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
            if url and name: entries.append({"name": name, "url": url, "group": group})
        i += 1
    return entries

def parse_txt(text: str) -> list[dict]:
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
                        entries.append({"name": parts[0].strip() or "未知", "url": url, "group": "未分组"})
                break
        else:
            m = re.search(r'(rtsp://\S+|rtp://\S+|udp://\S+|https?://\S+)', line)
            if m:
                entries.append({"name": line[:m.start()].strip() or "未知", "url": m.group(1), "group": "未分组"})
    return entries

# ============ 协议检测 ============

def detect_ip_version(url: str) -> str:
    """检测 URL 是 IPv4 还是 IPv6"""
    # 检查是否包含 IPv6 地址（方括号格式）
    if re.search(r'\[[0-9a-fA-F:]+\]', url):
        return "ipv6"
    # 检查是否包含 IPv4 地址
    if re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', url):
        return "ipv4"
    # 域名无法判断，返回 auto
    return "auto"

# ============ 搜索 ============

async def _fetch(session, url: str, timeout: int) -> str:
    h = {'User-Agent': 'VLC/3.0.18', 'Accept': '*/*'}
    async with session.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
        return await r.text(encoding='utf-8', errors='replace')

async def search_all(source_type: str = "all", timeout: int = 15, concurrency: int = 5) -> list[dict]:
    """从内置源搜索，返回原始条目列表"""
    targets = []
    if source_type in ("multicast", "all"):
        for s in MULTICAST_IPV4:
            targets.append({**s, "source_type": "multicast"})
        for s in MULTICAST_IPV6:
            targets.append({**s, "source_type": "multicast"})
    if source_type in ("hotel", "all"):
        for s in HOTEL_SOURCES:
            targets.append({**s, "source_type": "hotel"})

    sem = asyncio.Semaphore(concurrency)
    all_entries = []

    async def _one(s):
        async with sem:
            try:
                async with aiohttp.ClientSession() as session:
                    text = await _fetch(session, s["url"], timeout)
                if '#EXTM3U' in text or '#EXTINF' in text:
                    entries = parse_m3u(text)
                else:
                    entries = parse_txt(text)
                for e in entries:
                    e["source_name"] = s["name"]
                    e["source_type"] = s["source_type"]
                return entries
            except:
                return []

    results = await asyncio.gather(*[_one(t) for t in targets])
    seen_urls = set()
    for r in results:
        for e in r:
            if e["url"] not in seen_urls:
                seen_urls.add(e["url"])
                all_entries.append(e)
    return all_entries

# ============ 按频道表匹配 ============

def match_channels(raw_entries: list[dict], channels: list[Channel]) -> dict:
    """
    将原始条目按频道表匹配分组
    返回: {channel_id: [PlayEntry, ...]}
    """
    enabled = [ch for ch in channels if ch.enabled]
    matched = {ch.id: [] for ch in enabled}

    for raw in raw_entries:
        raw_name = raw.get("name", "")
        for ch in enabled:
            # 模糊匹配：频道名包含关键词或关键词包含频道名
            kw = ch.name.replace(" ", "").lower()
            nm = raw_name.replace(" ", "").lower()
            if kw in nm or nm in kw or kw == nm:
                protocol = detect_ip_version(raw["url"])
                entry = PlayEntry(
                    name=raw_name,
                    url=raw["url"],
                    group=ch.group,
                    source_name=raw.get("source_name", ""),
                    source_type=raw.get("source_type", "multicast"),
                    protocol=protocol,
                )
                matched[ch.id].append(entry)
                break
    return matched

# ============ 测速 ============

async def check_single(session, url: str, timeout: int) -> dict:
    """测速单个地址，返回 {url, valid, status_code, response_time}"""
    start = time.monotonic()
    res = {"url": url, "valid": False, "status_code": 0, "response_time": 0, "error": ""}
    h = {'User-Agent': 'VLC/3.0.18', 'Accept': '*/*', 'Range': 'bytes=0-1023'}
    try:
        try:
            r = await session.head(url, headers=h, timeout=aiohttp.ClientTimeout(total=timeout), ssl=False, allow_redirects=True)
            elapsed = int((time.monotonic() - start) * 1000)
            res["status_code"] = r.status
            res["response_time"] = elapsed
            if r.status < 400:
                res["valid"] = True
                return res
        except:
            pass
        # GET 降级
        start = time.monotonic()
        async with session.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=timeout), ssl=False, allow_redirects=True) as r:
            await r.content.read(512)
            elapsed = int((time.monotonic() - start) * 1000)
            res["status_code"] = r.status
            res["response_time"] = elapsed
            if r.status < 400:
                res["valid"] = True
            else:
                res["error"] = f"HTTP {r.status}"
    except asyncio.TimeoutError:
        res["response_time"] = int((time.monotonic() - start) * 1000)
        res["error"] = "timeout"
    except Exception as e:
        res["response_time"] = int((time.monotonic() - start) * 1000)
        res["error"] = str(e)[:80]
    return res

async def speed_test(entries: list[PlayEntry], concurrency: int = 20, timeout: int = 5,
                     ip_version: str = "ipv4") -> list[PlayEntry]:
    """
    并发测速，按 IP 版本过滤，同一频道保留最快的 MAX_KEEP 条
    ip_version: ipv4 / ipv6 / both
    """
    # 先按 IP 版本过滤
    filtered = []
    for e in entries:
        if ip_version == "both":
            filtered.append(e)
        elif ip_version == "ipv4" and e.protocol in ("ipv4", "auto"):
            filtered.append(e)
        elif ip_version == "ipv6" and e.protocol in ("ipv6", "auto"):
            filtered.append(e)
        elif e.protocol == "auto":
            filtered.append(e)  # 域名无法判断时保留

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _check(e):
        async with sem:
            result = await check_single(session, e.url, timeout)
            e.valid = result["valid"]
            e.response_time = result["response_time"]
            e.status_code = result["status_code"]
            return e

    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[_check(e) for e in filtered])

    return [r for r in results if r.valid]

def keep_fastest(matched: dict, max_keep: int = MAX_KEEP) -> list[PlayEntry]:
    """
    对每个频道的匹配结果按响应时间排序，保留最快的 max_keep 条
    """
    final = []
    for ch_id, entries in matched.items():
        if not entries:
            continue
        # 按响应时间排序
        sorted_entries = sorted(entries, key=lambda e: e.response_time if e.response_time > 0 else 99999)
        # 保留最快的
        kept = sorted_entries[:max_keep]
        final.extend(kept)
    return final

# ============ 完整流程 ============

async def run_full_pipeline(
    channels: list[Channel],
    source_type: str = "all",
    ip_version: str = "ipv4",
    concurrency: int = 20,
    timeout: int = 5,
    max_keep: int = MAX_KEEP,
    search_timeout: int = 15,
) -> dict:
    """
    完整流程：搜索 → 频道匹配 → IPv4/IPv6 过滤 → 测速 → 择优
    返回: {entries: [PlayEntry], stats: {total, matched, valid, kept}, channels: {ch_id: count}}
    """
    # 1. 搜索
    raw = await search_all(source_type=source_type, timeout=search_timeout)

    # 2. 频道匹配
    matched = match_channels(raw, channels)
    all_matched = []
    for ch_id, entries in matched.items():
        all_matched.extend(entries)

    channel_stats = {ch_id: len(entries) for ch_id, entries in matched.items()}

    # 3. 测速
    tested = await speed_test(all_matched, concurrency=concurrency, timeout=timeout, ip_version=ip_version)

    # 4. 重新按频道分组并择优
    tested_by_ch = {}
    for e in tested:
        for ch in channels:
            if ch.enabled and (ch.name.replace(" ", "").lower() in e.name.replace(" ", "").lower() or
                               e.name.replace(" ", "").lower() in ch.name.replace(" ", "").lower()):
                tested_by_ch.setdefault(ch.id, []).append(e)
                break

    final = []
    final_stats = {}
    for ch_id, entries in tested_by_ch.items():
        sorted_e = sorted(entries, key=lambda x: x.response_time)
        kept = sorted_e[:max_keep]
        final.extend(kept)
        final_stats[ch_id] = len(kept)

    # 5. 更新缓存
    cache = load_speed_cache()
    for e in final:
        cache[e.url] = {
            "response_time": e.response_time,
            "status_code": e.status_code,
            "valid": e.valid,
            "protocol": e.protocol,
            "timestamp": time.time()
        }
    save_speed_cache(cache)

    return {
        "entries": final,
        "stats": {
            "total_searched": len(raw),
            "total_matched": len(all_matched),
            "total_tested": len(tested),
            "total_kept": len(final),
            "ip_version": ip_version,
            "max_keep": max_keep,
        },
        "channel_stats": final_stats,
    }

# ============ 结果持久化 ============

def save_result(entries: list[PlayEntry]):
    _ensure_dir()
    data = [{
        "name": e.name, "url": e.url, "group": e.group,
        "source_name": e.source_name, "source_type": e.source_type,
        "protocol": e.protocol, "response_time": e.response_time,
        "status_code": e.status_code, "valid": e.valid,
    } for e in entries]
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_result() -> list[dict]:
    if not os.path.exists(RESULT_FILE):
        return []
    try:
        with open(RESULT_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

# ============ 生成导出文件 ============

def gen_m3u(entries: list) -> str:
    lines = ['#EXTM3U']
    for e in entries:
        name = e.name if hasattr(e, 'name') else e.get('name', '')
        url = e.url if hasattr(e, 'url') else e.get('url', '')
        group = e.group if hasattr(e, 'group') else e.get('group', '未分组')
        lines.append(f'#EXTINF:-1 group-title="{group}",{name}')
        lines.append(url)
    return '\n'.join(lines)

def gen_txt(entries: list, sep: str = ",") -> str:
    lines = ['# IPTV 频道列表', f'# 生成时间: {time.strftime("%Y-%m-%d %H:%M:%S")}', '']
    for e in entries:
        name = e.name if hasattr(e, 'name') else e.get('name', '')
        url = e.url if hasattr(e, 'url') else e.get('url', '')
        lines.append(f'{name}{sep}{url}')
    return '\n'.join(lines)
