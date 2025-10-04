from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.devtools.screenshot_helper import screenshot_helper_const
from zzz_od.application.devtools.screenshot_helper.screenshot_helper_app import (
    ScreenshotHelperApp,
)
from zzz_od.application.devtools.screenshot_helper.screenshot_helper_config import ScreenshotHelperConfig

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class ScreenshotHelperAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=screenshot_helper_const.APP_ID,
            app_name=screenshot_helper_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return ScreenshotHelperApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        return ScreenshotHelperConfig(
            instance_idx=instance_idx,
            group_id=group_id,
        )

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        return None