"""
IPTV 源验证器模块

提供异步 IPTV 源验证功能：
- 验证单个 M3U 源 URL 是否可访问且内容合法
- 验证单个播放流地址是否可达
- 并发批量验证多个源，支持并发数控制
"""

import asyncio
import time
from typing import Optional

import aiohttp

from app.core.m3u import M3UParser, M3UChannel


async def check_stream(url: str, timeout: int = 5) -> dict:
    """
    验证单个播放流地址是否可达。

    对目标 URL 发起 HTTP HEAD 请求（失败时降级为 GET），
    根据响应状态码判断播放地址是否有效。

    Args:
        url: 播放流地址（如 http://example.com/live/123.m3u8）
        timeout: 请求超时时间（秒），默认 5 秒

    Returns:
        dict: 验证结果，包含以下字段：
            - url (str): 被验证的地址
            - valid (bool): 是否有效
            - status_code (int | None): HTTP 状态码（请求成功时有值）
            - response_time (float): 响应时间（毫秒）
            - error (str | None): 错误信息（验证失败时有值）
            - content_type (str | None): 响应 Content-Type（如有）

    Examples:
        >>> result = await check_stream("http://example.com/stream.m3u8", timeout=5)
        >>> if result["valid"]:
        ...     print(f"有效！响应时间: {result['response_time']:.0f}ms")
        ... else:
        ...     print(f"无效: {result['error']}")
    """
    result: dict = {
        "url": url,
        "valid": False,
        "status_code": None,
        "response_time": 0.0,
        "error": None,
        "content_type": None,
    }

    if not url or not url.startswith(("http://", "https://")):
        result["error"] = "无效的 URL 格式（必须以 http:// 或 https:// 开头）"
        return result

    timeout_cfg = aiohttp.ClientTimeout(total=timeout)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
    }

    start = time.monotonic()

    try:
        async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
            # 先尝试 HEAD 请求（轻量级，不下载正文）
            try:
                async with session.head(url, headers=headers, allow_redirects=True) as resp:
                    elapsed = (time.monotonic() - start) * 1000
                    result["status_code"] = resp.status
                    result["response_time"] = round(elapsed, 2)
                    result["content_type"] = resp.headers.get("Content-Type")
                    if resp.status < 400:
                        result["valid"] = True
                        return result
                    # HEAD 返回 403/405 等，某些服务器不支持 HEAD，降级为 GET
            except (aiohttp.ClientError, asyncio.TimeoutError):
                pass

            # HEAD 失败时降级为 GET 请求，只读前 1KB 数据
            start = time.monotonic()
            async with session.get(url, headers=headers, allow_redirects=True) as resp:
                # 仅读取少量数据以确认连接有效
                if resp.content_type not in ("text/html",):
                    await resp.content.read(1024)
                elapsed = (time.monotonic() - start) * 1000
                result["status_code"] = resp.status
                result["response_time"] = round(elapsed, 2)
                result["content_type"] = resp.headers.get("Content-Type")

                if resp.status < 400:
                    result["valid"] = True
                else:
                    result["error"] = f"HTTP {resp.status}: {resp.reason}"

    except asyncio.TimeoutError:
        elapsed = (time.monotonic() - start) * 1000
        result["response_time"] = round(elapsed, 2)
        result["error"] = f"请求超时（>{timeout}s）"
    except aiohttp.ClientConnectorError as e:
        elapsed = (time.monotonic() - start) * 1000
        result["response_time"] = round(elapsed, 2)
        result["error"] = f"连接失败: {str(e)}"
    except aiohttp.ClientError as e:
        elapsed = (time.monotonic() - start) * 1000
        result["response_time"] = round(elapsed, 2)
        result["error"] = f"请求异常: {str(e)}"
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        result["response_time"] = round(elapsed, 2)
        result["error"] = f"未知错误: {type(e).__name__}: {str(e)}"

    return result


async def validate_source(
    url: str,
    timeout: int = 10,
    check_channels: bool = False,
    channel_sample: int = 3,
    channel_timeout: int = 5,
) -> dict:
    """
    验证单个 IPTV M3U 源 URL 是否可用且内容合法。

    流程：
    1. 异步获取 M3U 源内容
    2. 使用 M3UParser 解析内容
    3. 验证是否包含至少一个有效频道（有名称 + URL）
    4. （可选）深度检测：随机抽样验证频道播放地址是否可达

    Args:
        url: M3U 源 URL
        timeout: 源下载超时时间（秒），默认 10 秒
        check_channels: 是否深度检测频道播放地址，默认 False
        channel_sample: 深度检测时最大抽样频道数，默认 3
        channel_timeout: 单个频道检测超时（秒），默认 5 秒

    Returns:
        dict: 验证结果，结构如下：
            {
                "url": str,           # 被验证的源 URL
                "valid": bool,        # 整体是否有效
                "status_code": int | None,  # HTTP 状态码
                "response_time": float,     # 获取源的响应时间（毫秒）
                "channel_count": int,       # 解析到的有效频道数量
                "error": str | None,        # 错误信息（验证失败时有值）
                "channels_checked": int,    # 深度检测的频道数（仅 check_channels=True）
                "channels_valid": int,      # 深度检测中有效的频道数
                "stream_results": list,     # 各频道检测结果（仅 check_channels=True）
            }

    Examples:
        >>> # 仅验证 M3U 源可访问性和内容合法性
        >>> result = await validate_source("http://example.com/iptv.m3u")

        >>> # 加上深度频道检测
        >>> result = await validate_source("http://example.com/iptv.m3u", check_channels=True)
    """
    result: dict = {
        "url": url,
        "valid": False,
        "status_code": None,
        "response_time": 0.0,
        "channel_count": 0,
        "error": None,
        "channels_checked": 0,
        "channels_valid": 0,
        "stream_results": [],
    }

    if not url or not url.startswith(("http://", "https://")):
        result["error"] = "无效的 URL 格式（必须以 http:// 或 https:// 开头）"
        return result

    timeout_cfg = aiohttp.ClientTimeout(total=timeout)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
    }

    start_time = time.monotonic()

    try:
        # ========== 第一步：下载 M3U 源内容 ==========
        async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
            async with session.get(url, headers=headers, allow_redirects=True) as resp:
                elapsed = (time.monotonic() - start_time) * 1000
                result["status_code"] = resp.status
                result["response_time"] = round(elapsed, 2)

                if resp.status >= 400:
                    result["error"] = f"HTTP {resp.status}: {resp.reason}"
                    return result

                # 读取文本内容
                content = await resp.text(encoding="utf-8", errors="replace")

        # ========== 第二步：解析 M3U 内容 ==========
        channels: list[M3UChannel] = M3UParser.parse(content)
        result["channel_count"] = len(channels)

        if not channels:
            result["error"] = "M3U 内容解析后未找到有效频道（需包含 #EXTINF 和 URL）"
            return result

        # ========== 第三步：深度检测频道播放地址（可选） ==========
        if check_channels and channels:
            # 从前 channel_sample 个频道中抽样检测
            sample = channels[:channel_sample]
            semaphore = asyncio.Semaphore(min(channel_sample, 5))

            async def _check_with_limit(channel: M3UChannel) -> dict:
                """在并发限制下检测单个频道"""
                async with semaphore:
                    if channel.url:
                        return await check_stream(channel.url, timeout=channel_timeout)
                return {
                    "url": channel.url,
                    "valid": False,
                    "error": "频道没有播放地址",
                }

            stream_results = await asyncio.gather(
                *[_check_with_limit(ch) for ch in sample],
                return_exceptions=False,
            )

            result["stream_results"] = stream_results
            result["channels_checked"] = len(stream_results)
            result["channels_valid"] = sum(1 for r in stream_results if r.get("valid"))

        # 所有检查通过
        result["valid"] = True

    except asyncio.TimeoutError:
        elapsed = (time.monotonic() - start_time) * 1000
        result["response_time"] = round(elapsed, 2)
        result["error"] = f"源下载超时（>{timeout}s）"
    except aiohttp.ClientConnectorError as e:
        elapsed = (time.monotonic() - start_time) * 1000
        result["response_time"] = round(elapsed, 2)
        result["error"] = f"连接失败: {str(e)}"
    except aiohttp.ClientError as e:
        elapsed = (time.monotonic() - start_time) * 1000
        result["response_time"] = round(elapsed, 2)
        result["error"] = f"请求异常: {str(e)}"
    except Exception as e:
        elapsed = (time.monotonic() - start_time) * 1000
        result["response_time"] = round(elapsed, 2)
        result["error"] = f"未知错误: {type(e).__name__}: {str(e)}"

    return result


async def validate_sources(
    urls: list[str],
    concurrency: int = 10,
    timeout: int = 10,
    check_channels: bool = False,
    channel_sample: int = 3,
    channel_timeout: int = 5,
) -> list[dict]:
    """
    并发批量验证多个 IPTV M3U 源。

    使用 asyncio.Semaphore 控制并发数，避免同时发起过多请求。
    validate_source() 的并发包装版本。

    Args:
        urls: M3U 源 URL 列表
        concurrency: 最大并发验证数，默认 10
        timeout: 单个源的下载超时时间（秒），默认 10 秒
        check_channels: 是否深度检测频道播放地址，默认 False
        channel_sample: 深度检测时每个源的最大抽样频道数，默认 3
        channel_timeout: 单个频道检测超时（秒），默认 5 秒

    Returns:
        list[dict]: 每个 URL 对应的验证结果列表，顺序与输入一致。
            每项结构同 validate_source() 的返回值。

    Examples:
        >>> urls = [
        ...     "http://source1.com/iptv.m3u",
        ...     "http://source2.com/iptv.m3u8",
        ... ]
        >>> results = await validate_sources(urls, concurrency=5)
        >>> for r in results:
        ...     status = "✅" if r["valid"] else "❌"
        ...     print(f"{status} {r['url']} - {r['channel_count']} 频道")
    """
    if not urls:
        return []

    # 信号量控制全局并发数
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _validate_with_limit(url: str) -> dict:
        """在并发限制下验证单个源"""
        async with semaphore:
            return await validate_source(
                url,
                timeout=timeout,
                check_channels=check_channels,
                channel_sample=channel_sample,
                channel_timeout=channel_timeout,
            )

    tasks = [_validate_with_limit(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    return list(results)
