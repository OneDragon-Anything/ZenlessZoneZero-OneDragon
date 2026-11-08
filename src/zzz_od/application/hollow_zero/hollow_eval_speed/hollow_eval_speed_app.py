from typing import ClassVar, cast

from zzz_od.application.hollow_zero.hollow_eval_speed import hollow_eval_speed_const
from zzz_od.application.hollow_zero.hollow_eval_speed.hollow_eval_speed_config import (
    HollowEvalSpeedConfig,
)
from zzz_od.application.hollow_zero.withered_domain.withered_domain_app import (
    WitheredDomainApp,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.hollow_quick_runner import HollowQuickRunner
from zzz_od.hollow_zero.hollow_runner import HollowRunner
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig


class HollowEvalSpeedApp(WitheredDomainApp):

    """零号业绩速刷:固定进入枯萎之都-施工废墟-内部,只速刷零号业绩。注意:这样刷业绩会亏掉周期奖励的丁尼。"""

    SPEED_RUN: ClassVar[bool] = True

    def __init__(self, ctx: ZContext):
        WitheredDomainApp.__init__(
            self,
            ctx=ctx,
            app_id=hollow_eval_speed_const.APP_ID,
            op_name=hollow_eval_speed_const.APP_NAME,
        )

    def _get_challenge_config(self) -> HollowZeroChallengeConfig | None:
        return cast(HollowEvalSpeedConfig, self.config).build_challenge_config()

    def _create_runner(self) -> HollowRunner:
        return HollowQuickRunner(self.ctx)
