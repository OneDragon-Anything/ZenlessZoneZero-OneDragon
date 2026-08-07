from pathlib import Path

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


def find_key_sim_yml(work_dir: Path, plugin_dirs: list[Path], config_name: str) -> Path | None:
    """定位键鼠脚本 yml 的读取路径。

    优先级：用户 config/key_sim/<name>.yml > 插件目录 key_sim/<name>.yml。
    两者都没有时返回 None，由调用方回退读取仓库自带的 sample 文件。

    Args:
        work_dir: 项目工作目录（config 目录的父目录）
        plugin_dirs: 插件目录列表（内置 application 子目录 / plugins 下的第三方插件目录）
        config_name: 脚本名

    Returns:
        命中的 yml 路径；未命中返回 None
    """
    user_yml = work_dir / 'config' / 'key_sim' / f'{config_name}.yml'
    if user_yml.is_file():
        return user_yml
    for plugin_dir in plugin_dirs:
        plugin_yml = plugin_dir / 'key_sim' / f'{config_name}.yml'
        if plugin_yml.is_file():
            return plugin_yml
    return None


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

    def _load_key_sim_config(self) -> YamlOperator:
        """加载键鼠脚本配置：用户 config 优先，其次插件目录，最后回退仓库 sample。"""
        plugin_dirs = [
            plugin_info.plugin_dir
            for plugin_info in self.ctx.factory_manager.plugin_infos
            if plugin_info.plugin_dir is not None
        ]
        yml_path = find_key_sim_yml(
            Path(os_utils.get_work_dir()), plugin_dirs, self.config_name
        )
        if yml_path is not None:
            return YamlOperator(str(yml_path))
        # 用户与插件都没有该脚本时，回退读取仓库自带的 sample 文件
        return YamlConfig(self.config_name, sub_dir=['key_sim'], sample=True,
                          copy_from_sample=False)

    @node_from(from_name='加载配置')
    @operation_node(name='执行按键')
    def run_key_sim(self) -> OperationRoundResult:
        for op in self.ops:
            op.execute()

        return self.round_success()
