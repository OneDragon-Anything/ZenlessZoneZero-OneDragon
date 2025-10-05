from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.hollow_zero.withered_domain import withered_domain_const
from zzz_od.application.hollow_zero.withered_domain.withered_domain_app import WitheredDomainApp
from zzz_od.application.hollow_zero.withered_domain.withered_domain_config import (
    WitheredDomainConfig,
)
from zzz_od.application.hollow_zero.withered_domain.withered_domain_run_record import (
    WitheredDomainRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class WitheredDomainAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=withered_domain_const.APP_ID,
            app_name=withered_domain_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return WitheredDomainApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        return WitheredDomainConfig(
            instance_idx=instance_idx,
            group_id=group_id,
        )

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        return WitheredDomainRunRecord(
            config=self.get_config(
                instance_idx=instance_idx,
                group_id=application_const.DEFAULT_GROUP_ID,
            ),
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )