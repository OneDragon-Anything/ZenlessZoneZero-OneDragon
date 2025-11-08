from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext


def build_all_merge():
    """
    构建所有合并后的文件
    """
    ctx = ZContext()
    config_list = get_auto_battle_op_config_list('auto_battle')
    for config_name in config_list:
        op = AutoBattleOperator(
            ctx=ctx.auto_battle_context,
            sub_dir='auto_battle',
            template_name=config_name.value,
            read_from_merged=False,
        )
        op.load()
        op.save_as_one_file()


if __name__ == '__main__':
    build_all_merge()
