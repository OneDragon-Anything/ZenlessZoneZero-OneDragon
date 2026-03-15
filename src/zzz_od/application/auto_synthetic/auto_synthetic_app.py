from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.application.auto_synthetic import auto_synthetic_const
from zzz_od.application.auto_synthetic.auto_synthetic_config import AutoSyntheticConfig
from zzz_od.application.auto_synthetic.operations.ether_battery_synthesis_op import EtherBatterySynthesisOp
from zzz_od.application.auto_synthetic.operations.hifi_master_synthesis_op import HifiMasterSynthesisOp


class Task:
    """任务类"""

    def __init__(self, name: str, operation_class, enabled: bool = True):
        self.name = name
        self.operation_class = operation_class
        self.enabled = enabled
        self.result = None


class AutoSyntheticApp(ZApplication):
    TASK_HIFI_MASTER = '母盘合成'
    TASK_ETHER_BATTERY = '电池合成'

    def __init__(self, ctx: ZContext) -> None:
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=auto_synthetic_const.APP_ID,
            op_name=auto_synthetic_const.APP_NAME,
        )
        self.config: AutoSyntheticConfig = self.ctx.run_context.get_config(
            app_id=auto_synthetic_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.tasks: list[Task] = []
        self.current_task_index: int = 0

    @operation_node(name='检查配置', is_start_node=True)
    def check_config(self) -> OperationRoundResult:
        """检查配置，构建任务队列"""
        self._build_tasks()

        if not self.tasks:
            return self.round_success(status='无需合成')

        self.current_task_index = 0
        return self._execute_all_tasks()

    def _build_tasks(self) -> None:
        """根据配置构建任务列表"""
        self.tasks = []

        if self.config.hifi_master_copy:
            self.tasks.append(Task(
                name=self.TASK_HIFI_MASTER,
                operation_class=HifiMasterSynthesisOp
            ))

        if self.config.source_ether_battery:
            self.tasks.append(Task(
                name=self.TASK_ETHER_BATTERY,
                operation_class=EtherBatterySynthesisOp
            ))

    def _execute_all_tasks(self) -> OperationRoundResult:
        """执行所有任务"""
        while self.current_task_index < len(self.tasks):
            task = self.tasks[self.current_task_index]

            # 创建并执行操作
            if task.name == self.TASK_ETHER_BATTERY:
                op = task.operation_class(self.ctx, self.config)
            else:
                op = task.operation_class(self.ctx)

            result = op.execute()
            task.result = result

            # 移动到下一个任务
            self.current_task_index += 1

        # 所有任务执行完毕
        return self.round_success(status='全部完成')

    @node_from(from_name='检查配置', status='全部完成')
    @node_from(from_name='检查配置', status='无需合成')
    @operation_node(name='最终返回')
    def final_return(self) -> OperationRoundResult:
        """最终返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())