from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from zzz_od.application.devtools.shiyu_defense_team_test import (
    shiyu_defense_team_test_const,
)
from zzz_od.application.devtools.shiyu_defense_team_test.shiyu_defense_team_test_app import (
    ShiyuDefenseTeamTestApp,
)
from zzz_od.application.devtools.shiyu_defense_team_test.shiyu_defense_team_test_config import (
    ShiyuDefenseTeamTestConfig,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class ShiyuDefenseTeamTestAppFactory(ApplicationFactory):

    def __init__(self, ctx: ZContext):
        ApplicationFactory.__init__(self, shiyu_defense_team_test_const)
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return ShiyuDefenseTeamTestApp(self.ctx)

    def create_config(
        self,
        instance_idx: int,
        group_id: str,
    ) -> ApplicationConfig:
        return ShiyuDefenseTeamTestConfig(
            instance_idx=instance_idx,
            group_id=group_id,
        )
