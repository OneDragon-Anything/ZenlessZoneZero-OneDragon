import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import Future

from one_dragon.base.conditional_operation.conditional_operator import ConditionalOperator
from one_dragon.base.conditional_operation.state_recorder import StateRecord, StateRecorder
from one_dragon.base.conditional_operation.operation_task import OperationTask
from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext


class TestAutoBattle:

    @pytest.fixture
    def ctx(self):
        ctx = ZContext()
        yield ctx
        ctx.after_app_shutdown()

    def test_all_valid(self, ctx: ZContext) -> None:
        """
        确保所有自动战斗配置文件无异常
        """
        config_list = get_auto_battle_op_config_list('auto_battle')
        for config in config_list:
            op = AutoBattleOperator(ctx, 'auto_battle', config.value)
            success, msg = op._init_operator()
            assert success, msg