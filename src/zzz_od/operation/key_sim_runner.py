from pathlib import Path

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.key_sim_yaml_config import KeySimYamlConfig
from zzz_od.operation.zzz_operation import ZOperation


class KeySimRunner(ZOperation):

    def __init__(self, ctx: ZContext, config_name: str):
        ZOperation.__init__(self, ctx,
                            op_name=f'{gt("模拟按键")} {config_name}')
        self.config_name: str = config_name
        self.ops: list[AtomicOp] = []

    @operation_node(name='加载配置', is_start_node=True)
    def load_config(self) -> OperationRoundResult:
        config = self._load_key_sim_config()
        op_def_list = [
            OperationDef(i)
            for i in config.data.get('operations', [])
        ]
        self.ops = [
            self.ctx.auto_battle_context.atomic_op_factory.get_atomic_op(i)
            for i in op_def_list
        ]

        return self.round_success()

    def _load_key_sim_config(self) -> KeySimYamlConfig:
        """加载键鼠脚本配置：用户 config 优先，其次当前应用插件注册的脚本目录，最后回退仓库 sample。"""
        key_sim_dir: Path | None = None
        app_id = self.ctx.run_context.current_app_id
        if app_id is not None:
            plugin_info = self.ctx.factory_manager.get_plugin_info(app_id)
            if (
                plugin_info is not None
                and plugin_info.key_sim_dir != ''
                and plugin_info.plugin_dir is not None
            ):
                key_sim_dir = plugin_info.plugin_dir / plugin_info.key_sim_dir
        return KeySimYamlConfig(self.config_name, plugin_dir=key_sim_dir)

    @node_from(from_name='加载配置')
    @operation_node(name='执行按键')
    def run_key_sim(self) -> OperationRoundResult:
        for op in self.ops:
            op.execute()

        return self.round_success()
