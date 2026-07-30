from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.devtools.shiyu_defense_team_test import (
    shiyu_defense_team_test_const,
)
from zzz_od.application.devtools.shiyu_defense_team_test.shiyu_defense_team_test_config import (
    ShiyuDefenseTeamTestConfig,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam


class ShiyuDefenseTeamTestApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=shiyu_defense_team_test_const.APP_ID,
            op_name=shiyu_defense_team_test_const.APP_NAME,
            need_check_game_win=False,
        )
        self.config: ShiyuDefenseTeamTestConfig = self.ctx.run_context.get_config(
            app_id=shiyu_defense_team_test_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

    @operation_node(name='扫描并选择预备编队', is_start_node=True)
    def choose_team(self) -> OperationRoundResult:
        op = ChoosePredefinedTeam(
            self.ctx,
            shiyu_target_list=self.config.get_target_list(),
            start_at_team_list=True,
            finish_without_confirm=False,
        )
        return self.round_by_op_result(op.execute())
