from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.devtools.shiyu_defense_team_test.shiyu_defense_team_test_const import (
    APP_ID,
)


class ShiyuDefenseTeamTestAppSetting(AppSettingProvider):
    app_id = APP_ID
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.shiyu_defense_team_test_setting_interface import (
            ShiyuDefenseTeamTestInterface,
        )

        return ShiyuDefenseTeamTestInterface
