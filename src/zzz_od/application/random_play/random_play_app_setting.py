from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.random_play.random_play_const import APP_ID


class RandomPlayAppSetting(AppSettingProvider):
    app_id = APP_ID
    setting_type = SettingType.FLYOUT

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.random_play_setting_flyout import (
            RandomPlaySettingFlyout,
        )

        return RandomPlaySettingFlyout
