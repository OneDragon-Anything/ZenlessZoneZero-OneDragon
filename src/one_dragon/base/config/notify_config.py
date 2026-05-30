from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig


class NotifyLevel:
    """旧版通知等级，仅用于兼容 main 分支已有配置。"""

    OFF = 0
    APP = 1
    ALL = 2
    MERGE = 3


class NotifyLifecycleMode(Enum):
    """应用生命周期通知模式。"""

    OFF = ConfigItem(label='关闭', value='off', desc='不发送开始和结束通知')
    FINISH_ONLY = ConfigItem(label='仅结束', value='finish_only', desc='应用完成后发送通知')
    START_AND_FINISH = ConfigItem(label='开始和结束', value='start_and_finish', desc='应用开始和完成时发送通知')


class NotifyDetailMode(Enum):
    """节点细节通知模式。"""

    OFF = ConfigItem(label='关闭', value='off', desc='不发送节点细节通知')
    ERROR_ONLY = ConfigItem(label='仅失败', value='error_only', desc='只在节点失败时立即通知')
    ALL = ConfigItem(label='逐条', value='all', desc='每个标记节点完成后立即通知')
    MERGE = ConfigItem(label='合并', value='merge', desc='应用结束时合并发送节点细节')


class NotifyConfig(YamlConfig):

    def __init__(self, instance_idx: int, app_map: dict[str, str]) -> None:
        YamlConfig.__init__(self, 'notify', instance_idx=instance_idx)
        self.app_map = app_map.copy()
        self._migrate_legacy_config()

    def __getattr__(self, name: str) -> Mapping[str, str]:
        """
        按 app_map 动态解析应用通知配置。
        """
        app_map = self.__dict__.get('app_map')
        if isinstance(app_map, dict) and name in app_map:
            return MappingProxyType({
                'lifecycle': self.get_app_lifecycle_mode(name),
                'detail': self.get_app_detail_mode(name),
            })
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: object) -> None:
        """
        按 app_map 动态写入应用通知配置，避免把动态字段挂到类级别。
        """
        app_map = self.__dict__.get('app_map')
        if isinstance(app_map, dict) and name in app_map:
            self._set_app_modes(name, value)
            return
        object.__setattr__(self, name, value)

    @property
    def title(self) -> str:
        return self.get('title', '一条龙运行通知')

    @title.setter
    def title(self, new_value: str) -> None:
        self.update('title', new_value)

    @property
    def enable_notify(self) -> bool:
        return self.get('enable_notify', True)

    @enable_notify.setter
    def enable_notify(self, new_value: bool) -> None:
        self.update('enable_notify', new_value)

    @property
    def enable_before_notify(self) -> bool:
        return self.get('enable_before_notify', True)

    @enable_before_notify.setter
    def enable_before_notify(self, new_value: bool) -> None:
        self.update('enable_before_notify', new_value)

    @property
    def notify_on_error(self) -> bool:
        return self.get('notify_on_error', True)

    @notify_on_error.setter
    def notify_on_error(self, new_value: bool) -> None:
        self.update('notify_on_error', new_value)

    @property
    def merge_error_immediate_notify(self) -> bool:
        return self.get('merge_error_immediate_notify', self.notify_on_error)

    @merge_error_immediate_notify.setter
    def merge_error_immediate_notify(self, new_value: bool) -> None:
        self.update('merge_error_immediate_notify', new_value)

    @property
    def application_notify_settings(self) -> dict[str, dict[str, object]]:
        value = self.get('applications', {})
        if not isinstance(value, dict):
            return {}
        return value

    def get_app_lifecycle_mode(self, app_id: str) -> str:
        """
        获取应用生命周期通知模式。
        """
        app_setting = self._get_app_setting(app_id)
        if app_setting is not None:
            mode = app_setting.get('lifecycle', NotifyLifecycleMode.START_AND_FINISH.value.value)
            return self._normalize_lifecycle_mode(mode)

        lifecycle_mode, _ = self._get_legacy_app_modes(app_id)
        return lifecycle_mode

    def set_app_lifecycle_mode(self, app_id: str, mode: str) -> None:
        """
        设置应用生命周期通知模式。
        """
        setting = self._copy_app_settings()
        app_setting = setting.get(app_id, {})
        app_setting['lifecycle'] = self._normalize_lifecycle_mode(mode)
        app_setting.setdefault('detail', self.get_app_detail_mode(app_id))
        setting[app_id] = app_setting
        self.update('applications', setting)

    def get_app_detail_mode(self, app_id: str) -> str:
        """
        获取节点细节通知模式。
        """
        app_setting = self._get_app_setting(app_id)
        if app_setting is not None:
            mode = app_setting.get('detail', NotifyDetailMode.ALL.value.value)
            return self._normalize_detail_mode(mode)

        _, detail_mode = self._get_legacy_app_modes(app_id)
        return detail_mode

    def set_app_detail_mode(self, app_id: str, mode: str) -> None:
        """
        设置节点细节通知模式。
        """
        setting = self._copy_app_settings()
        app_setting = setting.get(app_id, {})
        app_setting.setdefault('lifecycle', self.get_app_lifecycle_mode(app_id))
        app_setting['detail'] = self._normalize_detail_mode(mode)
        setting[app_id] = app_setting
        self.update('applications', setting)

    def _get_app_setting(self, app_id: str) -> dict[str, object] | None:
        """
        获取新版应用通知配置。
        """
        if not app_id:
            return None

        app_setting = self.application_notify_settings.get(app_id)
        return app_setting if isinstance(app_setting, dict) else None

    def _copy_app_settings(self) -> dict[str, dict[str, object]]:
        """
        复制新版应用通知配置，避免直接修改 YAML 数据引用。
        """
        result: dict[str, dict[str, object]] = {}
        for app_id, app_setting in self.application_notify_settings.items():
            if isinstance(app_id, str) and isinstance(app_setting, dict):
                result[app_id] = app_setting.copy()
        return result

    def _set_app_modes(self, app_id: str, value: object) -> None:
        """
        写入动态应用通知配置。
        """
        if isinstance(value, dict):
            lifecycle = self._normalize_lifecycle_mode(
                value.get('lifecycle', self.get_app_lifecycle_mode(app_id))
            )
            detail = self._normalize_detail_mode(
                value.get('detail', self.get_app_detail_mode(app_id))
            )
        else:
            lifecycle, detail = self._legacy_level_to_modes(int(value))

        setting = self._copy_app_settings()
        setting[app_id] = {
            'lifecycle': lifecycle,
            'detail': detail,
        }
        self.update('applications', setting)

    def _normalize_lifecycle_mode(self, value: object) -> str:
        """
        归一化应用生命周期通知模式。
        """
        if value is False:
            return NotifyLifecycleMode.OFF.value.value
        if isinstance(value, NotifyLifecycleMode):
            return str(value.value.value)
        valid_values = tuple(item.value.value for item in NotifyLifecycleMode)
        if value in valid_values:
            return str(value)
        return NotifyLifecycleMode.START_AND_FINISH.value.value

    def _normalize_detail_mode(self, value: object) -> str:
        """
        归一化节点细节通知模式。
        """
        if value is False:
            return NotifyDetailMode.OFF.value.value
        if isinstance(value, NotifyDetailMode):
            return str(value.value.value)
        valid_values = tuple(item.value.value for item in NotifyDetailMode)
        if value in valid_values:
            return str(value)
        return NotifyDetailMode.ALL.value.value

    # ---------- 旧版配置迁移与兼容 2027/1/1 删除----------

    def get_app_notify_level(self, app_id: str) -> int:
        """
        获取旧版通知等级。

        新代码请使用 get_app_lifecycle_mode 和 get_app_detail_mode。
        """
        return self._get_legacy_app_notify_level(app_id)

    def _migrate_legacy_config(self) -> None:
        """
        将 main 分支旧版通知配置迁移为二维配置并落盘。
        """
        if isinstance(self.get('applications', None), dict):
            return

        setting: dict[str, dict[str, str]] = {}
        for app_id in self.app_map:
            lifecycle, detail = self._get_legacy_app_modes(app_id)
            setting[app_id] = {
                'lifecycle': lifecycle,
                'detail': detail,
            }

        self.update('applications', setting, save=False)
        self.update('merge_error_immediate_notify', self.notify_on_error, save=False)
        self.update('notify_schema_version', 2)

    def _get_legacy_app_modes(self, app_id: str) -> tuple[str, str]:
        """
        获取旧版配置映射出的新版二维模式。
        """
        return self._legacy_level_to_modes(self._get_legacy_app_notify_level(app_id))

    def _get_legacy_app_notify_level(self, app_id: str) -> int:
        """
        获取 main 分支旧版通知等级。
        0: 关闭
        1: 仅应用
        2: 全部（应用和节点，逐条发送）
        3: 合并（应用和节点，合并发送）
        """
        if not app_id:
            return NotifyLevel.ALL

        return int(self.get(app_id, NotifyLevel.ALL))

    def _legacy_level_to_modes(self, level: int) -> tuple[str, str]:
        """
        将旧版通知等级转换为新版二维模式。
        """
        if level <= NotifyLevel.OFF:
            return NotifyLifecycleMode.OFF.value.value, NotifyDetailMode.OFF.value.value
        lifecycle = (
            NotifyLifecycleMode.START_AND_FINISH.value.value
            if self.enable_before_notify
            else NotifyLifecycleMode.FINISH_ONLY.value.value
        )
        if level == NotifyLevel.APP:
            detail = NotifyDetailMode.ERROR_ONLY.value.value if self.notify_on_error else NotifyDetailMode.OFF.value.value
        elif level == NotifyLevel.MERGE:
            detail = NotifyDetailMode.MERGE.value.value
        else:
            detail = NotifyDetailMode.ALL.value.value
        return lifecycle, detail
