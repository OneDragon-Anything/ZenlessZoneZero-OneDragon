from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.hollow_zero.hollow_eval_speed.hollow_eval_speed_const import (
    APP_ID,
)


class HollowEvalSpeedAppSetting(AppSettingProvider):
    app_id = APP_ID
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.view.hollow_zero.hollow_eval_speed_setting_interface import (
            HollowEvalSpeedSettingInterface,
        )

        return HollowEvalSpeedSettingInterface
