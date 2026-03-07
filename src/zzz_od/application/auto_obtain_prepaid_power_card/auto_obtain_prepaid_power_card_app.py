from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.auto_obtain_prepaid_power_card import auto_obtain_prepaid_power_card_const
from zzz_od.application.auto_obtain_prepaid_power_card.auto_obtain_prepaid_power_card_config import \
    AutoObtainPrepaidPowerCardConfig
from zzz_od.application.auto_obtain_prepaid_power_card.operations import (
    OutpostLogisticsOperation,
    MonthlyRestockOperation,
    FadingSignalOperation
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class AutoObtainPrepaidPowerCardApp(ZApplication):

    # 商店名称常量
    OUTPOST_LOGISTICS = "后勤商店"
    MONTHLY_RESTOCK = "情报板商店"
    FADING_SIGNAL = "信号残响"

    def __init__(self, ctx: ZContext) -> None:
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=auto_obtain_prepaid_power_card_const.APP_ID,
            op_name=auto_obtain_prepaid_power_card_const.APP_NAME,
        )

        self.config: AutoObtainPrepaidPowerCardConfig = self.ctx.run_context.get_config(
            app_id=auto_obtain_prepaid_power_card_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        # 任务队列
        self._task_queue: list[str] = []
        self._current_task_index: int = 0

    @operation_node(name='检查配置', is_start_node=True)
    def check_config(self) -> OperationRoundResult:
        """检查配置，构建任务队列"""
        self._task_queue = []

        if self.config.outpost_logistics:
            self._task_queue.append(self.OUTPOST_LOGISTICS)
        if self.config.monthly_restock:
            self._task_queue.append(self.MONTHLY_RESTOCK)
        if self.config.fading_signal:
            self._task_queue.append(self.FADING_SIGNAL)

        if not self._task_queue:
            return self.round_success(status='无需获取')

        self._current_task_index = 0

        return self._get_next_task_status()

    def _get_next_task_status(self) -> OperationRoundResult:
        """获取下一个任务的状态"""
        if self._current_task_index >= len(self._task_queue):
            return self.round_success(status='全部完成')

        current_task = self._task_queue[self._current_task_index]

        return self.round_success(status=current_task)

    # ==================== 后勤商店节点 ====================

    @node_from(from_name='检查配置', status='后勤商店')
    @operation_node(name='后勤商店')
    def outpost_logistics(self) -> OperationRoundResult:
        """执行后勤商店操作"""
        op = OutpostLogisticsOperation(self.ctx, self.config)
        result = self.round_by_op_result(op.execute())

        if result.is_success:
            self._current_task_index += 1
            return self._get_next_task_status()
        return result

    # ==================== 情报板商店节点 ====================

    @node_from(from_name='检查配置', status='情报板商店')
    @node_from(from_name='后勤商店', status='情报板商店')
    @operation_node(name='情报板商店')
    def monthly_restock(self) -> OperationRoundResult:
        """执行情报板商店操作"""
        op = MonthlyRestockOperation(self.ctx, self.config)
        result = self.round_by_op_result(op.execute())

        if result.is_success:
            self._current_task_index += 1
            return self._get_next_task_status()
        return result

    # ==================== 信号残响节点 ====================

    @node_from(from_name='检查配置', status='信号残响')
    @node_from(from_name='情报板商店', status='信号残响')
    @operation_node(name='信号残响')
    def fading_signal(self) -> OperationRoundResult:
        """执行信号残响操作"""
        op = FadingSignalOperation(self.ctx, self.config)
        result = self.round_by_op_result(op.execute())

        if result.is_success:
            self._current_task_index += 1
            return self._get_next_task_status()
        return result

    # ==================== 完成节点 ====================

    @node_from(from_name='后勤商店', status='全部完成')
    @node_from(from_name='情报板商店', status='全部完成')
    @node_from(from_name='信号残响', status='全部完成')
    @node_from(from_name='检查配置', status='无需获取')
    @operation_node(name='最终返回')
    def final_return(self) -> OperationRoundResult:
        """最终返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())