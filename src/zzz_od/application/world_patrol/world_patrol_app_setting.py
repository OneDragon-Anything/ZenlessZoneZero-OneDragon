from one_dragon_qt.services.app_setting.app_setting_provider import (
    AppSettingProvider,
    SettingType,
)


class WorldPatrolAppSetting(AppSettingProvider):
    app_id = "world_patrol"
    setting_type = SettingType.INTERFACE

    @staticmethod
    def get_setting_cls() -> type:
        from zzz_od.gui.app_setting.world_patrol_combined_setting_interface import (
            WorldPatrolCombinedSettingInterface,
        )

        return WorldPatrolCombinedSettingInterface
