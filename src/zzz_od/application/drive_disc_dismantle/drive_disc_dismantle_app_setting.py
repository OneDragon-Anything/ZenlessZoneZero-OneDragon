from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)


class DriveDiscDismantleAppSetting(AppSettingProvider):
    app_id = "drive_disc_dismantle"
    setting_type = SettingType.FLYOUT

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.drive_disc_dismantle_setting_flyout import (
            DriveDiscDismantleSettingFlyout,
        )

        return DriveDiscDismantleSettingFlyout
