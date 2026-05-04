from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.suibian_temple.suibian_temple_const import APP_ID


class SuibianTempleAppSetting(AppSettingProvider):
    app_id = APP_ID
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.suibian_temple_setting_interface import (
            SuibianTempleSettingInterface,
        )

        return SuibianTempleSettingInterface
