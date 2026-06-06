"""M3U/M3U8 解析器和生成器"""
import re
import aiohttp
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class M3UChannel:
    """M3U 频道条目"""
    name: str = ""
    url: str = ""
    group_title: str = "未分组"
    tvg_id: str = ""
    tvg_name: str = ""
    tvg_logo: str = ""
    tvg_shift: str = ""
    radio: bool = False
    extra_tags: dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.tvg_name or self.name


class M3UParser:
    """M3U/M3U8 解析器"""

    EXTINF_PATTERN = re.compile(
        r'#EXTINF:(-?\d+)\s*(.*?)\s*,\s*(.*?)$', re.MULTILINE
    )
    TAG_PATTERN = re.compile(r'([\w-]+)="([^"]*)"')

    @classmethod
    def parse(cls, content: str) -> list[M3UChannel]:
        """解析 M3U 内容"""
        channels = []
        lines = content.strip().split('\n')

        if not lines or not lines[0].strip().startswith('#EXTM3U'):
            # 尝试宽松解析
            pass

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if line.startswith('#EXTINF:'):
                channel = M3UChannel()
                # 解析 EXTINF 行
                match = cls.EXTINF_PATTERN.match(line)
                if match:
                    attrs_str = match.group(2)
                    channel.name = match.group(3).strip()
                    # 解析属性
                    for tag_match in cls.TAG_PATTERN.finditer(attrs_str):
                        key, value = tag_match.groups()
                        key_lower = key.lower()
                        if key_lower == 'tvg-id':
                            channel.tvg_id = value
                        elif key_lower == 'tvg-name':
                            channel.tvg_name = value
                        elif key_lower == 'tvg-logo':
                            channel.tvg_logo = value
                        elif key_lower == 'tvg-shift':
                            channel.tvg_shift = value
                        elif key_lower == 'group-title':
                            channel.group_title = value
                        elif key_lower == 'radio':
                            channel.radio = value.lower() == 'true'
                        else:
                            channel.extra_tags[key] = value
                else:
                    # 宽松匹配：取逗号后的名称
                    comma_idx = line.find(',')
                    if comma_idx > 0:
                        channel.name = line[comma_idx + 1:].strip()

                # 下一行是 URL
                if i + 1 < len(lines):
                    url_line = lines[i + 1].strip()
                    if not url_line.startswith('#'):
                        channel.url = url_line
                        i += 1

                if channel.url and channel.name:
                    channels.append(channel)

            elif line.startswith('#EXTVLCOPT:') or line.startswith('#EXTGRP:'):
                # 处理 EXTGRP 作为 group-title
                if line.startswith('#EXTGRP:') and channels:
                    channels[-1].group_title = line[8:].strip()

            i += 1

        return channels

    @classmethod
    async def parse_url(cls, url: str, timeout: int = 15, headers: Optional[dict] = None) -> list[M3UChannel]:
        """从 URL 获取并解析 M3U"""
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
        }
        if headers:
            default_headers.update(headers)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=default_headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                content = await resp.text(encoding='utf-8', errors='replace')
                return cls.parse(content)


class M3UGenerator:
    """M3U 生成器"""

    @classmethod
    def generate(cls, channels: list[M3UChannel], include_extm3u: bool = True) -> str:
        """生成 M3U 内容"""
        lines = []
        if include_extm3u:
            lines.append('#EXTM3U x-tvg-url=""')

        for ch in channels:
            if not ch.url or not ch.name:
                continue

            attrs = []
            if ch.tvg_id:
                attrs.append(f'tvg-id="{ch.tvg_id}"')
            if ch.tvg_name:
                attrs.append(f'tvg-name="{ch.tvg_name}"')
            if ch.tvg_logo:
                attrs.append(f'tvg-logo="{ch.tvg_logo}"')
            if ch.tvg_shift:
                attrs.append(f'tvg-shift="{ch.tvg_shift}"')
            if ch.group_title and ch.group_title != "未分组":
                attrs.append(f'group-title="{ch.group_title}"')
            if ch.radio:
                attrs.append('radio="true"')
            for k, v in ch.extra_tags.items():
                attrs.append(f'{k}="{v}"')

            attr_str = " ".join(attrs)
            lines.append(f'#EXTINF:-1 {attr_str},{ch.name}')
            lines.append(ch.url)

        return "\n".join(lines)

    @classmethod
    def generate_simple(cls, channels: list[dict]) -> str:
        """从简单字典列表生成 M3U"""
        m3u_channels = []
        for ch in channels:
            m3u_channels.append(M3UChannel(
                name=ch.get('name', ''),
                url=ch.get('url', ''),
                group_title=ch.get('group_title', '未分组'),
                tvg_id=ch.get('tvg_id', ''),
                tvg_name=ch.get('tvg_name', ''),
                tvg_logo=ch.get('tvg_logo', ''),
            ))
        return cls.generate(m3u_channels)
