from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from one_dragon_qt.widgets.app_setting.app_setting_manager import AppSettingManager

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class ZAppSettingManager(AppSettingManager):

    def __init__(self, ctx: ZContext) -> None:
        AppSettingManager.__init__(self)
        self.ctx: ZContext = ctx

    # ──── Dialog（缓存实例）────

    def show_charge_plan_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.charge_plan_setting_dialog import (
            ChargePlanSettingDialog,
        )
        self._show_dialog(ChargePlanSettingDialog, self.ctx, parent, group_id)

    def show_coffee_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.coffee_setting_dialog import CoffeeSettingDialog
        self._show_dialog(CoffeeSettingDialog, self.ctx, parent, group_id)

    def show_lost_void_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.lost_void_setting_dialog import (
            LostVoidSettingDialog,
        )
        self._show_dialog(LostVoidSettingDialog, self.ctx, parent, group_id)

    def show_notorious_hunt_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.notorious_hunt_setting_dialog import (
            NotoriousHuntSettingDialog,
        )
        self._show_dialog(NotoriousHuntSettingDialog, self.ctx, parent, group_id)

    def show_redemption_code_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.redemption_code_setting_dialog import (
            RedemptionCodeSettingDialog,
        )
        self._show_dialog(RedemptionCodeSettingDialog, self.ctx, parent, group_id)

    def show_shiyu_defense_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.shiyu_defense_setting_dialog import (
            ShiyuDefenseSettingDialog,
        )
        self._show_dialog(ShiyuDefenseSettingDialog, self.ctx, parent, group_id)

    def show_suibian_temple_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.suibian_temple_setting_dialog import (
            SuibianTempleSettingDialog,
        )
        self._show_dialog(SuibianTempleSettingDialog, self.ctx, parent, group_id)

    def show_withered_domain_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.withered_domain_setting_dialog import (
            WitheredDomainSettingDialog,
        )
        self._show_dialog(WitheredDomainSettingDialog, self.ctx, parent, group_id)

    def show_world_patrol_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.world_patrol_setting_dialog import (
            WorldPatrolSettingDialog,
        )
        self._show_dialog(WorldPatrolSettingDialog, self.ctx, parent, group_id)

    # ──── Flyout（每次新建）────

    def show_drive_disc_dismantle_setting_flyout(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.drive_disc_dismantle_setting_flyout import (
            DriveDiscDismantleSettingFlyout,
        )
        self._show_flyout(DriveDiscDismantleSettingFlyout, self.ctx, parent, group_id, target)

    def show_intel_board_setting_flyout(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.intel_board_setting_flyout import (
            IntelBoardSettingFlyout,
        )
        self._show_flyout(IntelBoardSettingFlyout, self.ctx, parent, group_id, target)

    def show_life_on_line_setting_flyout(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.life_on_line_setting_flyout import (
            LifeOnLineSettingFlyout,
        )
        self._show_flyout(LifeOnLineSettingFlyout, self.ctx, parent, group_id, target)

    def show_random_play_setting_flyout(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.app_setting.random_play_setting_flyout import (
            RandomPlaySettingFlyout,
        )
        self._show_flyout(RandomPlaySettingFlyout, self.ctx, parent, group_id, target)
