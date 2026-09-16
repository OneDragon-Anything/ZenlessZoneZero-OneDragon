"""Validate gettext catalogs used by the desktop application."""

from __future__ import annotations

import ast
import re
import string
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = ROOT / 'assets' / 'text' / 'ui'
LANGUAGES = ('zh', 'en', 'vi')
UI_SOURCE_ROOTS = (ROOT / 'src' / 'one_dragon_qt', ROOT / 'src' / 'zzz_od' / 'gui')
APPLICATION_SOURCE_ROOT = ROOT / 'src' / 'zzz_od' / 'application'
CONFIG_SOURCE_ROOTS = (
    ROOT / 'src' / 'one_dragon' / 'base' / 'config',
    ROOT / 'src' / 'one_dragon' / 'base' / 'controller' / 'pc_button',
    ROOT / 'src' / 'one_dragon' / 'envs',
    APPLICATION_SOURCE_ROOT,
    ROOT / 'src' / 'zzz_od' / 'config',
)
PUSH_CHANNEL_SOURCE_ROOT = ROOT / 'src' / 'one_dragon' / 'base' / 'push' / 'channel'
REPOSITORY_CONFIG_PATH = ROOT / 'config' / 'repository.yml'
RAW_TEXT_CONSTRUCTORS = {
    'BodyLabel',
    'CaptionLabel',
    'Dialog',
    'DisplayLabel',
    'LargeTitleLabel',
    'MessageBox',
    'PrimaryPushButton',
    'PushButton',
    'QLabel',
    'QPushButton',
    'SubtitleLabel',
    'TitleLabel',
    'TransparentPushButton',
}
RAW_TEXT_METHODS = {'setPlaceholderText', 'setText', 'setToolTip', 'setWindowTitle'}
PERCENT_PLACEHOLDER_PATTERN = re.compile(
    r'%(?:\((?P<name>[^)]+)\))?'
    r'[#0\- +]*(?:\d+|\*)?(?:\.(?:\d+|\*))?'
    r'[hlL]?(?P<type>[diouxXeEfFgGcrsa%])'
)


def read_catalog(path: Path) -> tuple[dict[str, str], set[str]]:
    """Read single-line and continued msgid/msgstr entries from a PO file."""
    entries: dict[str, str] = {}
    duplicates: set[str] = set()
    msgid: str | None = None
    msgstr: str = ''
    active: str | None = None
    has_msgstr = False

    for raw_line in path.read_text(encoding='utf-8').splitlines() + ['']:
        line = raw_line.strip()
        if line.startswith('msgid '):
            if msgid is not None:
                if not has_msgstr:
                    raise ValueError(f'Missing msgstr for {msgid!r} in {path}')
                if msgid in entries:
                    duplicates.add(msgid)
                entries[msgid] = msgstr
            msgid = ast.literal_eval(line[6:])
            msgstr = ''
            active = 'msgid'
            has_msgstr = False
        elif line.startswith('msgstr '):
            if msgid is None:
                raise ValueError(f'msgstr without msgid in {path}')
            msgstr = ast.literal_eval(line[7:])
            active = 'msgstr'
            has_msgstr = True
        elif line.startswith('"') and active is not None:
            value = ast.literal_eval(line)
            if active == 'msgid':
                msgid = (msgid or '') + value
            else:
                msgstr += value
        elif not line and msgid is not None:
            if not has_msgstr:
                raise ValueError(f'Missing msgstr for {msgid!r} in {path}')
            if msgid in entries:
                duplicates.add(msgid)
            entries[msgid] = msgstr
            msgid = None
            msgstr = ''
            active = None
            has_msgstr = False

    return entries, duplicates


def placeholders(value: str) -> Counter[str]:
    """Return comparable brace-style and percent-style placeholder counts."""
    result: Counter[str] = Counter()
    for _, field_name, _, _ in string.Formatter().parse(value):
        if field_name is None:
            continue
        token = 'brace:auto' if field_name == '' else f'brace:{field_name}'
        result[token] += 1
    for match in PERCENT_PLACEHOLDER_PATTERN.finditer(value):
        placeholder_type = match.group('type')
        if placeholder_type == '%':
            continue
        name = match.group('name')
        token = f'percent:{name}:{placeholder_type}' if name else f'percent:{placeholder_type}'
        result[token] += 1
    return result


def find_missing_ui_msgids(catalog: set[str]) -> set[str]:
    """Find literal UI source strings without catalog entries."""
    missing: set[str] = set()
    translated_helpers = {
        '_show_error_message',
        '_show_info_bar',
        '_show_success_message',
        'show_info_bar',
    }
    for root in UI_SOURCE_ROOTS:
        for path in root.rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name) and node.func.id in {'gt', 'tr'}:
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        if node.args[0].value not in catalog:
                            missing.add(node.args[0].value)
                helper_name = None
                if isinstance(node.func, ast.Name):
                    helper_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    helper_name = node.func.attr
                if helper_name in translated_helpers:
                    for argument in node.args[:2]:
                        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                            if argument.value not in catalog:
                                missing.add(argument.value)
                if isinstance(node.func, ast.Name) and node.func.id == 'ColumnMeta':
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        if node.args[0].value not in catalog:
                            missing.add(node.args[0].value)
                for keyword in node.keywords:
                    if keyword.arg != 'nav_text_cn':
                        continue
                    if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
                        continue
                    if keyword.value.value not in catalog:
                        missing.add(keyword.value.value)
    return missing


def find_missing_application_names(catalog: set[str]) -> set[str]:
    """Find application names used by the App Runner without catalog entries."""
    missing: set[str] = set()
    for path in APPLICATION_SOURCE_ROOT.rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == 'APP_NAME' for target in node.targets):
                continue
            if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                continue
            if any('\u3400' <= char <= '\u9fff' for char in node.value.value) and node.value.value not in catalog:
                missing.add(node.value.value)
    return missing


def find_missing_config_items(catalog: set[str]) -> set[str]:
    """Find display labels in configuration enums without catalog entries."""
    missing: set[str] = set()
    for root in CONFIG_SOURCE_ROOTS:
        for path in root.rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != 'ConfigItem':
                    continue
                if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                    continue
                value = node.args[0].value
                if any('\u3400' <= char <= '\u9fff' for char in value) and value not in catalog:
                    missing.add(value)
    return missing


def find_missing_push_channel_names(catalog: set[str]) -> set[str]:
    """Find notification channel names without catalog entries."""
    missing: set[str] = set()
    for path in PUSH_CHANNEL_SOURCE_ROOT.rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != 'channel_name' or not isinstance(keyword.value, ast.Constant):
                    continue
                value = keyword.value.value
                if isinstance(value, str) and any('\u3400' <= char <= '\u9fff' for char in value) and value not in catalog:
                    missing.add(value)
    return missing


def find_missing_push_channel_schema_text(catalog: set[str]) -> set[str]:
    """Find untranslated labels, placeholders, and options in push channel schemas."""
    missing: set[str] = set()
    for path in PUSH_CHANNEL_SOURCE_ROOT.rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != 'PushChannelConfigField':
                continue
            for keyword in node.keywords:
                if keyword.arg in {'title', 'placeholder'}:
                    values = [keyword.value]
                elif keyword.arg == 'options' and isinstance(keyword.value, (ast.List, ast.Tuple)):
                    values = keyword.value.elts
                else:
                    continue
                for value_node in values:
                    if not isinstance(value_node, ast.Constant) or not isinstance(value_node.value, str):
                        continue
                    value = value_node.value
                    if any('\u3400' <= char <= '\u9fff' for char in value) and value not in catalog:
                        missing.add(value)
    return missing


def find_missing_repository_labels(catalog: set[str]) -> set[str]:
    """Find translated display labels loaded from the repository YAML config."""
    missing: set[str] = set()
    for raw_line in REPOSITORY_CONFIG_PATH.read_text(encoding='utf-8').splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith('label:'):
            continue
        value = stripped.removeprefix('label:').strip().strip('"\'')
        if any('\u3400' <= char <= '\u9fff' for char in value) and value not in catalog:
            missing.add(value)
    return missing


def find_untranslated_ui_literals() -> set[str]:
    """Find Chinese literals passed directly to text-rendering Qt APIs."""
    findings: set[str] = set()
    for root in UI_SOURCE_ROOTS:
        for path in root.rglob('*.py'):
            if 'demo' in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name):
                    call_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    call_name = node.func.attr
                else:
                    continue
                if call_name not in RAW_TEXT_CONSTRUCTORS | RAW_TEXT_METHODS:
                    continue
                values = list(node.args)
                values.extend(
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg in {'content', 'text', 'title'}
                )
                for value_node in values:
                    if isinstance(value_node, ast.Call):
                        if isinstance(value_node.func, ast.Name) and value_node.func.id in {'gt', 'tr'}:
                            continue
                    if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
                        value = value_node.value
                    elif isinstance(value_node, ast.JoinedStr):
                        value = ''.join(
                            item.value
                            for item in value_node.values
                            if isinstance(item, ast.Constant) and isinstance(item.value, str)
                        )
                    else:
                        continue
                    if any('\u3400' <= char <= '\u9fff' for char in value):
                        findings.add(f'{path.relative_to(ROOT)}:{node.lineno}: {value}')
    return findings


def main() -> int:
    """Validate catalog keys, duplicate msgids, and format placeholders."""
    catalogs: dict[str, dict[str, str]] = {}
    failed = False
    for language in LANGUAGES:
        entries, duplicates = read_catalog(CATALOG_DIR / f'{language}.po')
        catalogs[language] = entries
        if duplicates:
            failed = True
            print(f'{language}: duplicate msgids: {sorted(duplicates)}')

    reference = set(catalogs['en'])
    missing_ui_msgids = find_missing_ui_msgids(reference)
    if missing_ui_msgids:
        failed = True
        print(f'en: UI source msgids missing from catalog: {sorted(missing_ui_msgids)}')
    missing_application_names = find_missing_application_names(reference)
    if missing_application_names:
        failed = True
        print(f'en: application names missing from catalog: {sorted(missing_application_names)}')
    missing_config_items = find_missing_config_items(reference)
    if missing_config_items:
        failed = True
        print(f'en: config item labels missing from catalog: {sorted(missing_config_items)}')
    missing_push_channel_names = find_missing_push_channel_names(reference)
    if missing_push_channel_names:
        failed = True
        print(f'en: push channel names missing from catalog: {sorted(missing_push_channel_names)}')
    missing_push_channel_schema_text = find_missing_push_channel_schema_text(reference)
    if missing_push_channel_schema_text:
        failed = True
        print(f'en: push channel schema text missing from catalog: {sorted(missing_push_channel_schema_text)}')
    missing_repository_labels = find_missing_repository_labels(reference)
    if missing_repository_labels:
        failed = True
        print(f'en: repository labels missing from catalog: {sorted(missing_repository_labels)}')
    untranslated_ui_literals = find_untranslated_ui_literals()
    if untranslated_ui_literals:
        failed = True
        print(f'untranslated Chinese UI literals: {sorted(untranslated_ui_literals)}')
    for language, entries in catalogs.items():
        keys = set(entries)
        missing = sorted(reference - keys)
        extra = sorted(keys - reference)
        if missing or extra:
            failed = True
            print(f'{language}: missing={missing}, extra={extra}')

    for key in reference:
        try:
            expected = placeholders(catalogs['en'][key])
        except ValueError:
            failed = True
            print(f'en: invalid format string for {key!r}')
            continue
        for language, entries in catalogs.items():
            if key not in entries:
                continue
            try:
                actual = placeholders(entries[key])
            except ValueError:
                failed = True
                print(f'{language}: invalid format string for {key!r}')
                continue
            if actual != expected:
                failed = True
                print(f'{language}: incompatible placeholders for {key!r}')

    if failed:
        return 1
    print(f'Validated {len(reference)} keys across {len(LANGUAGES)} languages.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
