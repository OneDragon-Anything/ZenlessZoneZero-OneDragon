from typing import List, Optional, ClassVar

from one_dragon.base.config.one_dragon_config import OneDragonInstance, InstanceRun
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class OneDragonApp(Application):

    STATUS_ALL_DONE: ClassVar[str] = '全部结束'
    STATUS_NEXT: ClassVar[str] = '下一个'
    STATUS_NO_LOGIN: ClassVar[str] = '下一个'

    def __init__(self, ctx: OneDragonContext, app_id: str,
                 op_name: str = '一条龙',
                 op_to_enter_game: Optional[Operation] = None,
                 op_to_switch_account: Optional[Operation] = None):
        Application.__init__(
            self,
            ctx, app_id,
            op_name=gt(op_name),
            op_to_enter_game=op_to_enter_game
        )

        self._to_run_app_list: List[Application] = []  # 需要执行的app列表 有序
        self._current_app_idx: int = 0  # 当前运行的app 下标
        self._instance_list: List[OneDragonInstance] = []  # 需要运行的实例
        self._instance_idx: int = 0  # 当前运行的实例下标
        self._instance_start_idx: int = 0  # 最初开始的实例下标
        self._op_to_switch_account: Operation = op_to_switch_account  # 切换账号的op
        self._fail_app_idx: List[int] = []  # 失败的app下标
        self._current_retry_app_idx: int = 0  # 当前重试的_fail_app_idx的下标

    def get_app_list(self) -> List[Application]:
        return []

    def get_app_order_list(self) -> List[str]:
        """
        获取应用运行顺序
        :return: app id list
        """
        return self.ctx.one_dragon_app_config.app_order

    def update_app_order_list(self, new_app_orders: List[str]) -> None:
        """
        更新引用运行顺序
        :param new_app_orders: app id list
        :return:
        """
        self.ctx.one_dragon_app_config.app_order = new_app_orders

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        current_instance = self.ctx.one_dragon_config.current_active_instance
        if self.ctx.one_dragon_config.instance_run == InstanceRun.ALL.value.value:
            self._instance_list = []
            for i in self.ctx.one_dragon_config.instance_list:
                if not i.active_in_od:
                    continue
                self._instance_list.append(i)
                if i.idx == current_instance.idx:
                    self._instance_start_idx = len(self._instance_list) - 1
        else:
            self._instance_list = [current_instance]
            self._instance_start_idx = 0

        self._instance_idx = self._instance_start_idx

    def get_one_dragon_apps_in_order(self) -> List[Application]:
        """
        按运行顺序配置 返回需要在一条龙中运行的app
        :return:
        """
        all_apps = self.get_app_list()
        app_orders = self.get_app_order_list()

        result_list: List[Application] = []
        # 按顺序加入
        for app_order in app_orders:
            for app in all_apps:
                if app.app_id == app_order:
                    result_list.append(app)
                    break

        # 把没有在顺序里的加入
        for app in all_apps:
            if app.app_id not in app_orders:
                result_list.append(app)

        # 每次都更新配置
        new_app_orders = [app.app_id for app in result_list]
        self.update_app_order_list(new_app_orders)

        return result_list

    @node_from(from_name='切换账号后处理', status=STATUS_NEXT)  # 切换实例后重新开始
    @operation_node(name='检测任务状态', is_start_node=True)
    def check_app(self) -> OperationRoundResult:
        """
        找出需要运行的app
        :return:
        """
        order_app_list = self.get_one_dragon_apps_in_order()
        self._fail_app_idx = []

        self._to_run_app_list = []
        for app in order_app_list:
            if app.app_id not in self.ctx.one_dragon_app_config.app_run_list:
                continue
            app.run_record.check_and_update_status()
            if app.run_record.run_status_under_now == AppRunRecord.STATUS_SUCCESS:
                continue
            self._to_run_app_list.append(app)

        for app in self._to_run_app_list:  # 运行一条龙时 各app不需要改变上下文
            app.init_context_before_start = False
            app.stop_context_after_stop = False

        self._current_app_idx = 0
        self._current_retry_app_idx = 0

        return self.round_success()

    @node_from(from_name='检测任务状态')
    @node_from(from_name='运行任务', status=STATUS_NEXT)
    @operation_node(name='运行任务')
    def run_app(self) -> OperationRoundResult:
        """
        运行任务
        :return:
        """
        if self._current_app_idx < 0 or self._current_app_idx >= len(self._to_run_app_list):
            return self.round_success(status=OneDragonApp.STATUS_ALL_DONE)

        app = self._to_run_app_list[self._current_app_idx]
        app_result = app.execute()
        if not app_result.success:
            self._fail_app_idx.append(self._current_app_idx)
        self._current_app_idx += 1

        return self.round_success(status=OneDragonApp.STATUS_NEXT)

    @node_from(from_name='运行任务')
    @node_from(from_name='重试失败任务', status=STATUS_NEXT)
    @operation_node(name='重试失败任务')
    def run_retry_app(self) -> OperationRoundResult:
        if self._current_retry_app_idx < 0 or self._current_retry_app_idx >= len(self._fail_app_idx):
            return self.round_success(status=OneDragonApp.STATUS_ALL_DONE)

        app_idx = self._fail_app_idx[self._current_retry_app_idx]
        app = self._to_run_app_list[app_idx]
        app.execute()

        self._current_retry_app_idx += 1

        return self.round_success(status=OneDragonApp.STATUS_NEXT)

    @node_from(from_name='重试失败任务')
    @operation_node(name='切换实例配置')
    def switch_instance(self) -> OperationRoundResult:
        self._instance_idx += 1
        if self._instance_idx >= len(self._instance_list):
            self._instance_idx = 0

        self.ctx.switch_instance(self._instance_list[self._instance_idx].idx)
        log.info('下一个实例 %s', self.ctx.one_dragon_config.current_active_instance.name)

        return self.round_success()

    @node_from(from_name='切换实例配置')
    @operation_node(name='切换账号')
    def switch_account(self) -> OperationRoundResult:
        if len(self._instance_list) == 1:
            return self.round_success('无需切换账号')
        if self._op_to_switch_account is None:
            return self.round_fail('未实现切换账号')
        else:
            # return self.round_success(wait=1)  # 调试用
            return self.round_by_op_result(self._op_to_switch_account.execute())

    @node_from(from_name='切换账号')
    @operation_node(name='切换账号后处理')
    def after_switch_account(self) -> OperationRoundResult:
        if self._instance_idx == self._instance_start_idx:  # 已经完成一轮了
            return self.round_success(OneDragonApp.STATUS_ALL_DONE)
        else:
            return self.round_success(OneDragonApp.STATUS_NEXT)

    def after_operation_done(self, result: OperationResult):
        Application.after_operation_done(self, result)
        for app in self._to_run_app_list:   # 一条龙结束后 各app恢复
            app.init_context_before_start = True
            app.stop_context_after_stop = True
