from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)
from zzz_od.application.hollow_zero.withered_domain.withered_domain_const import APP_ID


class WitheredDomainAppSetting(AppSettingProvider):
    app_id = APP_ID
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.withered_domain_combined_setting_interface import (
            WitheredDomainCombinedSettingInterface,
        )

        return WitheredDomainCombinedSettingInterface
