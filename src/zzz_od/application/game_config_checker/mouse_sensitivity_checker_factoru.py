from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.game_config_checker import mouse_sensitivity_checker_const
from zzz_od.application.game_config_checker.mouse_sensitivity_checker import (
    MouseSensitivityChecker,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class MouseSensitivityCheckerFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(
            self,
            app_id=mouse_sensitivity_checker_const.APP_ID,
            app_name=mouse_sensitivity_checker_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return MouseSensitivityChecker(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        return None

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        return None