from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.notorious_hunt.notorious_hunt_const import APP_ID


class NotoriousHuntAppSetting(AppSettingProvider):
    app_id = APP_ID
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.notorious_hunt_setting_interface import (
            NotoriousHuntSettingInterface,
        )

        return NotoriousHuntSettingInterface
