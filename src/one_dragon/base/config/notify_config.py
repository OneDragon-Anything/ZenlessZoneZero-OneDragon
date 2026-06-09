from __future__ import annotations

from enum import Enum
from typing import cast

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.user_config import UserConfig


class NotifyLevel:
    """旧版通知等级，仅用于迁移已有配置。"""

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


class NotifyConfig(UserConfig):

    def __init__(self, instance_idx: int, app_map: dict[str, str]) -> None:
        UserConfig.__init__(self, 'notify', instance_idx=instance_idx)
        self.app_map = app_map.copy()
        self._migrate_legacy_config()

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
    def merge_error_immediate_notify(self) -> bool:
        return self.get('merge_error_immediate_notify', self.get('notify_on_error', True))

    @merge_error_immediate_notify.setter
    def merge_error_immediate_notify(self, new_value: bool) -> None:
        self.update('merge_error_immediate_notify', new_value)

    @property
    def application_notify_settings(self) -> dict[str, dict[str, str]]:
        value = self.get('applications', {})
        if not isinstance(value, dict):
            return {}
        return cast(dict[str, dict[str, str]], value)

    def get_app_notify_modes(self, app_id: str) -> tuple[str, str]:
        """
        获取应用通知二维模式。
        """
        app_setting = self.application_notify_settings.get(app_id)
        if isinstance(app_setting, dict):
            lifecycle = app_setting.get('lifecycle', NotifyLifecycleMode.START_AND_FINISH.value.value)
            detail = app_setting.get('detail', NotifyDetailMode.ALL.value.value)
            return lifecycle, detail

        return self._get_legacy_modes(app_id)

    def set_app_notify_modes(
        self,
        app_id: str,
        lifecycle: str | None = None,
        detail: str | None = None,
    ) -> None:
        """
        设置应用通知二维模式。
        """
        current_lifecycle, current_detail = self.get_app_notify_modes(app_id)
        next_lifecycle = current_lifecycle if lifecycle is None else lifecycle
        next_detail = current_detail if detail is None else detail

        settings: dict[str, dict[str, str]] = {}
        for setting_app_id, app_setting in self.application_notify_settings.items():
            if isinstance(setting_app_id, str) and isinstance(app_setting, dict):
                settings[setting_app_id] = app_setting.copy()
        settings[app_id] = {
            'lifecycle': next_lifecycle,
            'detail': next_detail,
        }
        self.update('applications', settings)

    def get_app_lifecycle_mode(self, app_id: str) -> str:
        """
        获取应用生命周期通知模式。
        """
        lifecycle, _ = self.get_app_notify_modes(app_id)
        return lifecycle

    def set_app_lifecycle_mode(self, app_id: str, mode: str) -> None:
        """
        设置应用生命周期通知模式。
        """
        self.set_app_notify_modes(app_id, lifecycle=mode)

    def get_app_detail_mode(self, app_id: str) -> str:
        """
        获取节点细节通知模式。
        """
        _, detail = self.get_app_notify_modes(app_id)
        return detail

    def set_app_detail_mode(self, app_id: str, mode: str) -> None:
        """
        设置节点细节通知模式。
        """
        self.set_app_notify_modes(app_id, detail=mode)

    # ---------- 旧版配置迁移 2027/1/1 删除----------

    def _migrate_legacy_config(self) -> None:
        """
        将 main 分支旧版通知配置迁移为二维配置并落盘。
        """
        if isinstance(self.get('applications', None), dict):
            return

        setting: dict[str, dict[str, str]] = {}
        for app_id in self.app_map:
            lifecycle, detail = self._get_legacy_modes(app_id)
            setting[app_id] = {
                'lifecycle': lifecycle,
                'detail': detail,
            }

        self.update('applications', setting, save=False)
        self.update('merge_error_immediate_notify', self.get('notify_on_error', True), save=False)
        self.update('notify_schema_version', 2)

    def _get_legacy_modes(self, app_id: str) -> tuple[str, str]:
        """
        获取旧版配置映射出的新版二维模式。
        """
        level = int(self.get(app_id, NotifyLevel.ALL))
        return self._legacy_level_to_modes(level)

    def _legacy_level_to_modes(self, level: int) -> tuple[str, str]:
        """
        将旧版通知等级转换为新版二维模式。
        """
        if level <= NotifyLevel.OFF:
            return NotifyLifecycleMode.OFF.value.value, NotifyDetailMode.OFF.value.value
        lifecycle = (
            NotifyLifecycleMode.START_AND_FINISH.value.value
            if self.get('enable_before_notify', True)
            else NotifyLifecycleMode.FINISH_ONLY.value.value
        )
        if level == NotifyLevel.APP:
            detail = NotifyDetailMode.ERROR_ONLY.value.value if self.get('notify_on_error', True) else NotifyDetailMode.OFF.value.value
        elif level == NotifyLevel.MERGE:
            detail = NotifyDetailMode.MERGE.value.value
        else:
            detail = NotifyDetailMode.ALL.value.value
        return lifecycle, detail
