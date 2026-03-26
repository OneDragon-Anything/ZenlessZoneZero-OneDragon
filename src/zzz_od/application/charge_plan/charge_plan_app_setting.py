from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)


class ChargePlanAppSetting(AppSettingProvider):
    app_id = "charge_plan"
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.view.one_dragon.charge_plan_interface import ChargePlanInterface

        return ChargePlanInterface
