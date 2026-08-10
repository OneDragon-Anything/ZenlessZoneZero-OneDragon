"""Compile project UI PO catalogs into GNU MO files using the standard library."""

from __future__ import annotations

import struct
from pathlib import Path

from validate_i18n import read_catalog


ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = ROOT / 'assets' / 'text' / 'ui'
OUTPUT_DIR = ROOT / 'assets' / 'text' / 'output'


def compile_catalog(language: str) -> None:
    """Compile one PO catalog into the layout expected by gettext."""
    entries, _ = read_catalog(CATALOG_DIR / f'{language}.po')
    msgids = sorted(entries)
    originals = b'\0'.join(msgid.encode('utf-8') for msgid in msgids) + b'\0'
    translations = b'\0'.join(entries[msgid].encode('utf-8') for msgid in msgids) + b'\0'

    count = len(msgids)
    header_size = 7 * 4
    table_size = count * 16
    original_offset = header_size + table_size
    translation_offset = original_offset + len(originals)

    original_table: list[tuple[int, int]] = []
    cursor = original_offset
    for msgid in msgids:
        value = msgid.encode('utf-8')
        original_table.append((len(value), cursor))
        cursor += len(value) + 1

    translation_table: list[tuple[int, int]] = []
    cursor = translation_offset
    for msgid in msgids:
        value = entries[msgid].encode('utf-8')
        translation_table.append((len(value), cursor))
        cursor += len(value) + 1

    data = bytearray()
    data.extend(struct.pack('<7I', 0x950412DE, 0, count, header_size, header_size + count * 8, 0, 0))
    for length, offset in original_table:
        data.extend(struct.pack('<2I', length, offset))
    for length, offset in translation_table:
        data.extend(struct.pack('<2I', length, offset))
    data.extend(originals)
    data.extend(translations)

    output_path = OUTPUT_DIR / language / 'LC_MESSAGES' / 'ui.mo'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)


def main() -> None:
    """Compile every supported UI language."""
    for language in ('zh', 'en', 'vi'):
        compile_catalog(language)


if __name__ == '__main__':
    main()
