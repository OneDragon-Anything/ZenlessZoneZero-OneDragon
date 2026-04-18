from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from zzz_od.application.devtools.intel_manage import intel_manage_const
from zzz_od.application.devtools.intel_manage.intel_manage_app import IntelManageApp
from zzz_od.application.devtools.intel_manage.intel_manage_config import IntelManageConfig

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class IntelManageAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=intel_manage_const.APP_ID,
            app_name=intel_manage_const.APP_NAME,
            default_group=intel_manage_const.DEFAULT_GROUP,
            need_notify=intel_manage_const.NEED_NOTIFY,
        )
        self.ctx: ZContext = ctx

    def create_application(self, _instance_idx: int, _group_id: str) -> Application:
        """创建应用实例（instance_idx和group_id参数为接口要求，当前应用不需要）"""
        return IntelManageApp(self.ctx)

    def create_config(self, instance_idx: int, group_id: str) -> IntelManageConfig:
        return IntelManageConfig(instance_idx, group_id)
