from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.trigrams_collection import trigrams_collection_const
from zzz_od.application.trigrams_collection.trigrams_collection_app import (
    TrigramsCollectionApp,
)
from zzz_od.application.trigrams_collection.trigrams_collection_record import (
    TrigramsCollectionRunRecord,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class TrigramsCollectionFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=trigrams_collection_const.APP_ID,
            app_name=trigrams_collection_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return TrigramsCollectionApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        # This app has no config, return None
        return None

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        return TrigramsCollectionRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )