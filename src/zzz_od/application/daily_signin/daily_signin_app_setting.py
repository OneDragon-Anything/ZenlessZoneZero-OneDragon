from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.daily_signin.daily_signin_const import APP_ID


class DailySignInAppSetting(AppSettingProvider):
    app_id: str = APP_ID
    setting_type: SettingType = SettingType.FLYOUT

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.daily_signin_setting_flyout import (
            DailySignInSettingFlyout,
        )

        return DailySignInSettingFlyout
