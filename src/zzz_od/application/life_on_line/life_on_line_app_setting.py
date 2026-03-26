from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)


class LifeOnLineAppSetting(AppSettingProvider):
    app_id = "life_on_line"
    setting_type = SettingType.FLYOUT

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.life_on_line_setting_flyout import (
            LifeOnLineSettingFlyout,
        )

        return LifeOnLineSettingFlyout
