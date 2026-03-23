from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from one_dragon_qt.widgets.app_setting.app_setting_manager import AppSettingManager

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class ZAppSettingManager(AppSettingManager):

    def __init__(self, ctx: ZContext) -> None:
        AppSettingManager.__init__(self, ctx)

    # ──── 单页设置界面（推入二级界面）────

    def show_charge_plan_setting(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.view.one_dragon.charge_plan_interface import ChargePlanInterface
        self._push_interface(ChargePlanInterface, parent)

    def show_coffee_setting(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.coffee_setting_interface import (
            CoffeeSettingInterface,
        )
        self._push_interface(CoffeeSettingInterface, parent)

    def show_notorious_hunt_setting(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.notorious_hunt_setting_interface import (
            NotoriousHuntSettingInterface,
        )
        self._push_interface(NotoriousHuntSettingInterface, parent)

    def show_redemption_code_setting(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.redemption_code_setting_interface import (
            RedemptionCodeSettingInterface,
        )
        self._push_interface(RedemptionCodeSettingInterface, parent)

    def show_shiyu_defense_setting(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.shiyu_defense_setting_interface import (
            ShiyuDefenseSettingInterface,
        )
        self._push_interface(ShiyuDefenseSettingInterface, parent)

    def show_suibian_temple_setting(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.suibian_temple_setting_interface import (
            SuibianTempleSettingInterface,
        )
        self._push_interface(SuibianTempleSettingInterface, parent)

    # ──── 多标签设置界面（推入二级界面）────

    def show_lost_void_setting(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.lost_void_combined_setting_interface import (
            LostVoidCombinedSettingInterface,
        )
        self._push_interface(LostVoidCombinedSettingInterface, parent)

    def show_withered_domain_setting(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.withered_domain_combined_setting_interface import (
            WitheredDomainCombinedSettingInterface,
        )
        self._push_interface(WitheredDomainCombinedSettingInterface, parent)

    def show_world_patrol_setting(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.world_patrol_combined_setting_interface import (
            WorldPatrolCombinedSettingInterface,
        )
        self._push_interface(WorldPatrolCombinedSettingInterface, parent)

    # ──── Flyout（保持不变）────

    def show_drive_disc_dismantle_setting_flyout(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.drive_disc_dismantle_setting_flyout import (
            DriveDiscDismantleSettingFlyout,
        )
        self._show_flyout(DriveDiscDismantleSettingFlyout, parent, group_id, target)

    def show_intel_board_setting_flyout(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.intel_board_setting_flyout import (
            IntelBoardSettingFlyout,
        )
        self._show_flyout(IntelBoardSettingFlyout, parent, group_id, target)

    def show_life_on_line_setting_flyout(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.life_on_line_setting_flyout import (
            LifeOnLineSettingFlyout,
        )
        self._show_flyout(LifeOnLineSettingFlyout, parent, group_id, target)

    def show_random_play_setting_flyout(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.random_play_setting_flyout import (
            RandomPlaySettingFlyout,
        )
        self._show_flyout(RandomPlaySettingFlyout, parent, group_id, target)
