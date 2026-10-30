from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_const import APP_ID


class LostVoidAppSetting(AppSettingProvider):
    app_id = APP_ID
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.lost_void_combined_setting_interface import (
            LostVoidCombinedSettingInterface,
        )

        return LostVoidCombinedSettingInterface
