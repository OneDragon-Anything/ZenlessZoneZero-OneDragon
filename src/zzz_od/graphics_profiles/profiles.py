"""库存或图像配置的独立逻辑，不启动游戏，不修改已有任务计划。"""

from __future__ import annotations

import copy
import csv
import io
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from zzz_od.graphics_profiles import settings_reader as reader

ROOT = Path(__file__).resolve().parent
PROFILES = Path(__file__).with_name('calibrated_profiles.json')
ALLOWED = frozenset(
    [
        '3',
        '110',
        '9',
        '12',
        '10',
        '15',
        '13',
        '108',
        '99',
        '109',
        '106',
        '13162',
        '16',
        '12155',
        '16184',
        '14',
    ]
)
ITEM_TYPE = 'MoleMole.SystemSettingLocalData'


def ensure_idle() -> None:
    """确认游戏未运行；状态不明时拒绝修改。"""
    query = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq ZenlessZoneZero.exe', '/FO', 'CSV', '/NH'],
        capture_output=True,
        check=True,
        timeout=10,
    )
    output = query.stdout.decode('latin-1').strip()
    if not output or any(
        row and row[0].lower() == 'zenlesszonezero.exe'
        for row in csv.reader(io.StringIO(output))
    ):
        raise RuntimeError(
            'Game running or process query unavailable; no graphics write'
        )


def merge_graphics(document: dict[str, Any], values: dict[str, int]) -> dict[str, Any]:
    """只合并已核实的图像字段，保留其他配置。"""
    if not isinstance(values, dict) or set(values) != ALLOWED:
        raise ValueError('Uncalibrated graphics field set')
    merged = copy.deepcopy(document)
    settings = merged.get('SystemSettingDataMap')
    if not isinstance(settings, dict):
        raise ValueError('Native system settings schema changed')
    for key, value in values.items():
        item = settings.get(key)
        if (
            not isinstance(item, dict)
            or item.get('$Type') != ITEM_TYPE
            or type(item.get('Data')) is not int
            or (type(value) is not int)
            or (not 0 <= value <= 4)
        ):
            raise ValueError('Native graphics type/value changed: ' + key)
        item['Data'] = value
    return merged


def encode_document(document: dict[str, Any]) -> bytes:
    """编码原生配置并核对往返结果。"""
    stream = io.BytesIO()
    reader.load_codec().write_string(
        stream,
        json.dumps(document, ensure_ascii=True, separators=(',', ':')),
        reader.MAGIC,
    )
    raw = stream.getvalue()
    if reader.decode_document(raw) != document:
        raise RuntimeError('Encoded native settings failed round trip')
    return raw


def validate_native_utf8(raw: bytes) -> None:
    """检查原生配置字符串的 UTF8 格式。"""
    index, length, shift = (22, 0, 0)
    while True:
        if index >= len(raw) or shift > 28:
            raise ValueError('Invalid native string header')
        byte = raw[index]
        index += 1
        length |= (byte & 127) << shift
        shift += 7
        if byte < 128:
            break
    if index + length + 1 != len(raw) or raw[-1] != 11:
        raise ValueError('Invalid native string length/footer')
    raw[index : index + length].decode('utf-8', errors='strict')


def encode_graphics_patch(
    before_raw: bytes, document: dict[str, Any], values: dict[str, int]
) -> bytes:
    """只修改图像值，保留其他字段及文本格式。"""
    merged = merge_graphics(document, values)
    text = (
        reader.load_codec()
        .read_string(io.BytesIO(before_raw), reader.MAGIC)
        .encode('latin-1')
        .decode('utf-8')
    )
    if not text.isascii():
        raise RuntimeError(
            'Native non-ASCII format needs codec recalibration; no write'
        )
    original_stream = io.BytesIO()
    reader.load_codec().write_string(original_stream, text, reader.MAGIC)
    if original_stream.getvalue() != before_raw:
        raise RuntimeError('Native codec not byte-exact; no write')
    start = re.search('"SystemSettingDataMap"\\s*:\\s*(?=\\{)', text)
    if not start:
        raise ValueError('Native graphics map not found')
    map_start = start.end()
    parsed, map_end = json.JSONDecoder().raw_decode(text, map_start)
    if parsed != document['SystemSettingDataMap']:
        raise ValueError('Ambiguous native graphics map')
    section = text[map_start:map_end]
    seen = set()

    def replace_item(match: Any) -> Any:
        key = match.group(1)
        if key not in ALLOWED:
            return match.group(0)
        if key in seen:
            raise ValueError('Duplicate calibrated graphics field')
        seen.add(key)
        obj = match.group(2)
        pattern = '("Data"\\s*:\\s*)(-?\\d+)'
        if len(re.findall(pattern, obj)) != 1:
            raise ValueError('Ambiguous native graphics number')
        changed = re.sub(pattern, lambda found: found.group(1) + str(values[key]), obj)
        if len(changed) != len(obj):
            raise ValueError('Native numeric width changed; recalibration required')
        return match.group(0).replace(obj, changed, 1)

    section = re.sub('"(\\d+)"\\s*:\\s*(\\{[^{}]*\\})', replace_item, section)
    if seen != ALLOWED:
        raise ValueError('Native graphics structure changed')
    text = text[:map_start] + section + text[map_end:]
    stream = io.BytesIO()
    reader.load_codec().write_string(stream, text, reader.MAGIC)
    raw = stream.getvalue()
    validate_native_utf8(raw)
    if reader.decode_document(raw) != merged:
        raise RuntimeError('Native graphics patch did not preserve unrelated fields')
    return raw


def atomic_write(path: Path, raw: bytes) -> None:
    """在同目录写临时文件并原子替换目标。"""
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def native_lock(path: Path) -> Iterator[None]:
    """持有原生配置文件锁，退出时释放。"""
    import msvcrt

    with path.open('a+b') as stream:
        if path.stat().st_size == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def apply(
    values: dict[str, int],
    path: Path,
    backup_dir: Path | None = None,
    idle: Callable[[], None] = ensure_idle,
) -> dict[str, Any]:
    """备份、修改并读回图像设置；外部修改时不覆盖。"""
    idle()
    before_raw = path.read_bytes()
    before = reader.decode_document(before_raw)
    merged = merge_graphics(before, values)
    if merged == before:
        return {'changed': False, 'readback': 'passed'}
    new_raw = encode_graphics_patch(before_raw, before, values)
    backup_dir = backup_dir or ROOT / 'state/zzz-graphics-backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bin')
    with backup.open('xb') as stream:
        stream.write(before_raw)
        stream.flush()
        os.fsync(stream.fileno())
    idle()
    if path.read_bytes() != before_raw:
        raise RuntimeError('Native settings changed concurrently; no write')
    atomic_write(path, new_raw)
    try:
        if reader.read_document(path) != merged:
            raise RuntimeError('Native graphics readback mismatch')
    except Exception as error:
        if path.read_bytes() != new_raw:
            raise RuntimeError(
                'Concurrent native save; preserved current file, backup: ' + str(backup)
            ) from error
        idle()
        atomic_write(path, before_raw)
        if path.read_bytes() != before_raw:
            raise RuntimeError(
                'Rollback unconfirmed; backup: ' + str(backup)
            ) from error
        raise
    return {'changed': True, 'readback': 'passed', 'backup': str(backup)}
