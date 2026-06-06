"""IPTV 源搜索引擎"""
import aiohttp
import asyncio
from typing import Optional
from app.core.m3u import M3UParser
from app.core.validator import validate_source

# ============ 内置 IPTV 源列表 ============
# 这些是已知的高质量公开 IPTV 源
BUILTIN_SOURCES = {
    "iptv-org": {
        "name": "iptv-org/iptv (GitHub)",
        "url": "https://iptv-org.github.io/iptv/index.m3u",
        "region": "国际",
        "operator": "第三方",
    },
    "fanmingming-live": {
        "name": "fanmingming/live (GitHub)",
        "url": "https://live.fanmingming.com/tv/m3u/ipv6.m3u",
        "region": "全国",
        "operator": "第三方",
    },
    "fanmingming-tv": {
        "name": "fanmingming/live - TV",
        "url": "https://live.fanmingming.com/tv/m3u/global.m3u",
        "region": "国际",
        "operator": "第三方",
    },
    "yanue-m3u": {
        "name": "yanue/iptv",
        "url": "https://raw.githubusercontent.com/yanue/V2ray/master/m3u/iptv.m3u8",
        "region": "国际",
        "operator": "第三方",
    },
    "kensonchoi-iptv": {
        "name": "KensonChoi/iptv",
        "url": "https://raw.githubusercontent.com/KensonChoi/iptv/main/iptv.m3u",
        "region": "国际",
        "operator": "第三方",
    },
    # 国内常见源
    "hcao-m3u": {
        "name": "HCao/iptv (国内)",
        "url": "https://raw.githubusercontent.com/HCao/iptv/main/iptv.m3u",
        "region": "全国",
        "operator": "第三方",
    },
}


async def search_all(max_sources: int = 50, timeout: int = 15, concurrency: int = 5) -> dict:
    """
    自动搜索所有内置 IPTV 源
    
    Args:
        max_sources: 最大搜索源数
        timeout: 每个源超时时间（秒）
        concurrency: 并发数
    
    Returns:
        {
            "total": 总源数,
            "valid": 有效源数,
            "total_channels": 总频道数,
            "valid_channels": 有效频道数（去重后）,
            "sources": [{"name", "url", "valid", "channel_count", "error"}],
            "channels": [M3UChannel, ...]
        }
    """
    sources = list(BUILTIN_SOURCES.values())[:max_sources]
    results = {
        "total": len(sources),
        "valid": 0,
        "total_channels": 0,
        "valid_channels": 0,
        "sources": [],
        "channels": [],
    }

    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_one(source_info):
        async with semaphore:
            name = source_info["name"]
            url = source_info["url"]
            try:
                validation = await validate_source(url, timeout=timeout)
                source_result = {
                    "name": name,
                    "url": url,
                    "valid": validation["valid"],
                    "channel_count": validation.get("channel_count", 0),
                    "response_time": validation.get("response_time", 0),
                    "error": validation.get("error", ""),
                    "region": source_info.get("region", ""),
                    "operator": source_info.get("operator", ""),
                }
                return source_result, validation.get("channels", [])
            except Exception as e:
                return {
                    "name": name,
                    "url": url,
                    "valid": False,
                    "channel_count": 0,
                    "response_time": 0,
                    "error": str(e)[:200],
                    "region": source_info.get("region", ""),
                    "operator": source_info.get("operator", ""),
                }, []

    tasks = [fetch_one(s) for s in sources]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    seen_urls = set()
    all_channels = []

    for r in all_results:
        if isinstance(r, Exception):
            results["sources"].append({
                "name": "unknown", "url": "", "valid": False,
                "channel_count": 0, "response_time": 0,
                "error": str(r)[:200], "region": "", "operator": "",
            })
            continue

        source_result, channels = r
        results["sources"].append(source_result)

        if source_result["valid"]:
            results["valid"] += 1
            results["total_channels"] += source_result["channel_count"]

            for ch in channels:
                if ch.url not in seen_urls:
                    seen_urls.add(ch.url)
                    # 附加 meta 信息
                    ch.extra_tags["_source"] = source_result["name"]
                    ch.extra_tags["_region"] = source_result.get("region", "")
                    ch.extra_tags["_operator"] = source_result.get("operator", "")
                    all_channels.append(ch)

    results["valid_channels"] = len(all_channels)
    results["channels"] = all_channels

    return results


async def search_custom(urls: list[str], timeout: int = 15, concurrency: int = 5) -> dict:
    """
    搜索用户自定义的 IPTV 源 URL 列表
    
    Args:
        urls: URL 列表
        timeout: 超时时间
        concurrency: 并发数
    
    Returns:
        同 search_all()
    """
    sources = [{"name": f"自定义源-{i+1}", "url": u, "region": "", "operator": ""}
               for i, u in enumerate(urls) if u.strip()]

    results = {
        "total": len(sources),
        "valid": 0,
        "total_channels": 0,
        "valid_channels": 0,
        "sources": [],
        "channels": [],
    }

    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_one(source_info):
        async with semaphore:
            try:
                validation = await validate_source(source_info["url"], timeout=timeout)
                return {
                    "name": source_info["name"],
                    "url": source_info["url"],
                    "valid": validation["valid"],
                    "channel_count": validation.get("channel_count", 0),
                    "response_time": validation.get("response_time", 0),
                    "error": validation.get("error", ""),
                    "region": source_info.get("region", ""),
                    "operator": source_info.get("operator", ""),
                }, validation.get("channels", [])
            except Exception as e:
                return {
                    "name": source_info["name"],
                    "url": source_info["url"],
                    "valid": False, "channel_count": 0,
                    "response_time": 0, "error": str(e)[:200],
                    "region": "", "operator": "",
                }, []

    tasks = [fetch_one(s) for s in sources]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    seen_urls = set()
    for r in all_results:
        if isinstance(r, Exception):
            continue
        src, channels = r
        results["sources"].append(src)
        if src["valid"]:
            results["valid"] += 1
            results["total_channels"] += src["channel_count"]
            for ch in channels:
                if ch.url not in seen_urls:
                    seen_urls.add(ch.url)
                    results["channels"].append(ch)

    results["valid_channels"] = len(results["channels"])
    return results


def get_builtin_sources() -> list[dict]:
    """获取所有内置源信息"""
    return [{"id": k, **v} for k, v in BUILTIN_SOURCES.items()]


def add_builtin_source(key: str, name: str, url: str, region: str = "", operator: str = ""):
    """动态添加内置源"""
    BUILTIN_SOURCES[key] = {
        "name": name,
        "url": url,
        "region": region,
        "operator": operator,
    }
