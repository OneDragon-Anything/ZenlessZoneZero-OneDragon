from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.bagel.bagel_const import APP_ID


class BagelAppSetting(AppSettingProvider):
    """独立应用设置入口。"""

    app_id: str = APP_ID
    setting_type: SettingType = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        """延迟加载 Qt 设置组件。"""
        from zzz_od.gui.app_setting.bagel_setting_interface import BagelSettingInterface

        return BagelSettingInterface
