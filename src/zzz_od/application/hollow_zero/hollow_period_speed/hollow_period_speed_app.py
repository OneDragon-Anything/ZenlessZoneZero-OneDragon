from typing import ClassVar, cast

from zzz_od.application.hollow_zero.hollow_period_speed import hollow_period_speed_const
from zzz_od.application.hollow_zero.hollow_period_speed.hollow_period_speed_config import (
    HollowPeriodSpeedConfig,
)
from zzz_od.application.hollow_zero.withered_domain.withered_domain_app import (
    WitheredDomainApp,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.hollow_quick_runner import HollowQuickRunner
from zzz_od.hollow_zero.hollow_runner import HollowRunner
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig


class HollowPeriodSpeedApp(WitheredDomainApp):

    """空洞周期速刷:固定进入枯萎之都-施工废墟-内部,速刷零号业绩或周期奖励。入口流程与枯萎之都一致。"""

    SPEED_RUN: ClassVar[bool] = True

    def __init__(self, ctx: ZContext):
        WitheredDomainApp.__init__(
            self,
            ctx=ctx,
            app_id=hollow_period_speed_const.APP_ID,
            op_name=hollow_period_speed_const.APP_NAME,
        )

    def _get_challenge_config(self) -> HollowZeroChallengeConfig | None:
        return cast(HollowPeriodSpeedConfig, self.config).build_challenge_config()

    def _create_runner(self) -> HollowRunner:
        return HollowQuickRunner(self.ctx)
