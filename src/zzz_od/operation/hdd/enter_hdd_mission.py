from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam
from zzz_od.operation.zzz_operation import ZOperation


class EnterHddMission(ZOperation):

    def __init__(self, ctx: ZContext,
                 chapter: str,
                 mission_type: str,
                 mission_name: str,
                 predefined_team_idx: int = -1):
        """
        需要刚进来HDD画面时使用
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name=gt('进入 HDD 副本'))

        self.chapter: str = chapter
        self.mission_type: str = mission_type
        self.mission_name: str = mission_name
        self.predefined_team_idx = predefined_team_idx  # 预备编队下标 -1代表不选择

    def handle_init(self):
        pass

    @operation_node(name='选择章节', is_start_node=True)
    def choose_chapter(self) -> OperationRoundResult:
        screen = self.screenshot()

        area = self.ctx.screen_loader.get_area('HDD', '章节列表')
        result = self.round_by_ocr_and_click(screen, self.chapter, area=area)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        area = self.ctx.screen_loader.get_area('HDD', '章节显示')
        result = self.round_by_ocr(screen, self.chapter, area=area)
        if result.is_success:
            return self.round_success(status=result.status)

        # 完成一次退出后 可能在副本列表画面
        result = self.round_by_find_area(screen, 'HDD', '下一步')
        if result.is_success:
            return self.round_success(status=result.status)

        # 不符合时 点击弹出选项
        result = self.round_by_click_area('HDD', '章节显示')
        return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='选择章节')
    @operation_node(name='选择委托')
    def choose_mission_type(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('HDD', '委托区域')
        result = self.round_by_ocr_and_click(screen, self.mission_type, area=area)
        if result.is_success:
            return self.round_wait(status=result.status, wait=2)

        # 点击直到看到下一步
        result = self.round_by_find_area(screen, 'HDD', '下一步')
        if result.is_success:  # 稍微等待
            return self.round_success(wait=1)

        return self.round_retry(wait=1)

    @node_from(from_name='选择章节', status='下一步')
    @node_from(from_name='选择委托')
    @operation_node(name='选择副本', node_max_retry_times=10)  # 有些副本比较多 多允许滑动几次找找
    def choose_mission(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('HDD', '副本区域')
        result = self.round_by_ocr_and_click(screen, self.mission_name, area=area)
        if result.is_success:
            return self.round_success(wait=1)

        # 找不到时候 往下滑
        drag_from = area.center
        drag_to = drag_from + Point(0, -200)
        self.ctx.controller.drag_to(start=drag_from, end=drag_to)

        return self.round_retry(wait=1)

    @node_from(from_name='选择副本')
    @operation_node(name='下一步')
    def click_next(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, 'HDD', '下一步',
                                                 success_wait=2, retry_wait=1)

    @node_from(from_name='下一步')
    @operation_node(name='选择预备编队')
    def choose_predefined_team(self) -> OperationRoundResult:
        if self.predefined_team_idx == -1:
            return self.round_success('无需选择预备编队')
        else:
            op = ChoosePredefinedTeam(self.ctx, [self.predefined_team_idx])
            return self.round_by_op_result(op.execute())

    @node_from(from_name='选择预备编队')
    @operation_node(name='出战')
    def click_deploy(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, 'HDD', '出战',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='出战')
    @operation_node(name='识别低等级')
    def check_level(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, 'HDD', '确定并出战',
                                                 retry_wait=1)

    @node_from(from_name='识别低等级')
    @node_from(from_name='识别低等级', success=False)
    @operation_node(name='进入成功')
    def finish(self) -> OperationRoundResult:
        return self.round_success()
