import time

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.operation.transport import Transport
from zzz_od.operation.wait_normal_world import WaitNormalWorld
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class HifiMasterSynthesisOp(ZOperation):
    """母盘合成操作 - 单一职责：处理母盘合成的所有UI交互"""

    def __init__(self, ctx):
        ZOperation.__init__(self, ctx, op_name='母盘合成')

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        """前往音像店"""
        op = Transport(self.ctx, '六分街', '音像店', wait_at_last=False)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='等待加载', node_max_retry_times=60)
    def wait_loading(self) -> OperationRoundResult:
        """等待加载"""
        result = self.round_by_find_area(self.last_screenshot, '音像店', '合成')
        if result.is_success:
            return self.round_success(result.status)

        op = WaitNormalWorld(self.ctx, check_once=True)
        result = self.round_by_op_result(op.execute())
        if result.is_success:
            return self.round_success(result.status)

        return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='等待加载')
    @operation_node(name='移动交互')
    def move_interact(self) -> OperationRoundResult:
        """移动交互"""
        self.ctx.controller.move_w(press=True, press_time=1, release=True)
        time.sleep(1)
        self.ctx.controller.interact(press=True, press_time=0.2, release=True)
        return self.round_success()

    @node_from(from_name='等待加载', status='合成')
    @node_from(from_name='移动交互')
    @operation_node(name='打开合成')
    def open_synthesis(self) -> OperationRoundResult:
        """打开合成界面"""
        result = self.round_by_find_and_click_area(self.last_screenshot, '音像店', '合成')
        if result.is_success:
            return self.round_success(result.status, wait=1)
        return self.round_retry(wait=1)

    @node_from(from_name='打开合成')
    @operation_node(name='识别界面')
    def check_ui(self) -> OperationRoundResult:
        """识别界面"""
        result = self.round_by_find_area(self.last_screenshot, '音像店', '母盘合成')
        if result.is_success:
            return self.round_success(status='可合成')

        result = self.round_by_find_area(self.last_screenshot, '音像店', '文本-合成素材不足')
        if result.is_success:
            return self.round_success(status='素材不足')

        return self.round_retry(wait=1)

    @node_from(from_name='识别界面', status='可合成')
    @operation_node(name='执行合成')
    def perform_synthesis(self) -> OperationRoundResult:
        """执行合成"""
        result = self.round_by_find_and_click_area(self.last_screenshot, '音像店', '母盘合成')
        if result.is_success:
            return self.round_success(result.status, wait=1)
        return self.round_retry(wait=1)

    @node_from(from_name='执行合成')
    @operation_node(name='确认合成')
    def confirm(self) -> OperationRoundResult:
        """确认合成"""
        result = self.round_by_find_and_click_area(self.last_screenshot, '音像店', '确认')
        if result.is_success:
            return self.round_success(result.status, wait=1)
        return self.round_retry(wait=1)

    @node_from(from_name='确认合成')
    @node_from(from_name='识别界面', status='素材不足')
    @operation_node(name='返回大世界')
    def return_to_world(self) -> OperationRoundResult:
        """返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())