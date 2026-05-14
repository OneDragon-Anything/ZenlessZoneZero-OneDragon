from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.shiyu_defense.shiyu_defense_const import APP_ID


class ShiyuDefenseAppSetting(AppSettingProvider):
    app_id = APP_ID
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.shiyu_defense_setting_interface import (
            ShiyuDefenseSettingInterface,
        )

        return ShiyuDefenseSettingInterface
