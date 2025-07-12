from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.compendium import CompendiumTab
from zzz_od.operation.compendium.compendium_choose_category import CompendiumChooseCategory
from zzz_od.operation.compendium.compendium_choose_mission_type import CompendiumChooseMissionType
from zzz_od.operation.compendium.compendium_choose_tab import CompendiumChooseTab
from zzz_od.operation.compendium.open_compendium import OpenCompendium
from zzz_od.operation.zzz_operation import ZOperation


class TransportByCompendium(ZOperation):

    def __init__(self, ctx: ZContext, tab_name: str, category_name: str, mission_type_name: str):
        """
        使用快捷手册传送 最后不会等待加载完毕
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name='%s %s %s-%s-%s' % (
                gt('传送'),
                gt('快捷手册', 'game'),
                gt(tab_name, 'game'), gt(category_name, 'game'), gt(mission_type_name, 'game')
            )
        )

        self.tab_name: str = tab_name
        self.category_name: str = category_name
        self.mission_type_name: str = mission_type_name

        if self.mission_type_name == '自定义模板':  # 没法直接传送到自定义
            self.mission_type_name: str = '基础材料'

    @operation_node(name='识别初始画面', is_start_node=True)
    def check_first_screen(self) -> OperationRoundResult:
        screen = self.screenshot()
        possible_screen_names = [
            '快捷手册-目标',
            '快捷手册-日常',
            '快捷手册-训练',
            '快捷手册-作战',
            '快捷手册-战术'
        ]
        screen_name = self.check_and_update_current_screen(screen, possible_screen_names)
        if screen_name is None:
            return self.round_success()
        else:
            return self.round_success('快捷手册')

    @node_from(from_name='识别初始画面')
    @operation_node(name='快捷手册')
    def open_compendium(self) -> OperationRoundResult:
        op = OpenCompendium(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别初始画面', status='快捷手册')
    @node_from(from_name='快捷手册')
    @operation_node(name='选择TAB')
    def choose_tab(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name=f'快捷手册-{self.tab_name}')

    @node_from(from_name='选择TAB')
    @operation_node(name='选择分类')
    def choose_category(self) -> OperationRoundResult:
        op = CompendiumChooseCategory(self.ctx, self.category_name)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='选择分类')
    @operation_node(name='选择副本分类')
    def choose_mission_type(self) -> OperationRoundResult:
        mission_type = self.ctx.compendium_service.get_mission_type_data(
            self.tab_name, self.category_name, self.mission_type_name
        )
        op = CompendiumChooseMissionType(self.ctx, mission_type)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.start_running()
    op = TransportByCompendium(ctx, '训练', '定期清剿', '疯子与追随者')
    op.execute()


if __name__ == '__main__':
    __debug()
