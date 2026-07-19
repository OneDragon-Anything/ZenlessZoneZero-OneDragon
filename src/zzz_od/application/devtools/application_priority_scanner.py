from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApplicationPriorityItem:
    app_id: str
    app_name: str
    default_group: bool
    priority: int | None
    source: str
    const_file: Path


def _read_const_fields(const_file: Path) -> dict[str, object]:
    field_names = {'APP_ID', 'APP_NAME', 'DEFAULT_GROUP', 'PRIORITY'}
    fields: dict[str, object] = {}
    tree = ast.parse(const_file.read_text(encoding='utf-8'), filename=str(const_file))

    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [target for target in node.targets if isinstance(target, ast.Name)]
            value_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target]
            value_node = node.value
        else:
            continue

        if value_node is None:
            continue
        for target in targets:
            if target.id in field_names:
                fields[target.id] = ast.literal_eval(value_node)

    return fields


def _scan_directory(
    directory: Path,
    source: str,
    project_root: Path,
) -> tuple[list[ApplicationPriorityItem], list[str]]:
    items: list[ApplicationPriorityItem] = []
    errors: list[str] = []
    app_dirs = sorted({factory_file.parent for factory_file in directory.rglob('*_factory.py')})

    for app_dir in app_dirs:
        factory_files = sorted(app_dir.glob('*_factory.py'))
        const_files = sorted(app_dir.glob('*_const.py'))
        relative_dir = app_dir.relative_to(project_root)
        if len(factory_files) != 1:
            errors.append(f'{relative_dir}: 应用目录必须只有一个 factory 文件')
            continue
        if len(const_files) != 1:
            errors.append(f'{relative_dir}: 应用目录必须只有一个 const 文件')
            continue

        const_file = const_files[0]
        try:
            fields = _read_const_fields(const_file)
            app_id = fields.get('APP_ID')
            app_name = fields.get('APP_NAME')
            default_group = fields.get('DEFAULT_GROUP')
            priority = fields.get('PRIORITY')

            if not isinstance(app_id, str):
                raise ValueError('APP_ID 必须为字符串')
            if not isinstance(app_name, str):
                raise ValueError('APP_NAME 必须为字符串')
            if not isinstance(default_group, bool):
                raise ValueError('DEFAULT_GROUP 必须为布尔值')
            if priority is not None and (
                not isinstance(priority, int) or isinstance(priority, bool)
            ):
                raise ValueError('PRIORITY 必须为整数')
        except (SyntaxError, ValueError) as exc:
            errors.append(f'{const_file.relative_to(project_root)}: {exc}')
            continue

        items.append(
            ApplicationPriorityItem(
                app_id=app_id,
                app_name=app_name,
                default_group=default_group,
                priority=priority,
                source=source,
                const_file=const_file.relative_to(project_root),
            )
        )

    return items, errors


def scan_application_priorities() -> tuple[list[ApplicationPriorityItem], list[str]]:
    project_root = Path(__file__).resolve().parents[4]
    application_dir = Path(__file__).resolve().parents[1]
    scan_dirs = [(application_dir, 'builtin')]
    plugins_dir = project_root / 'plugins'
    if plugins_dir.is_dir():
        scan_dirs.append((plugins_dir, 'third_party'))

    items: list[ApplicationPriorityItem] = []
    errors: list[str] = []
    for directory, source in scan_dirs:
        directory_items, directory_errors = _scan_directory(
            directory,
            source,
            project_root,
        )
        items.extend(directory_items)
        errors.extend(directory_errors)

    items.sort(
        key=lambda item: (
            item.priority is None,
            item.priority if item.priority is not None else 0,
            item.app_id,
        )
    )
    return items, errors


def main() -> int:
    items, errors = scan_application_priorities()
    print(f'APP 优先级扫描结果：{len(items)} 个应用')
    print('PRIORITY  DEFAULT  SOURCE       APP_ID                           APP_NAME  CONST_FILE')
    for item in items:
        priority = str(item.priority) if item.priority is not None else '-'
        default_group = 'yes' if item.default_group else 'no'
        print(
            f'{priority:>8}  {default_group:<7}  {item.source:<11}  '
            f'{item.app_id:<32} {item.app_name}  {item.const_file}'
        )

    if errors:
        print('\n扫描失败：', file=sys.stderr)
        for error in errors:
            print(f'- {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
