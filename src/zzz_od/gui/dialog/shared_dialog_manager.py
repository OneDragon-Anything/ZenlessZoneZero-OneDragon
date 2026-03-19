from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class SharedDialogManager:

    def __init__(self, ctx: ZContext) -> None:
        self.ctx: ZContext = ctx

    @cached_property
    def _charge_plan_dialog(self):
        from zzz_od.gui.dialog.charge_plan_setting_dialog import ChargePlanSettingDialog
        return ChargePlanSettingDialog(ctx=self.ctx)

    def show_charge_plan_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._charge_plan_dialog.show_by_group(group_id=group_id, parent=parent)

    @cached_property
    def _coffee_dialog(self):
        from zzz_od.gui.dialog.coffee_setting_dialog import CoffeeSettingDialog
        return CoffeeSettingDialog(ctx=self.ctx)

    def show_coffee_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._coffee_dialog.show_by_group(group_id=group_id, parent=parent)

    @cached_property
    def _drive_disc_dismantle_dialog(self):
        from zzz_od.gui.dialog.drive_disc_dismantle_setting_dialog import (
            DriveDiscDismantleSettingDialog,
        )
        return DriveDiscDismantleSettingDialog(ctx=self.ctx)

    def show_drive_disc_dismantle_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._drive_disc_dismantle_dialog.show_by_group(group_id=group_id, parent=parent)

    def show_intel_board_setting_flyout(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        from zzz_od.gui.dialog.intel_board_setting_dialog import IntelBoardSettingFlyout
        IntelBoardSettingFlyout.show_flyout(
            ctx=self.ctx, group_id=group_id, target=target, parent=parent,
        )

    @cached_property
    def _life_on_line_dialog(self):
        from zzz_od.gui.dialog.life_on_line_setting_dialog import (
            LifeOnLineSettingDialog,
        )
        return LifeOnLineSettingDialog(ctx=self.ctx)

    def show_life_on_line_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._life_on_line_dialog.show_by_group(group_id=group_id, parent=parent)

    @cached_property
    def _lost_void_dialog(self):
        from zzz_od.gui.dialog.lost_void_setting_dialog import LostVoidSettingDialog
        return LostVoidSettingDialog(ctx=self.ctx)

    def show_lost_void_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._lost_void_dialog.show_by_group(group_id=group_id, parent=parent)

    @cached_property
    def _notorious_hunt_dialog(self):
        from zzz_od.gui.dialog.notorious_hunt_setting_dialog import (
            NotoriousHuntSettingDialog,
        )
        return NotoriousHuntSettingDialog(ctx=self.ctx)

    def show_notorious_hunt_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._notorious_hunt_dialog.show_by_group(group_id=group_id, parent=parent)

    @cached_property
    def _random_play_dialog(self):
        from zzz_od.gui.dialog.random_play_setting_dialog import RandomPlaySettingDialog
        return RandomPlaySettingDialog(ctx=self.ctx)

    def show_random_play_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._random_play_dialog.show_by_group(group_id=group_id, parent=parent)

    @cached_property
    def _redemption_code_dialog(self):
        from zzz_od.gui.dialog.redemption_code_setting_dialog import (
            RedemptionCodeSettingDialog,
        )
        return RedemptionCodeSettingDialog(ctx=self.ctx)

    def show_redemption_code_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._redemption_code_dialog.show_by_group(group_id=group_id, parent=parent)

    @cached_property
    def _shiyu_defense_dialog(self):
        from zzz_od.gui.dialog.shiyu_defense_setting_dialog import (
            ShiyuDefenseSettingDialog,
        )
        return ShiyuDefenseSettingDialog(ctx=self.ctx)

    def show_shiyu_defense_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._shiyu_defense_dialog.show_by_group(group_id=group_id, parent=parent)

    @cached_property
    def _suibian_temple_dialog(self):
        from zzz_od.gui.dialog.suibian_temple_setting_dialog import (
            SuibianTempleSettingDialog,
        )
        return SuibianTempleSettingDialog(ctx=self.ctx)

    def show_suibian_temple_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._suibian_temple_dialog.show_by_group(group_id=group_id, parent=parent)

    @cached_property
    def _withered_domain_dialog(self):
        from zzz_od.gui.dialog.withered_domain_setting_dialog import (
            WitheredDomainSettingDialog,
        )
        return WitheredDomainSettingDialog(ctx=self.ctx)

    def show_withered_domain_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._withered_domain_dialog.show_by_group(group_id=group_id, parent=parent)

    @cached_property
    def _world_patrol_dialog(self):
        from zzz_od.gui.dialog.world_patrol_setting_dialog import (
            WorldPatrolSettingDialog,
        )
        return WorldPatrolSettingDialog(ctx=self.ctx)

    def show_world_patrol_setting_dialog(
        self, parent: QWidget, group_id: str, target: QWidget,
    ) -> None:
        self._world_patrol_dialog.show_by_group(group_id=group_id, parent=parent)
