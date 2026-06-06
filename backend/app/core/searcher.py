"""
IPTV 搜索引擎 - 组播源 + 酒店源
==================================
搜索策略：
1. 组播源：从 GitHub/码云等公开仓库爬取 IP 组播地址列表
2. 酒店源：从公开 IPTV 仓库爬取酒店专用源
3. 合并去重 → 验证可用性 → 生成 M3U + TXT
"""
import re
import aiohttp
import asyncio
from typing import Optional
from dataclasses import dataclass, field

# ============ 内置搜索目标 ============

# 组播源 URL（IGMP 组播地址列表）
MULTICAST_SEARCH_URLS = [
    # GitHub 组播源仓库
    {
        "name": "iptv-org (全球)",
        "url": "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cn.m3u",
        "type": "m3u",
        "source_type": "multicast_group",
    },
    {
        "name": "iptv-org (中国)",
        "url": "https://iptv-org.github.io/iptv/countries/cn.m3u",
        "type": "m3u",
        "source_type": "multicast_group",
    },
    {
        "name": "fanmingming (直播源)",
        "url": "https://live.fanmingming.com/tv/m3u/Global.m3u",
        "type": "m3u",
        "source_type": "multicast_group",
    },
    {
        "name": "fanmingming (IPv6)",
        "url": "https://live.fanmingming.com/tv/m3u/ipv6.m3u",
        "type": "ip",
        "source_type": "multicast_group",
    },
    # 码云/Gitee 组播源
    {
        "name": "ipmulticast (码云镜像)",
        "url": "https://gitee.com/xxy002/iptv/raw/master/iptv.m3u",
        "type": "m3u",
        "source_type": "multicast_group",
    },
    # 组播地址提取页面
    {
        "name": "组播地址库",
        "url": "https://raw.githubusercontent.com/Meroser/iptv/main/cn.m3u",
        "type": "m3u",
        "source_type": "multicast_group",
    },
    {
        "name": "Meroser-IPTV",
        "url": "https://raw.githubusercontent.com/Meroser/iptv/main/all.m3u",
        "type": "m3u",
        "source_type": "multicast_group",
    },
]

# 酒店源 URL（酒店 IPTV 专用）
HOTEL_SEARCH_URLS = [
    # 酒店 IPTV 源
    {
        "name": "酒店源 (iptv-org hotel)",
        "url": "https://iptv-org.github.io/iptv/categories/hotel.m3u",
        "type": "m3u",
        "source_type": "hotel",
    },
    {
        "name": "酒店源 (fanmingming hotel)",
        "url": "https://live.fanmingming.com/tv/m3u/hotel.m3u",
        "type": "m3u",
        "source_type": "hotel",
    },
    {
        "name": "酒店源 (global hotel)",
        "url": "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/hotel.m3u",
        "type": "m3u",
        "source_type": "hotel",
    },
]


@dataclass
class PlaylistEntry:
    """播放列表条目"""
    name: str
    url: str
    group: str = "未分组"
    region: str = ""
    source_name: str = ""
    source_type: str = "multicast"     # multicast / hotel
    is_valid: bool = False
    response_time: int = 0             # ms


# ============ M3U 解析 ============

M3U_EXTINF_PATTERN = re.compile(
    r'#EXTINF:(-?\d+)\s*(.*?)\s*,\s*(.*?)$', re.MULTILINE
)
M3U_TAG_PATTERN = re.compile(r'([\w-]+)="([^"]*)"')


def parse_m3u(text: str) -> list[PlaylistEntry]:
    """解析 M3U/M3U8 内容"""
    entries = []
    lines = text.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            entry = PlaylistEntry(name="", url="")
            m = M3U_EXTINF_PATTERN.match(line)
            if m:
                attrs = m.group(2)
                entry.name = m.group(3).strip()
                for tag in M3U_TAG_PATTERN.finditer(attrs):
                    k, v = tag.groups()
                    kl = k.lower()
                    if kl == 'group-title':
                        entry.group = v
                    elif kl == 'tvg-name' and not entry.name:
                        entry.name = v
            else:
                comma = line.find(',')
                if comma > 0:
                    entry.name = line[comma+1:].strip()
            # 下一行是 URL
            if i + 1 < len(lines):
                url_line = lines[i+1].strip()
                if not url_line.startswith('#') and url_line:
                    entry.url = url_line
                    i += 1
            if entry.url and entry.name:
                entries.append(entry)
        i += 1
    return entries


def parse_txt(text: str) -> list[PlaylistEntry]:
    """
    解析 TXT 格式（每行: 频道名,URL 或 频道名|URL）
    也支持从纯文本中提取 rtsp:// / rtp:// / udp:// 等组播地址
    """
    entries = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # 格式: 频道名,URL 或 频道名|URL
        for sep in [',', '|', '\t']:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    url = parts[1].strip()
                    if url and url.startswith(('http://', 'https://', 'rtsp://', 'rtp://', 'udp://', 'mms://')):
                        entries.append(PlaylistEntry(name=name or "未知频道", url=url))
                    break
        else:
            # 没有分隔符，尝试提取纯 URL
            url_m = re.search(r'(rtsp://\S+|rtp://\S+|udp://\S+|https?://\S+)', line)
            if url_m:
                url = url_m.group(1)
                name = line[:url_m.start()].strip() or "未知频道"
                entries.append(PlaylistEntry(name=name, url=url))
    return entries


# ============ 搜索核心 ============

async def fetch_url(url: str, timeout: int = 15) -> str:
    """异步获取 URL 内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            return await resp.text(encoding='utf-8', errors='replace')


async def search_sources(
    urls: list[str] = None,
    source_type: str = "all",
    timeout: int = 15,
    concurrency: int = 5,
) -> list[PlaylistEntry]:
    """
    从指定 URL 搜索源

    Args:
        urls: 自定义 URL 列表
        source_type: multicast / hotel / all
        timeout: 请求超时
        concurrency: 并发数

    Returns:
        去重后的播放列表条目
    """
    # 确定搜索目标
    targets = []
    if urls:
        for u in urls:
            targets.append({"name": f"自定义-{u[:40]}", "url": u, "type": "auto", "source_type": "custom"})
    else:
        if source_type in ("multicast", "all"):
            targets.extend(MULTICAST_SEARCH_URLS)
        if source_type in ("hotel", "all"):
            targets.extend(HOTEL_SEARCH_URLS)

    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_one(target):
        async with semaphore:
            try:
                text = await fetch_url(target["url"], timeout)
                t = target.get("type", "auto")
                if t == "m3u":
                    entries = parse_m3u(text)
                elif t == "txt":
                    entries = parse_txt(text)
                else:
                    # 自动检测
                    if '#EXTM3U' in text or '#EXTINF' in text:
                        entries = parse_m3u(text)
                    else:
                        entries = parse_txt(text)
                # 标记来源
                for e in entries:
                    e.source_name = target["name"]
                    e.source_type = target.get("source_type", "multicast")
                return entries
            except Exception as e:
                return []

    tasks = [fetch_one(t) for t in targets]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 合并去重（按 URL 去重）
    seen_urls = set()
    all_entries = []
    for r in results:
        if isinstance(r, (list, tuple)):
            for entry in r:
                if entry.url and entry.url not in seen_urls:
                    seen_urls.add(entry.url)
                    all_entries.append(entry)

    return all_entries


# ============ 可用性验证 ============

async def check_url(url: str, timeout: int = 5) -> dict:
    """
    检测播放地址可用性
    
    Returns:
        {"url": str, "valid": bool, "status_code": int, "response_time": int, "error": str}
    """
    start = asyncio.get_event_loop().time()
    result = {"url": url, "valid": False, "status_code": 0, "response_time": 0, "error": ""}
    try:
        headers = {
            'User-Agent': 'VLC/3.0.18 LibVLC/3.0.18',
            'Accept': '*/*',
        }
        async with aiohttp.ClientSession() as session:
            # 先用 HEAD 检测（轻量）
            try:
                resp = await session.head(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout),
                                          allow_redirects=True)
                result["status_code"] = resp.status
                if resp.status < 400:
                    result["valid"] = True
                elif resp.status in (405, 501):
                    # HEAD 不支持，降级 GET
                    raise aiohttp.ClientError("HEAD not supported")
                else:
                    result["error"] = f"HTTP {resp.status}"
            except (aiohttp.ClientError, asyncio.TimeoutError):
                # 降级 GET（只读前 1KB）
                resp = await session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout),
                                         allow_redirects=True)
                result["status_code"] = resp.status
                # 读取少量数据确认流可用
                chunk = await resp.content.read(1024)
                if resp.status < 400 and (len(chunk) > 0 or resp.content_type.startswith(('video', 'audio', 'application'))):
                    result["valid"] = True
                elif resp.status < 400:
                    # 200 但可能不是流，也算有效
                    result["valid"] = True
                else:
                    result["error"] = f"HTTP {resp.status}"

    except asyncio.TimeoutError:
        result["error"] = "timeout"
    except aiohttp.ClientConnectorError:
        result["error"] = "connection_refused"
    except OSError as e:
        if "Network is unreachable" in str(e):
            result["error"] = "network_unreachable"
        else:
            result["error"] = str(e)[:100]
    except Exception as e:
        result["error"] = str(e)[:100]

    result["response_time"] = int((asyncio.get_event_loop().time() - start) * 1000)
    return result


async def validate_entries(
    entries: list[PlaylistEntry],
    concurrency: int = 20,
    timeout: int = 5,
    progress_callback=None,
) -> list[PlaylistEntry]:
    """
    并发验证所有播放地址，返回有效条目
    
    Args:
        entries: 待验证条目
        concurrency: 并发数
        timeout: 每个地址超时(秒)
        progress_callback: 进度回调函数(current, total)

    Returns:
        验证有效的条目列表
    """
    semaphore = asyncio.Semaphore(concurrency)
    total = len(entries)
    checked = [0]

    async def check_one(entry):
        async with semaphore:
            try:
                result = await check_url(entry.url, timeout=timeout)
                entry.is_valid = result["valid"]
                entry.response_time = result["response_time"]
                checked[0] += 1
                if progress_callback:
                    progress_callback(checked[0], total)
                return entry if result["valid"] else None
            except Exception:
                checked[0] += 1
                if progress_callback:
                    progress_callback(checked[0], total)
                return None

    tasks = [check_one(e) for e in entries]
    results = await asyncio.gather(*tasks)

    valid = [r for r in results if r is not None]
    return valid


# ============ M3U + TXT 生成 ============

def generate_m3u(entries: list[PlaylistEntry]) -> str:
    """生成 M3U 播放列表"""
    lines = ['#EXTM3U x-tvg-url=""\n']
    for e in entries:
        group = e.group or "未分组"
        lines.append(f'#EXTINF:-1 group-title="{group}",{e.name}')
        lines.append(e.url)
        lines.append('')
    return '\n'.join(lines)


def generate_txt(entries: list[PlaylistEntry], format_type: str = "name,url") -> str:
    """
    生成 TXT 播放列表
    format_type: "name,url" 或 "name|url" 或 "url"
    """
    lines = ['# IPTV 播放列表 (TXT 格式)\n']
    sep = ',' if format_type == 'name,url' else '|' if format_type == 'name|' else ','
    for e in entries:
        if format_type == 'url':
            lines.append(e.url)
        else:
            lines.append(f'{e.name}{sep}{e.url}')
    return '\n'.join(lines)
