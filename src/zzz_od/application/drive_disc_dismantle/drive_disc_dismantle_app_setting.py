from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_const import APP_ID


class DriveDiscDismantleAppSetting(AppSettingProvider):
    app_id = APP_ID
    setting_type = SettingType.FLYOUT

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.drive_disc_dismantle_setting_flyout import (
            DriveDiscDismantleSettingFlyout,
        )

        return DriveDiscDismantleSettingFlyout
