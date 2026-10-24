from typing import Any

from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)


class InventoryMaintainAppSetting(AppSettingProvider):
    app_id = 'inventory_maintain'
    setting_type = SettingType.FLYOUT

    @staticmethod
    def get_setting_cls() -> Any:
        from zzz_od.application.inventory_maintain.inventory_maintain_settings import (
            InventoryMaintainSettings,
        )

        return InventoryMaintainSettings
