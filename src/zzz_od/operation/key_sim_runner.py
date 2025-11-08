from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class KeySimRunner(ZOperation):

    def __init__(self, ctx: ZContext, config_name: str):
        ZOperation.__init__(self, ctx,
                            op_name='%s %s' % (
                                gt('模拟按键'),
                                config_name
                            ))
        self.config_name: str = config_name
        self.ops: list[AtomicOp] = []

    @operation_node(name='加载配置', is_start_node=True)
    def load_config(self) -> OperationRoundResult:
        config = YamlConfig(self.config_name, sub_dir=['key_sim'], sample=True, copy_from_sample=False)
        op_def_list = [
            OperationDef(i)
            for i in config.data.get('operations', [])
        ]
        self.ops = [
            self.ctx.auto_battle_context.atomic_op_factory.get_atomic_op(i)
            for i in op_def_list
        ]

        return self.round_success()

    @node_from(from_name='加载配置')
    @operation_node(name='执行按键')
    def run_key_sim(self) -> OperationRoundResult:
        for op in self.ops:
            op.execute()

        return self.round_success()
