"""库存或图像配置的独立逻辑，不启动游戏，不修改已有任务计划。"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MAGIC = bytes(
    [
        85,
        110,
        209,
        150,
        116,
        209,
        131,
        206,
        149,
        110,
        103,
        105,
        110,
        208,
        181,
        46,
        71,
        208,
        176,
        109,
        101,
        206,
        159,
        98,
        106,
        101,
        209,
        129,
        116,
    ]
)


def load_codec() -> Any:
    """加载仅用于配置文件编解码的 Sleepy 实现。"""
    from zzz_od.graphics_profiles.sleepy import Sleepy

    return Sleepy()


def decode_document(raw: bytes) -> dict[str, Any]:
    """解码并核对原生设置结构。"""
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('Unexpected native settings size')
    text = load_codec().read_string(io.BytesIO(raw), MAGIC)
    doc = json.loads(text.encode('latin-1').decode('utf-8'))
    if not isinstance(doc, dict) or not isinstance(
        doc.get('SystemSettingDataMap'), dict
    ):
        raise ValueError('Native system settings schema changed')
    return doc


def read_document(path: Path) -> dict[str, Any]:
    """只读指定的原生配置文件。"""
    return decode_document(path.read_bytes())


def settings_only(doc: dict[str, Any]) -> dict[str, int]:
    """读取设置编号和值，拒绝未知数据结构。"""
    result = {}
    for key, item in doc['SystemSettingDataMap'].items():
        if (
            not key.isdigit()
            or not isinstance(item, dict)
            or type(item.get('Data')) is not int
        ):
            raise ValueError('Native setting has unknown format')
        result[key] = item['Data']
    return result
