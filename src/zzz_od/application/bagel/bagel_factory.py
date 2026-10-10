from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from zzz_od.application.bagel import bagel_const
from zzz_od.application.bagel.bagel_app import BagelApp
from zzz_od.application.bagel.bagel_config import BagelConfig
from zzz_od.application.bagel.bagel_run_record import BagelRunRecord

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class BagelFactory(ApplicationFactory):
    """由现有插件发现机制注册，加入默认一条龙。"""

    def __init__(self, ctx: ZContext) -> None:
        """保存上下文，实例配置由工厂缓存管理。"""
        super().__init__(bagel_const)
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> BagelApp:
        """使用调用者指定的账号和应用组。"""
        return BagelApp(
            self.ctx,
            self.get_config(instance_idx, group_id),
            self.get_run_record(instance_idx),
        )

    def create_config(self, instance_idx: int, group_id: str) -> BagelConfig:
        """创建独立应用配置。"""
        return BagelConfig(instance_idx, group_id)

    def create_run_record(self, instance_idx: int) -> BagelRunRecord:
        """创建账号级运行记录；旧物资进度不作为入场条件。"""
        return BagelRunRecord(
            instance_idx,
            self.ctx.game_account_config.game_refresh_hour_offset,
        )
