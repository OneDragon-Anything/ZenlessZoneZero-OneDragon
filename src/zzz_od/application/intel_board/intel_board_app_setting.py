from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.intel_board.intel_board_const import APP_ID


class IntelBoardAppSetting(AppSettingProvider):
    app_id = APP_ID
    setting_type = SettingType.FLYOUT

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.intel_board_setting_flyout import (
            IntelBoardSettingFlyout,
        )

        return IntelBoardSettingFlyout
