import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from one_dragon.launcher.runtime_launcher_bootstrap.builtin_manifest import (
    MANIFEST_SCHEMA_VERSION,
)
from one_dragon.launcher.runtime_launcher_bootstrap.profile import (
    RuntimeLauncherProfile,
)
from one_dragon.launcher.runtime_launcher_bootstrap.runtime_identity import (
    get_runtime_id,
)


class BuiltinSourceValidator:
    """校验内置源码目录和清单是否与当前启动内核匹配。"""

    def __init__(
        self,
        source_root: Path,
        manifest_path: Path,
        version: str,
        profile: RuntimeLauncherProfile,
    ) -> None:
        """创建内置源码校验器。

        Args:
            source_root: 内置源码根目录。
            manifest_path: 内置源码清单路径。
            version: 当前启动内核版本。
            profile: 当前项目要求的源码入口。
        """
        self.source_root: Path = source_root
        self.manifest_path: Path = manifest_path
        self.version: str = version
        self.profile: RuntimeLauncherProfile = profile

    def validate(self) -> None:
        """校验清单版本、必要入口和每个文件的摘要。"""
        if not self.manifest_path.is_file():
            raise FileNotFoundError(f'缺少内置源码清单: {self.manifest_path}')
        if not self.source_root.is_dir():
            raise FileNotFoundError(f'缺少内置源码目录: {self.source_root}')

        manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        self._validate_manifest_identity(manifest)
        recorded_paths = self._validate_recorded_files(manifest)
        self._validate_directory_matches_records(recorded_paths)

    def _validate_manifest_identity(self, manifest: object) -> None:
        """校验清单格式、版本和运行时标识。"""
        if not isinstance(manifest, dict):
            raise ValueError('内置源码清单格式错误')
        if manifest.get('schema_version') != MANIFEST_SCHEMA_VERSION:
            raise ValueError('内置源码清单版本不受支持')
        if manifest.get('release_version') != self.version:
            raise ValueError(
                '内置源码版本与启动内核不一致: '
                f'{manifest.get("release_version")} != {self.version}'
            )
        current_runtime_id = get_runtime_id()
        if manifest.get('runtime_id') != current_runtime_id:
            raise ValueError(
                '内置源码运行时标识不一致: '
                f'{manifest.get("runtime_id")} != {current_runtime_id}'
            )

        manifest_required = manifest.get('required_files')
        if not isinstance(manifest_required, list):
            raise ValueError('内置源码清单缺少 required_files')
        missing_required = sorted(
            set(self.profile.required_builtin_files) - set(manifest_required)
        )
        if missing_required:
            raise ValueError(
                f'内置源码清单缺少必要入口: {", ".join(missing_required)}'
            )

    def _validate_recorded_files(self, manifest: dict[str, Any]) -> set[str]:
        """校验清单记录的文件都存在且摘要一致。"""
        files = manifest.get('files')
        if not isinstance(files, list) or not files:
            raise ValueError('内置源码清单没有文件记录')

        recorded_paths: set[str] = set()
        for item in files:
            relative_path = self._validate_file_record(item, recorded_paths)
            recorded_paths.add(relative_path)

        missing_records = sorted(
            set(self.profile.required_builtin_files) - recorded_paths
        )
        if missing_records:
            raise ValueError(
                f'内置源码必要入口没有摘要记录: {", ".join(missing_records)}'
            )
        return recorded_paths

    def _validate_file_record(
        self,
        item: object,
        recorded_paths: set[str],
    ) -> str:
        """校验一条文件记录的路径、大小和摘要。"""
        if not isinstance(item, dict):
            raise ValueError('内置源码文件记录格式错误')
        relative_path = self._validate_manifest_path(item.get('path'))
        expected_size = item.get('size')
        expected_hash = item.get('sha256')
        if not isinstance(expected_size, int) or expected_size < 0:
            raise ValueError(f'内置源码文件大小无效: {relative_path}')
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise ValueError(f'内置源码文件摘要无效: {relative_path}')
        if relative_path in recorded_paths:
            raise ValueError(f'内置源码清单路径重复: {relative_path}')

        source_file = self.source_root.joinpath(*PurePosixPath(relative_path).parts)
        if source_file.is_symlink():
            raise ValueError(f'内置源码文件不能是符号链接: {relative_path}')
        if not source_file.is_file():
            raise FileNotFoundError(f'内置源码文件缺失: {relative_path}')
        if source_file.stat().st_size != expected_size:
            raise ValueError(f'内置源码文件大小不一致: {relative_path}')
        if self._sha256(source_file) != expected_hash:
            raise ValueError(f'内置源码文件校验失败: {relative_path}')
        return relative_path

    def _validate_directory_matches_records(self, recorded_paths: set[str]) -> None:
        """校验源码目录没有清单之外的文件。"""
        actual_paths = {
            path.relative_to(self.source_root).as_posix()
            for path in self.source_root.rglob('*')
            if path.is_file()
        }
        extra_paths = sorted(actual_paths - recorded_paths)
        if extra_paths:
            raise ValueError(
                f'内置源码包含清单外文件: {", ".join(extra_paths[:10])}'
            )

    @staticmethod
    def _validate_manifest_path(value: Any) -> str:
        """校验清单路径是相对路径且不包含上级目录。"""
        if not isinstance(value, str) or not value:
            raise ValueError('内置源码清单包含空路径')
        path = PurePosixPath(value)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError(f'内置源码清单包含非法路径: {value}')
        return path.as_posix()

    @staticmethod
    def _sha256(path: Path) -> str:
        """计算文件的 SHA256 摘要。"""
        digest = hashlib.sha256()
        with path.open('rb') as file:
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
