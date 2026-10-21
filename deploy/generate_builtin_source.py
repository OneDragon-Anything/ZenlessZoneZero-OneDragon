# ruff: noqa: E402

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / 'src'
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from one_dragon.launcher.runtime_launcher_bootstrap.builtin_manifest import (
    MANIFEST_SCHEMA_VERSION,
)
from one_dragon.launcher.runtime_launcher_bootstrap.profile import (
    RuntimeLauncherProfile,
)
from one_dragon.launcher.runtime_launcher_bootstrap.runtime_identity import (
    get_runtime_id,
)
from one_dragon.version import __version__
from zzz_od.win_exe.runtime_launcher_profile import ZRuntimeLauncherProfile


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _should_skip(path: Path) -> bool:
    return '__pycache__' in path.parts or path.suffix == '.pyc'


def _copy_source(source_root: Path, target_root: Path) -> None:
    for source_path in sorted(source_root.rglob('*')):
        relative_path = source_path.relative_to(source_root)
        if _should_skip(relative_path):
            continue
        if source_path.is_symlink():
            raise ValueError(f'内置源码不能包含符号链接: {relative_path}')

        target_path = target_root / relative_path
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
        elif source_path.is_file():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)


def _build_manifest(
    source_root: Path,
    release_version: str,
    required_files: tuple[str, ...],
) -> dict[str, object]:
    files: list[dict[str, object]] = []
    for path in sorted(source_root.rglob('*')):
        if not path.is_file():
            continue
        relative_path = path.relative_to(source_root).as_posix()
        files.append(
            {
                'path': relative_path,
                'size': path.stat().st_size,
                'sha256': _sha256(path),
            }
        )

    return {
        'schema_version': MANIFEST_SCHEMA_VERSION,
        'release_version': release_version,
        'runtime_id': get_runtime_id(),
        'required_files': list(required_files),
        'files': files,
    }


def _validate_paths(
    source_root: Path,
    output_root: Path,
    required_files: tuple[str, ...],
) -> None:
    if not source_root.is_dir():
        raise FileNotFoundError(f'源码目录不存在: {source_root}')
    if (
        source_root == output_root
        or source_root.is_relative_to(output_root)
        or output_root.is_relative_to(source_root)
    ):
        raise ValueError('源码目录与内置快照输出目录不能重叠')

    missing = [
        relative_path
        for relative_path in required_files
        if not (source_root / relative_path).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f'源码缺少恢复模式必要入口: {", ".join(missing)}'
        )


def generate_builtin_source(
    source_root: Path,
    output_root: Path,
    release_version: str,
    profile: RuntimeLauncherProfile | None = None,
) -> Path:
    """复制完整源码并生成恢复模式完整性清单。"""
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if profile is None:
        profile = ZRuntimeLauncherProfile()
    _validate_paths(source_root, output_root, profile.required_builtin_files)
    if not release_version:
        raise ValueError('发行版本不能为空')

    if output_root.exists():
        shutil.rmtree(output_root)
    builtin_src = output_root / 'src'
    builtin_src.mkdir(parents=True)
    _copy_source(source_root, builtin_src)

    manifest = _build_manifest(
        builtin_src,
        release_version,
        profile.required_builtin_files,
    )
    manifest_path = output_root / 'manifest.json'
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    return manifest_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description='生成集成启动器内置源码快照')
    parser.add_argument(
        '--source-root',
        type=Path,
        default=repo_root / 'src',
        help='需要完整复制的 src 目录',
    )
    parser.add_argument(
        '--output-root',
        type=Path,
        required=True,
        help='输出 builtin_src 目录',
    )
    parser.add_argument(
        '--release-version',
        default=__version__,
        help='写入清单的集成启动器发行版本',
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    manifest_path = generate_builtin_source(
        args.source_root,
        args.output_root,
        args.release_version,
    )
    print(f'内置源码清单已生成: {manifest_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
