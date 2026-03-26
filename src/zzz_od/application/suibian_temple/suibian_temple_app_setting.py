from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)


class SuibianTempleAppSetting(AppSettingProvider):
    app_id = "suibian_temple"
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.suibian_temple_setting_interface import (
            SuibianTempleSettingInterface,
        )

        return SuibianTempleSettingInterface
