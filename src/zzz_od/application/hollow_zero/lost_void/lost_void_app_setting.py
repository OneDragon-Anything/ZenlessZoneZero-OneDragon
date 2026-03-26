from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)


class LostVoidAppSetting(AppSettingProvider):
    app_id = "lost_void"
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.lost_void_combined_setting_interface import (
            LostVoidCombinedSettingInterface,
        )

        return LostVoidCombinedSettingInterface
