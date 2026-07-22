from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.hou_hou_bakery import hou_hou_bakery_const
from zzz_od.application.hou_hou_bakery.hou_hou_bakery_app import HouHouBakeryApp
from zzz_od.application.hou_hou_bakery.hou_hou_bakery_run_record import (
    HouHouBakeryRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class HouHouBakeryFactory(ApplicationFactory):
    """吼吼饼铺应用工厂: 负责创建应用实例与运行记录。"""

    def __init__(self, ctx: ZContext):
        """初始化工厂。

        Args:
            ctx: 运行上下文。
        """
        ApplicationFactory.__init__(self, hou_hou_bakery_const)
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        """创建吼吼饼铺应用实例。

        Args:
            instance_idx: 实例下标。
            group_id: 所属分组ID。

        Returns:
            Application: 吼吼饼铺应用实例。
        """
        return HouHouBakeryApp(self.ctx)

    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        """创建吼吼饼铺运行记录。

        Args:
            instance_idx: 实例下标。

        Returns:
            AppRunRecord: 吼吼饼铺运行记录。
        """
        return HouHouBakeryRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
