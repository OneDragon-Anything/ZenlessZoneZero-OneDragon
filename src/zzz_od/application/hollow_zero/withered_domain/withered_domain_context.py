from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application import application_const
from zzz_od.application.hollow_zero.withered_domain import withered_domain_const
from zzz_od.application.hollow_zero.withered_domain.withered_domain_config import WitheredDomainConfig
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class WitheredDomainContext:

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx

        self.challenge_config: Optional[HollowZeroChallengeConfig] = None

    def init_before_run(self) -> None:
        """
        应用开始前的初始化
        """
        config: Optional[WitheredDomainConfig] = self.ctx.run_context.get_config(
            app_id=withered_domain_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        if config is None or config.challenge_config is None:
            self.hollow_zero_challenge_config = HollowZeroChallengeConfig('', is_mock=True)
        else:
            self.hollow_zero_challenge_config = HollowZeroChallengeConfig(config.challenge_config)