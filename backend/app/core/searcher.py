"""
IPTV 搜索引擎 v3.2
====================
参考 iptv-api (HerbertHe/iptv-sources) 输出格式升级：
- 分类模板：按频道类型分组（央视/卫视/4K/财经/新闻/体育等）
- M3U输出：增加 tvg-name、tvg-logo、x-tvg-url
- TXT输出：emoji 分类头
- 多源聚合：组播 + 酒店 + 订阅源
- 分辨率 + 速率过滤
"""
import re
import aiohttp
import asyncio
import time
import json
import os
import subprocess
from typing import Optional
from dataclasses import dataclass, field, asdict

# 导入采集器模块（存量校验 + SQLite）
from app.core.collector import IpvDB, CHECK_TIMEOUT, full_collection

# ============ 配置 ============
MAX_KEEP = 10
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.expanduser("~"), ".iptv-data"))
CHANNEL_FILE = os.path.join(DATA_DIR, "channels.json")
SCHEDULE_FILE = os.path.join(DATA_DIR, "schedule.json")
RESULT_FILE = os.path.join(DATA_DIR, "result_cache.json")
SPEEDTEST_FILE = os.path.join(DATA_DIR, "speed_cache.json")
SUBSCRIBE_FILE = os.path.join(DATA_DIR, "subscribe.txt")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# ============ M3U 频道图标（fanmingming/live）============
TV_LOGO_BASE = "https://raw.githubusercontent.com/fanmingming/live/main/tv"
TV_EPG_URL = "https://raw.githubusercontent.com/fanmingming/live/main/e.xml"

# ============ 分类模板（参考 iptv-api config/demo.txt）============
CHANNEL_CATEGORIES = {
    "📺央视频道": [
        "CCTV", "CGTN", "CETV", "央视", "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5",
        "CCTV6", "CCTV7", "CCTV8", "CCTV9", "CCTV10", "CCTV11", "CCTV12",
        "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17", "CCTV5+", "CCTV4K",
        "CCTV5K", "CCTV-1", "CCTV-2", "CCTV-3", "CCTV-4", "CCTV-5", "CCTV-6",
        "CCTV-7", "CCTV-8", "CCTV-9", "CCTV-10", "CCTV-11", "CCTV-12", "CCTV-13",
        "CCTV-14", "CCTV-15", "CCTV-16", "CCTV-17", "CCTV-5+", "CCTV-4K"
    ],
    "📡卫视频道": [
        "卫视", "湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "北京卫视",
        "广东卫视", "深圳卫视", "山东卫视", "东南卫视", "安徽卫视", "江西卫视",
        "四川卫视", "重庆卫视", "天津卫视", "辽宁卫视", "湖北卫视", "河南卫视",
        "河北卫视", "贵州卫视", "云南卫视", "广西卫视", "陕西卫视", "吉林卫视",
        "甘肃卫视", "黑龙江卫视", "山西卫视", "宁夏卫视", "新疆卫视", "西藏卫视",
        "内蒙古卫视", "海南卫视", "厦门卫视", "珠江频道", "大湾区卫视"
    ],
    "🆕4K频道": [
        "4K", "超高清", "UHD", "CCTV4K", "东方卫视4K", "江苏卫视4K",
        "浙江卫视4K", "山东卫视4K", "湖南卫视4K", "四川卫视4K", "广东卫视4K", "深圳卫视4K"
    ],
    "☘️地方频道": [
        "地方", "都市", "新闻", "公共", "少儿", "生活", "法制", "影视",
        "体育", "教育", "旅游", "气象", "戏曲", "家政", "广场", "购物"
    ],
    "💰财经频道": [
        "财经", "证券", "东方财经", "第一财经", "北京财经", "Now财经台",
        "非凡商业台", "赢点台", "财富天下"
    ],
    "✉新闻频道": [
        "新闻", "资讯", "TVBS新闻", "民视新闻", "台视新闻", "中时新闻",
        "三立新闻寰宇新闻", "鏡新聞", "朝日新聞", "日テレNEWS", "SkyNews",
        "NHK World", "LiveNOW", "CNN", "BBC", "凤凰资讯", "凤凰中文", "凤凰香港"
    ],
    "🌊港台·海外": [
        "香港", "澳门", "TVB", "凤凰", "华视", "中视", "民视", "台视",
        "公视", "寰宇", "博斯", "ESPN", "Discovery", "National Geographic",
        "CNN", "BBC", "HBO", "FOX", "Disney", "Nickelodeon", "Cartoon Network"
    ],
    "🎬电影频道": [
        "电影", "影院", "CHC", "纬来电影", "东森电影", "龙祥电影",
        "好莱坞", "天映经典", "卫视电影", "美亚电影", "奇迹电影", "金马影院"
    ],
    "🏀体育频道": [
        "体育", "足球", "篮球", "排球", "网球", "高尔夫", "搏击",
        "赛车", "围棋", "象棋", "钓鱼", "武术", "搏击", "JJ体育",
        "ESPN", "Star Sports", "纬来体育", "DAZN", "NBA TV"
    ],
    "🎮游戏频道": [
        "游戏", "电竞", "GAME"
    ],
    "🎵音乐频道": [
        "音乐", "MTV", "Channel V", "MCM"
    ],
    "🧒动画频道": [
        "动画", "卡通", "少儿", "迪士尼", "Nickelodeon", "Cartoon Network",
        "Baby TV", "YOYO", "MOMO", "东森幼幼"
    ],
    "🏛经典剧场": [
        "剧场", "经典", "港剧", "古装", "武侠"
    ],
    "🧑明星频道": [
        "明星", "娱乐", "综艺"
    ],
}


def classify_channel(name: str) -> str:
    """根据频道名称自动分类"""
    for category, keywords in CHANNEL_CATEGORIES.items():
        for kw in keywords:
            if kw in name:
                return category
    return "📡卫视频道"  # 默认归类为卫视


def get_channel_logo(name: str) -> str:
    """获取频道图标 URL"""
    # 清理频道名称作为文件名
    clean = re.sub(r'[^\w\-]', '', name)
    return f"{TV_LOGO_BASE}/{clean}.png"


# ============ 数据模型 ============

@dataclass
class Channel:
    id: str = ""
    name: str = ""
    group: str = "未分组"
    enabled: bool = True
    max_results: int = MAX_KEEP


@dataclass
class PlayEntry:
    name: str = ""
    url: str = ""
    group: str = "未分组"
    source_name: str = ""
    source_type: str = "multicast"
    protocol: str = ""
    response_time: int = 0
    status_code: int = 0
    valid: bool = False
    resolution: str = ""       # 分辨率 (如 1920x1080)
    speed: float = 0.0         # 速率 M/s


@dataclass
class ScheduleConfig:
    enabled: bool = False
    hour: int = 3
    minute: int = 0
    source_type: str = "all"
    ip_version: str = "ipv4"
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


def get_active_sources(source_type: str = "all") -> list[dict]:
    """从数据源管理中获取启用的数据源，加上订阅源"""
    targets = []

    # 1. 从数据源管理获取
    try:
        from app.api.sources import load_sources
        sources = load_sources()
        active = [s for s in sources if s.enabled]
        if source_type == "multicast":
            active = [s for s in active if s.type == "multicast"]
        elif source_type == "hotel":
            active = [s for s in active if s.type == "hotel"]
        for s in active:
            targets.append({"name": s.name, "url": s.url, "source_type": s.type if s.type != "custom" else "multicast"})
    except:
        pass

    # 2. 从订阅文件获取
    if source_type in ("all", "multicast"):
        try:
            if os.path.exists(SUBSCRIBE_FILE):
                with open(SUBSCRIBE_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        url = line.strip()
                        if url and not url.startswith('#'):
                            targets.append({"name": "subscribe", "url": url, "source_type": "multicast"})
        except:
            pass

    # 3. 回退到硬编码
    if not targets:
        targets = _fallback_sources(source_type)

    return targets


def _fallback_sources(source_type: str) -> list[dict]:
    """回退到硬编码默认源"""
    result = []
    if source_type in ("multicast", "all"):
        for s in MULTICAST_IPV4 + MULTICAST_IPV6:
            result.append({**s, "source_type": "multicast"})
    if source_type in ("hotel", "all"):
        for s in HOTEL_SOURCES:
            result.append({**s, "source_type": "hotel"})
    return result


# ============ 频道表管理 ============

def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_channels() -> list[Channel]:
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
    _ensure_dir()
    with open(CHANNEL_FILE, 'w', encoding='utf-8') as f:
        json.dump([asdict(ch) for ch in channels], f, ensure_ascii=False, indent=2)


def _default_channels() -> list[Channel]:
    """默认频道表 - 按分类组织"""
    defaults = [
        # 央视
        ("CCTV-1 综合", "📺央视频道"), ("CCTV-2 财经", "📺央视频道"),
        ("CCTV-3 综艺", "📺央视频道"), ("CCTV-4 中文国际", "📺央视频道"),
        ("CCTV-5 体育", "📺央视频道"), ("CCTV-6 电影", "📺央视频道"),
        ("CCTV-7 国防军事", "📺央视频道"), ("CCTV-8 电视剧", "📺央视频道"),
        ("CCTV-9 纪录", "📺央视频道"), ("CCTV-10 科教", "📺央视频道"),
        ("CCTV-11 戏曲", "📺央视频道"), ("CCTV-12 社会与法", "📺央视频道"),
        ("CCTV-13 新闻", "📺央视频道"), ("CCTV-14 少儿", "📺央视频道"),
        ("CCTV-15 音乐", "📺央视频道"), ("CCTV-17 农业农村", "📺央视频道"),
        # 卫视
        ("湖南卫视", "📡卫视频道"), ("浙江卫视", "📡卫视频道"),
        ("江苏卫视", "📡卫视频道"), ("东方卫视", "📡卫视频道"),
        ("北京卫视", "📡卫视频道"), ("广东卫视", "📡卫视频道"),
        ("深圳卫视", "📡卫视频道"), ("山东卫视", "📡卫视频道"),
        ("东南卫视", "📡卫视频道"), ("安徽卫视", "📡卫视频道"),
        ("江西卫视", "📡卫视频道"), ("四川卫视", "📡卫视频道"),
        ("重庆卫视", "📡卫视频道"), ("天津卫视", "📡卫视频道"),
        ("辽宁卫视", "📡卫视频道"), ("湖北卫视", "📡卫视频道"),
        ("河南卫视", "📡卫视频道"), ("河北卫视", "📡卫视频道"),
        ("贵州卫视", "📡卫视频道"), ("云南卫视", "📡卫视频道"),
        ("广西卫视", "📡卫视频道"), ("陕西卫视", "📡卫视频道"),
        ("吉林卫视", "📡卫视频道"), ("甘肃卫视", "📡卫视频道"),
        ("黑龙江卫视", "📡卫视频道"), ("山西卫视", "📡卫视频道"),
        ("内蒙古卫视", "📡卫视频道"), ("宁夏卫视", "📡卫视频道"),
        ("新疆卫视", "📡卫视频道"), ("西藏卫视", "📡卫视频道"),
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

_EXTINF_RE = re.compile(r'#EXTINF:(-?\\d+)\\s*(.*?)\\s*,\\s*(.*?)$', re.MULTILINE)
_TAG_RE = re.compile(r'([\\w-]+)=\"([^\"]*)\"')


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
                    if k.lower() == 'group-title':
                        group = v
            else:
                c = line.find(',')
                if c > 0:
                    name = line[c+1:].strip()
            if i + 1 < len(lines):
                nxt = lines[i+1].strip()
                if not nxt.startswith('#') and nxt:
                    url = nxt
                    i += 1
            if url and name:
                entries.append({"name": name, "url": url, "group": group})
        i += 1
    return entries


def parse_txt(text: str) -> list[dict]:
    entries = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        for sep in [',', '|', '\t']:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    url = parts[1].strip()
                    if url.startswith(('http://', 'https://', 'rtsp://', 'rtp://', 'udp://', 'mms://')):
                        entries.append({"name": parts[0].strip() or "未知", "url": url, "group": "未分组"})
                break
        else:
            m = re.search(r'(rtsp://\\S+|rtp://\\S+|udp://\\S+|https?://\\S+)', line)
            if m:
                entries.append({"name": line[:m.start()].strip() or "未知", "url": m.group(1), "group": "未分组"})
    return entries


# ============ 协议检测 ============

def detect_ip_version(url: str) -> str:
    if re.search(r'\\[[0-9a-fA-F:]+\\]', url):
        return "ipv6"
    if re.search(r'\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}', url):
        return "ipv4"
    return "auto"


# ============ 搜索 ============

async def _fetch(session, url: str, timeout: int) -> str:
    h = {'User-Agent': 'VLC/3.0.18', 'Accept': '*/*'}
    async with session.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
        return await r.text(encoding='utf-8', errors='replace')


async def search_all(source_type: str = "all", timeout: int = 15, concurrency: int = 5) -> list[dict]:
    """多源搜索：组播 + 酒店 + 订阅源"""
    targets = get_active_sources(source_type)
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
                    # 如果源已经有 group 且不是默认值，保留；否则自动分类
                    if e.get("group", "未分组") == "未分组":
                        e["group"] = classify_channel(e["name"])
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
    enabled = [ch for ch in channels if ch.enabled]
    matched = {ch.id: [] for ch in enabled}

    for raw in raw_entries:
        raw_name = raw.get("name", "")
        for ch in enabled:
            kw = ch.name.replace(" ", "").lower()
            nm = raw_name.replace(" ", "").lower()
            if kw in nm or nm in kw or kw == nm:
                protocol = detect_ip_version(raw["url"])
                # 使用频道表的 group（已包含 emoji 分类）
                group = ch.group if ch.group and ch.group != "未分组" else raw.get("group", classify_channel(raw_name))
                entry = PlayEntry(
                    name=raw_name,
                    url=raw["url"],
                    group=group,
                    source_name=raw.get("source_name", ""),
                    source_type=raw.get("source_type", "multicast"),
                    protocol=protocol,
                )
                matched[ch.id].append(entry)
                break
    return matched


# ============ 测速 ============

async def check_single(session, url: str, timeout: int) -> dict:
    """测速单个地址，返回 {valid, status_code, response_time, speed, resolution}"""
    start = time.monotonic()
    res = {"valid": False, "status_code": 0, "response_time": 0, "speed": 0.0, "resolution": "", "error": ""}
    h = {'User-Agent': 'VLC/3.0.18', 'Accept': '*/*', 'Range': 'bytes=0-4095'}
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
            data = await r.content.read(1024)
            elapsed = int((time.monotonic() - start) * 1000)
            res["status_code"] = r.status
            res["response_time"] = elapsed
            if r.status < 400:
                res["valid"] = True
                # 估算速率
                if elapsed > 0:
                    res["speed"] = round(len(data) / elapsed / 1000, 2)  # KB/s
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
                     ip_version: str = "ipv4", min_speed: float = 0.0) -> list[PlayEntry]:
    """并发测速，支持 IP 版本过滤和最低速率过滤"""
    filtered = []
    for e in entries:
        if ip_version == "both":
            filtered.append(e)
        elif ip_version == "ipv4" and e.protocol in ("ipv4", "auto"):
            filtered.append(e)
        elif ip_version == "ipv6" and e.protocol in ("ipv6", "auto"):
            filtered.append(e)

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _check(e):
        async with sem:
            result = await check_single(session, e.url, timeout)
            e.valid = result["valid"]
            e.response_time = result["response_time"]
            e.status_code = result["status_code"]
            e.speed = result.get("speed", 0.0)
            return e

    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[_check(e) for e in filtered])

    # 过滤不满足最低速率的
    if min_speed > 0:
        return [r for r in results if r.valid and (r.speed == 0 or r.speed >= min_speed)]
    return [r for r in results if r.valid]


# ============ 存量 IP 校验（参考群晖 3 轮重试逻辑）============

async def check_existing_entries(db: IpvDB, entries: list[PlayEntry], 
                                  concurrency: int = 20, timeout: int = CHECK_TIMEOUT) -> dict:
    """
    存量 IP 检测 — 参考群晖 cqshushu/iptv-spider 逻辑：
    1. 一轮检测所有 IP
    2. 失效 IP 进行第 2 轮重试
    3. 仍失效的进行第 3 轮重试
    4. 超过阈值标记为暂时失效
    """
    total = len(entries)
    if total == 0:
        return {"total": 0, "valid": 0, "failed": 0, "retried": 0}
    
    sem = asyncio.Semaphore(concurrency)
    
    async def _check_one(e):
        async with sem:
            valid, rt, speed = await check_single(aiohttp.ClientSession(), e.url, timeout)
            e.valid = valid
            e.response_time = rt
            e.speed = speed
            return e
    
    # 第 1 轮
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[_check_one(e) for e in entries])
    
    valid_entries = [e for e in results if e.valid]
    failed_entries = [e for e in results if not e.valid]
    
    # 第 2 轮重试
    if failed_entries:
        await asyncio.sleep(1)
        async with aiohttp.ClientSession() as session:
            retry2 = await asyncio.gather(*[_check_one(e) for e in failed_entries])
        still_failed = [e for e in retry2 if not e.valid]
        valid_entries.extend([e for e in retry2 if e.valid])
        failed_entries = still_failed
    
    # 第 3 轮重试
    if failed_entries:
        await asyncio.sleep(2)
        async with aiohttp.ClientSession() as session:
            retry3 = await asyncio.gather(*[_check_one(e) for e in failed_entries])
        valid_entries.extend([e for e in retry3 if e.valid])
    
    return {
        "total": total,
        "valid": len(valid_entries),
        "failed": total - len(valid_entries),
        "entries": valid_entries,
    }


def keep_fastest(matched: dict, max_keep: int = MAX_KEEP) -> list[PlayEntry]:
    final = []
    for ch_id, entries in matched.items():
        if not entries:
            continue
        sorted_entries = sorted(entries, key=lambda e: e.response_time if e.response_time > 0 else 99999)
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
    min_speed: float = 0.0,
    enable_existing_check: bool = True,  # 是否启用存量校验
    collect_pages: int = 5,              # 采集页数
    collect_days: int = 7,               # 采集最近 N 天
) -> dict:
    """
    完整流程（v4 优化）：
    1. 采集新源（组播/酒店 API）
    2. 订阅源聚合（M3U/TXT）
    3. 频道匹配
    4. 测速（支持速率过滤）
    5. 存量 IP 校验（3轮重试）
    6. 择优导出
    """
    db = IpvDB()
    collection_stats = {}
    
    # 1. 采集新源（组播/酒店 API）
    if source_type in ("all", "multicast", "hotel"):
        collect_result = await full_collection(
            pages=collect_pages, 
            days=collect_days,
            concurrency=concurrency,
            source_type=source_type
        )
        collection_stats = {
            "multicast_found": collect_result.get("multicast", {}).found_count if "multicast" in collect_result else 0,
            "multicast_valid": collect_result.get("multicast", {}).valid_count if "multicast" in collect_result else 0,
            "hotel_found": collect_result.get("hotel", {}).found_count if "hotel" in collect_result else 0,
            "hotel_valid": collect_result.get("hotel", {}).valid_count if "hotel" in collect_result else 0,
            "existing_check": collect_result.get("existing_check", {}),
        }
    
    # 2. 订阅源聚合
    raw = await search_all(source_type=source_type, timeout=search_timeout)

    # 3. 频道匹配
    matched = match_channels(raw, channels)
    all_matched = []
    for ch_id, entries in matched.items():
        all_matched.extend(entries)

    # 4. 测速（支持速率过滤）
    tested = await speed_test(all_matched, concurrency=concurrency, timeout=timeout,
                               ip_version=ip_version, min_speed=min_speed)

    # 5. 存量 IP 校验（3轮重试）
    existing_check_result = {}
    if enable_existing_check:
        existing_entries = [PlayEntry(name=e.name, url=e.url, group=e.group) for e in tested if e.valid]
        existing_check_result = await check_existing_entries(db, existing_entries, concurrency, timeout)
        tested = existing_check_result.get("entries", tested)

    # 6. 择优
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

    # 7. 更新缓存
    cache = load_speed_cache()
    for e in final:
        cache[e.url] = {
            "response_time": e.response_time,
            "status_code": e.status_code,
            "valid": e.valid,
            "protocol": e.protocol,
            "speed": e.speed,
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
            "min_speed": min_speed,
            "collection": collection_stats,
            "existing_check": existing_check_result,
        },
        "channel_stats": final_stats,
    }


# ============ 生成输出文件（参考 iptv-api 格式）============

def gen_m3u(entries: list, update_time: str = None) -> str:
    """
    生成标准 M3U 格式（参考 iptv-api 输出格式）
    #EXTM3U x-tvg-url="..."
    #EXTINF:-1 tvg-name="CCTV1" tvg-logo="..." group-title="📺央视频道",CCTV1
    url
    """
    if update_time is None:
        update_time = time.strftime("%Y-%m-%d %H:%M:%S")

    lines = [f'#EXTM3U x-tvg-url="{TV_EPG_URL}"']

    # 更新时间行
    lines.append(f'#EXTINF:-1 tvg-name="更新时间" tvg-logo="" group-title="🕘️更新时间",{update_time}')
    lines.append("")

    # 按分组组织
    by_group = {}
    for e in entries:
        g = e.group if hasattr(e, 'group') else e.get('group', '📡卫视频道')
        if g not in by_group:
            by_group[g] = []
        by_group[g].append(e)

    # 按分类顺序输出
    group_order = ["🕘️更新时间", "📺央视频道", "📡卫视频道", "🆕4K频道", "☘️地方频道",
                   "💰财经频道", "✉新闻频道", "🌊港台·海外", "🎬电影频道", "🏀体育频道",
                   "🎮游戏频道", "🎵音乐频道", "🧒动画频道", "🏛经典剧场", "🧑明星频道"]

    for group in group_order:
        if group in by_group:
            for e in by_group[group]:
                name = e.name if hasattr(e, 'name') else e.get('name', '')
                url = e.url if hasattr(e, 'url') else e.get('url', '')
                logo = get_channel_logo(name)
                lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}')
                lines.append(url)
            # 删除已处理的
            del by_group[group]

    # 输出未在预定义分类中的组
    for group, items in by_group.items():
        for e in items:
            name = e.name if hasattr(e, 'name') else e.get('name', '')
            url = e.url if hasattr(e, 'url') else e.get('url', '')
            logo = get_channel_logo(name)
            lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}')
            lines.append(url)

    return '\n'.join(lines)


def gen_txt(entries: list, update_time: str = None) -> str:
    """
    生成标准 TXT 格式（参考 iptv-api 输出格式）
    🕘️更新时间,#genre#
    更新时间,url

    📺央视频道,#genre#
    CCTV1,url1
    CCTV1,url2
    """
    if update_time is None:
        update_time = time.strftime("%Y-%m-%d %H:%M:%S")

    lines = []

    # 按分组组织
    by_group = {}
    for e in entries:
        g = e.group if hasattr(e, 'group') else e.get('group', '📡卫视频道')
        if g not in by_group:
            by_group[g] = []
        by_group[g].append(e)

    # 按分类顺序输出
    group_order = ["🕘️更新时间", "📺央视频道", "📡卫视频道", "🆕4K频道", "☘️地方频道",
                   "💰财经频道", "✉新闻频道", "🌊港台·海外", "🎬电影频道", "🏀体育频道",
                   "🎮游戏频道", "🎵音乐频道", "🧒动画频道", "🏛经典剧场", "🧑明星频道"]

    # 更新时间
    lines.append("🕘️更新时间,#genre#")
    lines.append(f"{update_time},")
    lines.append("")

    for group in group_order:
        if group in by_group and group != "🕘️更新时间":
            lines.append(f"{group},#genre#")
            for e in by_group[group]:
                name = e.name if hasattr(e, 'name') else e.get('name', '')
                url = e.url if hasattr(e, 'url') else e.get('url', '')
                lines.append(f"{name},{url}")
            lines.append("")
            del by_group[group]

    # 输出未在预定义分类中的组
    for group, items in by_group.items():
        if items:
            lines.append(f"{group},#genre#")
            for e in items:
                name = e.name if hasattr(e, 'name') else e.get('name', '')
                url = e.url if hasattr(e, 'url') else e.get('url', '')
                lines.append(f"{name},{url}")
            lines.append("")

    return '\n'.join(lines)


# ============ 结果持久化 ============

def save_result(entries: list):
    _ensure_dir()
    data = [{
        "name": e.name if hasattr(e, 'name') else e.get('name', ''),
        "url": e.url if hasattr(e, 'url') else e.get('url', ''),
        "group": e.group if hasattr(e, 'group') else e.get('group', ''),
        "source_name": e.source_name if hasattr(e, 'source_name') else e.get('source_name', ''),
        "source_type": e.source_type if hasattr(e, 'source_type') else e.get('source_type', ''),
        "protocol": e.protocol if hasattr(e, 'protocol') else e.get('protocol', ''),
        "response_time": e.response_time if hasattr(e, 'response_time') else e.get('response_time', 0),
        "speed": e.speed if hasattr(e, 'speed') else e.get('speed', 0),
        "valid": e.valid if hasattr(e, 'valid') else e.get('valid', False),
    } for e in entries]
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_result() -> list:
    if not os.path.exists(RESULT_FILE):
        return []
    try:
        with open(RESULT_FILE, 'r') as f:
            return json.load(f)
    except:
        return []


def gen_m3u_from_result(result_cache: list = None) -> str:
    if result_cache is None:
        result_cache = load_result()
    if not result_cache:
        return gen_m3u([])
    entries = []
    for r in result_cache:
        e = PlayEntry(
            name=r.get("name", ""),
            url=r.get("url", ""),
            group=r.get("group", "📡卫视频道"),
            source_name=r.get("source_name", ""),
            source_type=r.get("source_type", "multicast"),
            protocol=r.get("protocol", ""),
            response_time=r.get("response_time", 0),
            speed=r.get("speed", 0),
            valid=r.get("valid", False),
        )
        entries.append(e)
    return gen_m3u(entries)


def gen_txt_from_result(result_cache: list = None) -> str:
    if result_cache is None:
        result_cache = load_result()
    if not result_cache:
        return gen_txt([])
    entries = []
    for r in result_cache:
        e = PlayEntry(
            name=r.get("name", ""),
            url=r.get("url", ""),
            group=r.get("group", "📡卫视频道"),
            source_name=r.get("source_name", ""),
            source_type=r.get("source_type", "multicast"),
            protocol=r.get("protocol", ""),
            response_time=r.get("response_time", 0),
            speed=r.get("speed", 0),
            valid=r.get("valid", False),
        )
        entries.append(e)
    return gen_txt(entries)
