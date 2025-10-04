from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.email_app.email_app import EmailApp
from zzz_od.application.email_app.email_run_record import EmailRunRecord

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class EmailAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id="email",
            app_name="邮件",
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return EmailApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        return None

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        return EmailRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
