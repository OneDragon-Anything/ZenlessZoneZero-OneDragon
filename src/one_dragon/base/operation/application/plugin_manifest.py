"""插件清单（plugin.json）读取

插件的展示元数据（版本、作者、主页、简介）和封面都来自插件包内的 ``plugin.json``，
常量模块只保留身份和运行行为。``plugin.json`` 来自第三方，字段在这里统一校验：
读取失败、格式不对、过大或字段类型不对都按「没有这项信息」处理，不打断插件加载。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST_FILE_NAME = 'plugin.json'
MAX_MANIFEST_BYTES = 64 * 1024

_MAX_VERSION_LEN = 32
_MAX_AUTHOR_LEN = 200
_MAX_HOMEPAGE_LEN = 200
_MAX_DESCRIPTION_LEN = 500


@dataclass(frozen=True)
class PluginManifestInfo:
    """从 plugin.json 取出并校验过的展示元数据，缺失或不合法的字段为空串。"""

    version: str = ''
    author: str = ''
    homepage: str = ''
    description: str = ''


def parse_manifest(data: bytes | str) -> dict[str, Any] | None:
    """解析 plugin.json 内容，过大、编码或 JSON 格式不对、顶层不是对象时返回 None。"""
    if isinstance(data, bytes):
        if len(data) > MAX_MANIFEST_BYTES:
            return None
        try:
            data = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            return None
    try:
        manifest = json.loads(data)
    except (ValueError, RecursionError):
        return None
    return manifest if isinstance(manifest, dict) else None


def read_manifest_file(manifest_file: Path) -> dict[str, Any] | None:
    """读取 plugin.json 文件，不存在或不可用时返回 None。"""
    try:
        if not manifest_file.is_file() or manifest_file.stat().st_size > MAX_MANIFEST_BYTES:
            return None
        return parse_manifest(manifest_file.read_bytes())
    except OSError:
        return None


def _clean_str(value: Any, max_len: int, truncate: bool = False) -> str:
    """只接受字符串，去首尾空白；超长时截断或丢弃，除换行和制表符外的控制字符视为不合法。"""
    if not isinstance(value, str):
        return ''
    value = value.strip()
    if any(ord(ch) < 32 and ch not in '\n\t' for ch in value):
        return ''
    if len(value) > max_len:
        return value[:max_len] if truncate else ''
    return value


def extract_manifest_info(manifest: dict[str, Any] | None) -> PluginManifestInfo:
    """从 plugin.json 内容取出展示元数据。

    字段映射：version、author.name、homepage、summary。主页只接受 https 地址，
    因为它会被浏览器打开，也会用来匹配商店条目。
    """
    if manifest is None:
        return PluginManifestInfo()

    author = manifest.get('author')
    author_name = author.get('name') if isinstance(author, dict) else ''
    homepage = _clean_str(manifest.get('homepage'), _MAX_HOMEPAGE_LEN)
    if not homepage.lower().startswith('https://'):
        homepage = ''

    return PluginManifestInfo(
        version=_clean_str(manifest.get('version'), _MAX_VERSION_LEN),
        author=_clean_str(author_name, _MAX_AUTHOR_LEN, truncate=True),
        homepage=homepage,
        description=_clean_str(manifest.get('summary'), _MAX_DESCRIPTION_LEN, truncate=True),
    )
