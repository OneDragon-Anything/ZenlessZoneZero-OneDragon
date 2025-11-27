from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.transport import Transport
from zzz_od.operation.compendium.compendium_choose_category import CompendiumChooseCategory
from zzz_od.operation.compendium.compendium_choose_mission_type import CompendiumChooseMissionType
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

    @operation_node(name='返回大世界', is_start_node=True)
    def back_to_world(self) -> OperationRoundResult:
        # 先回到大世界
        op = BackToNormalWorld(self.ctx)
        result = op.execute()
        if result.success and result.status == '大世界-勘域':
            # 仅在需要使用快捷手册的场景下，并且返回后不处于大世界-普通时，
            # 先传送到不成文规定的统一起点，避免传送确认弹窗差异
            tp = Transport(self.ctx, '录像店', '房间')  # 不成文规定：先前的鼠标校准功能选择的传送点
            return self.round_by_op_result(tp.execute())
        return self.round_by_op_result(result)

    @node_from(from_name='返回大世界')
    @operation_node(name='快捷手册')
    def choose_tab(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name=f'快捷手册-{self.tab_name}')

    @node_from(from_name='快捷手册')
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
    ctx.run_context.start_running()
    op = TransportByCompendium(ctx, '训练', '区域巡防', '疯子与追随者')
    op.execute()


if __name__ == '__main__':
    __debug()
