from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanConfig
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.restore_charge import RestoreCharge
from zzz_od.operation.zzz_operation import ZOperation


class ChooseNextOrFinishAfterBattle(ZOperation):

    def __init__(self, ctx: ZContext, try_next: bool):
        """
        在战斗结束画面 尝试点击 【再来一次】 或者 【结束】
        :param ctx: 上下文
        :param try_next: 是否尝试点击下一次
        """
        ZOperation.__init__(self, ctx, op_name=gt('战斗后选择'))
        self.try_next: bool = try_next

    @node_from(from_name='恢复电量', status='战斗结果-完成')
    @operation_node(name='判断再来一次', is_start_node=True)
    def check_next(self) -> OperationRoundResult:
        if self.try_next:
            result = self.round_by_find_and_click_area(self.last_screenshot, '战斗画面', '战斗结果-再来一次',
                                                       success_wait=1, retry_wait=1)
            if result.is_success:
                return result

        return self.round_by_find_and_click_area(self.last_screenshot, '战斗画面', '战斗结果-完成',
                                                 success_wait=5, retry_wait=1)

    @node_from(from_name='判断再来一次', status='战斗结果-再来一次')
    @operation_node(name='恢复电量')
    def restore_charge(self) -> OperationRoundResult:
        # 检查是否在恢复电量界面
        result = self.round_by_find_area(self.last_screenshot, '实战模拟室', '恢复电量')
        if not result.is_success:
            # 没有弹窗，直接返回再来一次的结果
            return self.round_success(status='战斗结果-再来一次')

        config: ChargePlanConfig | None = self.ctx.run_context.get_config(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        if config.is_restore_charge_enabled:
            op = RestoreCharge(self.ctx)
            result = self.round_by_op_result(op.execute())
            self.try_next = result.is_success
        else:
            self.try_next = False

        # 关闭弹窗之后重新点击
        return self.round_by_click_area('战斗画面', '战斗结果-完成', success_wait=0.5)
