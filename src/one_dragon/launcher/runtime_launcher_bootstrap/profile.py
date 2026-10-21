from abc import ABC, abstractmethod


class RuntimeLauncherProfile(ABC):
    """具体项目需要提供的集成启动器配置。"""

    @property
    @abstractmethod
    def application_name(self) -> str:
        """返回启动器显示名称。"""
        raise NotImplementedError

    @property
    @abstractmethod
    def runtime_entry_module(self) -> str:
        """返回正常模式动态入口模块。"""
        raise NotImplementedError

    @property
    @abstractmethod
    def recovery_entry_module(self) -> str:
        """返回恢复模式动态入口模块。"""
        raise NotImplementedError

    @property
    @abstractmethod
    def required_external_files(self) -> tuple[str, ...]:
        """返回外部源码必须存在的文件。"""
        raise NotImplementedError

    @property
    @abstractmethod
    def required_builtin_files(self) -> tuple[str, ...]:
        """返回内置源码必须存在的文件。"""
        raise NotImplementedError

    @property
    def frozen_import_modules(self) -> tuple[str, ...]:
        """返回必须固定在启动器中的稳定模块。"""
        return ()

    def sync_source(self, launcher_version: str) -> bool:
        """同步外部源码；不需要同步的项目保持默认实现。

        Args:
            launcher_version: 当前启动内核版本。

        Returns:
            外部源码是否发生变化。
        """
        del launcher_version
        return False
