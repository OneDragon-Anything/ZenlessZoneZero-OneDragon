from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from zzz_od.gui.dialog.charge_plan_setting_dialog import ChargePlanSettingDialog
from zzz_od.gui.dialog.coffee_setting_dialog import CoffeeSettingDialog
from zzz_od.gui.dialog.drive_disc_dismantle_setting_dialog import (
    DriveDiscDismantleSettingDialog,
)
from zzz_od.gui.dialog.intel_board_setting_dialog import IntelBoardSettingFlyout
from zzz_od.gui.dialog.lost_void_setting_dialog import LostVoidSettingDialog
from zzz_od.gui.dialog.notorious_hunt_setting_dialog import NotoriousHuntSettingDialog
from zzz_od.gui.dialog.random_play_setting_dialog import RandomPlaySettingDialog
from zzz_od.gui.dialog.redemption_code_setting_dialog import RedemptionCodeSettingDialog
from zzz_od.gui.dialog.suibian_temple_setting_dialog import SuibianTempleSettingDialog
from zzz_od.gui.dialog.withered_domain_setting_dialog import WitheredDomainSettingDialog
from zzz_od.gui.dialog.world_patrol_setting_dialog import WorldPatrolSettingDialog

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext

class SharedDialogManager:

    def __init__(self, ctx: ZContext) -> None:
        self.ctx: ZContext = ctx
        self._world_patrol_setting_dialog: WorldPatrolSettingDialog | None = None
        self._suibian_temple_setting_dialog: SuibianTempleSettingDialog | None = None
        self._charge_plan_setting_dialog: ChargePlanSettingDialog | None = None
        self._notorious_hunt_setting_dialog: NotoriousHuntSettingDialog | None = None
        self._coffee_setting_dialog: CoffeeSettingDialog | None = None
        self._random_play_setting_dialog: RandomPlaySettingDialog | None = None
        self._drive_disc_dismantle_setting_dialog: DriveDiscDismantleSettingDialog | None = None
        self._withered_domain_setting_dialog: WitheredDomainSettingDialog | None = None
        self._lost_void_setting_dialog: LostVoidSettingDialog | None = None
        self._redemption_code_setting_dialog: RedemptionCodeSettingDialog | None = None

    def show_world_patrol_setting_dialog(
        self,
        parent: QWidget,
        group_id: str,
    ) -> None:
        if self._world_patrol_setting_dialog is None:
            self._world_patrol_setting_dialog = WorldPatrolSettingDialog(ctx=self.ctx, parent=parent)

        self._world_patrol_setting_dialog.show_by_group(
            group_id=group_id,
            parent=parent,
        )

    def show_suibian_temple_setting_dialog(
        self,
        parent: QWidget,
        group_id: str,
    ) -> None:
        if self._suibian_temple_setting_dialog is None:
            self._suibian_temple_setting_dialog = SuibianTempleSettingDialog(ctx=self.ctx, parent=parent)

        self._suibian_temple_setting_dialog.show_by_group(
            group_id=group_id,
            parent=parent,
        )

    def show_charge_plan_setting_dialog(
        self,
        parent: QWidget,
        group_id: str,
    ) -> None:
        if self._charge_plan_setting_dialog is None:
            self._charge_plan_setting_dialog = ChargePlanSettingDialog(ctx=self.ctx, parent=parent)

        self._charge_plan_setting_dialog.show_by_group(
            group_id=group_id,
            parent=parent,
        )

    def show_notorious_hunt_setting_dialog(
        self,
        parent: QWidget,
        group_id: str,
    ) -> None:
        if self._notorious_hunt_setting_dialog is None:
            self._notorious_hunt_setting_dialog = NotoriousHuntSettingDialog(ctx=self.ctx, parent=parent)

        self._notorious_hunt_setting_dialog.show_by_group(
            group_id=group_id,
            parent=parent,
        )

    def show_coffee_setting_dialog(
        self,
        parent: QWidget,
        group_id: str,
    ) -> None:
        if self._coffee_setting_dialog is None:
            self._coffee_setting_dialog = CoffeeSettingDialog(ctx=self.ctx, parent=parent)

        self._coffee_setting_dialog.show_by_group(
            group_id=group_id,
            parent=parent,
        )

    def show_random_play_setting_dialog(
        self,
        parent: QWidget,
        group_id: str,
    ) -> None:
        if self._random_play_setting_dialog is None:
            self._random_play_setting_dialog = RandomPlaySettingDialog(ctx=self.ctx, parent=parent)

        self._random_play_setting_dialog.show_by_group(
            group_id=group_id,
            parent=parent,
        )

    def show_drive_disc_dismantle_setting_dialog(
        self,
        parent: QWidget,
        group_id: str,
    ) -> None:
        if self._drive_disc_dismantle_setting_dialog is None:
            self._drive_disc_dismantle_setting_dialog = DriveDiscDismantleSettingDialog(ctx=self.ctx, parent=parent)

        self._drive_disc_dismantle_setting_dialog.show_by_group(
            group_id=group_id,
            parent=parent,
        )

    def show_withered_domain_setting_dialog(
        self,
        parent: QWidget,
        group_id: str,
    ) -> None:
        if self._withered_domain_setting_dialog is None:
            self._withered_domain_setting_dialog = WitheredDomainSettingDialog(ctx=self.ctx, parent=parent)

        self._withered_domain_setting_dialog.show_by_group(
            group_id=group_id,
            parent=parent,
        )

    def show_lost_void_setting_dialog(
        self,
        parent: QWidget,
        group_id: str,
    ) -> None:
        if self._lost_void_setting_dialog is None:
            self._lost_void_setting_dialog = LostVoidSettingDialog(ctx=self.ctx, parent=parent)

        self._lost_void_setting_dialog.show_by_group(
            group_id=group_id,
            parent=parent,
        )

    def show_redemption_code_setting_dialog(
        self,
        parent: QWidget,
        group_id: str,
    ) -> None:
        if self._redemption_code_setting_dialog is None:
            self._redemption_code_setting_dialog = RedemptionCodeSettingDialog(ctx=self.ctx, parent=parent)

        self._redemption_code_setting_dialog.show_by_group(
            group_id=group_id,
            parent=parent,
        )

    def show_intel_board_setting_flyout(
        self,
        target: QWidget,
        parent: QWidget,
        group_id: str,
    ):
        IntelBoardSettingFlyout.show_flyout(
            ctx=self.ctx,
            group_id=group_id,
            target=target,
            parent=parent,
        )
