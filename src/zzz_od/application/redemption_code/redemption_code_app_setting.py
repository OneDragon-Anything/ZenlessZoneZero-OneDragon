from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)


class RedemptionCodeAppSetting(AppSettingProvider):
    app_id = "redemption_code"
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.redemption_code_setting_interface import (
            RedemptionCodeSettingInterface,
        )

        return RedemptionCodeSettingInterface
