from one_dragon.launcher.runtime_launcher_bootstrap.profile import (
    RuntimeLauncherProfile,
)
from zzz_od.win_exe.source_sync import sync_external_source


class ZRuntimeLauncherProfile(RuntimeLauncherProfile):
    """绝区零项目的集成启动器配置。"""

    @property
    def application_name(self) -> str:
        return '绝区零 一条龙 启动器'

    @property
    def runtime_entry_module(self) -> str:
        """返回正常模式动态入口模块。"""
        return 'zzz_od.win_exe.runtime_launcher'

    @property
    def recovery_entry_module(self) -> str:
        """返回恢复模式动态入口模块。"""
        return 'zzz_od.win_exe.recovery_app'

    @property
    def required_external_files(self) -> tuple[str, ...]:
        """返回外部源码必须存在的文件。"""
        return (
            'zzz_od/win_exe/source_sync.py',
            'zzz_od/win_exe/runtime_launcher.py',
            'zzz_od/gui/app.py',
            'zzz_od/application/zzz_application_launcher.py',
        )

    def sync_source(self, launcher_version: str) -> bool:
        """按绝区零配置同步外部源码。"""
        return sync_external_source(launcher_version)

    @property
    def frozen_import_modules(self) -> tuple[str, ...]:
        """返回必须固定在启动器中的稳定模块。"""
        return (
            'one_dragon.envs.recovery_repair_service',
        )

    @property
    def required_builtin_files(self) -> tuple[str, ...]:
        """返回内置源码必须存在的文件。"""
        return (
            'one_dragon/__init__.py',
            'one_dragon_qt/__init__.py',
            'zzz_od/__init__.py',
            'onnxocr/__init__.py',
            'zzz_od/win_exe/source_sync.py',
            'zzz_od/win_exe/runtime_launcher.py',
            'zzz_od/win_exe/recovery_app.py',
        )
