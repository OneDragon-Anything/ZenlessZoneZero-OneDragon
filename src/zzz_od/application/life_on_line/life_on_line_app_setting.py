from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.life_on_line.life_on_line_const import APP_ID


class LifeOnLineAppSetting(AppSettingProvider):
    app_id = APP_ID
    setting_type = SettingType.FLYOUT

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.life_on_line_setting_flyout import (
            LifeOnLineSettingFlyout,
        )

        return LifeOnLineSettingFlyout
