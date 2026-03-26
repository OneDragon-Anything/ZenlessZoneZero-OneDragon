from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)


class IntelBoardAppSetting(AppSettingProvider):
    app_id = "intel_board"
    setting_type = SettingType.FLYOUT

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.intel_board_setting_flyout import (
            IntelBoardSettingFlyout,
        )

        return IntelBoardSettingFlyout
