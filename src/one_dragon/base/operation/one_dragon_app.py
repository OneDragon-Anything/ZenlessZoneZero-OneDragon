from typing import ClassVar, List, Optional

from one_dragon.base.config.game_account_config import GameAccountConfig
from one_dragon.base.config.one_dragon_config import InstanceRun, OneDragonInstance
from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application.group_application import GroupApplication
from one_dragon.base.operation.application_base import Application
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
    STATUS_NO_LOGIN: ClassVar[str] = "下一个"

    def __init__(
        self,
        ctx: OneDragonContext,
        op_to_enter_game: Optional[Operation] = None,
        op_to_switch_account: Optional[Operation] = None,
    ):
        Application.__init__(
            self,
            ctx,
            app_id=application_const.ONE_DRAGON_APP_ID,
            op_name=gt(application_const.ONE_DRAGON_APP_NAME),
            op_to_enter_game=op_to_enter_game,
        )

        self._instance_list: List[OneDragonInstance] = []  # 需要运行的实例
        self._instance_idx: int = 0  # 当前运行的实例下标
        self._instance_start_idx: int = 0  # 最初开始的实例下标
        self._op_to_switch_account: Operation = op_to_switch_account  # 切换账号的op

        self._last_account_config: GameAccountConfig | None = None
        self._last_controller: ControllerBase | None = None

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        current_instance = self.ctx.one_dragon_config.current_active_instance
        if self.ctx.one_dragon_config.instance_run == InstanceRun.ALL.value.value:
            self._instance_list = self.ctx.one_dragon_config.instance_list_in_od

            if not self._instance_list:
                if current_instance is not None:
                    self._instance_list = [current_instance]
                else:
                    raise RuntimeError('未找到可以在一条龙中运行的实例')

            self._instance_start_idx = 0
            if current_instance is not None:
                for idx, instance in enumerate(self._instance_list):
                    if instance.idx == current_instance.idx:
                        self._instance_start_idx = idx
                        break
        else:
            self._instance_list = [current_instance]
            self._instance_start_idx = 0

        self._instance_idx = self._instance_start_idx

        if current_instance not in self._instance_list:
            self.ctx.switch_instance(self._instance_list[self._instance_idx].idx)

    @node_from(from_name='切换账号后处理', status=STATUS_NEXT)  # 切换实例后重新开始
    @operation_node(name='运行应用组', is_start_node=True)
    def run_group_app(self) -> OperationRoundResult:
        op = GroupApplication(
            ctx=self.ctx,
            group_id=application_const.DEFAULT_GROUP_ID,
            op_to_enter_game=self.op_to_enter_game
        )
        return self.round_by_op_result(op.execute())

    @node_from(from_name='运行应用组')
    @operation_node(name='切换实例配置', screenshot_before_round=False)
    def switch_instance(self) -> OperationRoundResult:
        self._last_account_config = self.ctx.game_account_config
        self._last_controller = self.ctx.controller

        self._instance_idx += 1
        if self._instance_idx >= len(self._instance_list):
            self._instance_idx = 0
        self.ctx.switch_instance(self._instance_list[self._instance_idx].idx)
        log.info('下一个实例 %s', self.ctx.one_dragon_config.current_active_instance.name)

        if (self._last_account_config is not None
            and self._last_account_config.game_path != self.ctx.game_account_config.game_path
        ):
            return self.round_success(status='游戏路径不同')

        return self.round_success()

    @node_from(from_name='切换实例配置', status='游戏路径不同')
    @operation_node(name='关闭游戏', screenshot_before_round=False)
    def close_game(self) -> OperationRoundResult:
        # 刷新窗口句柄, 避免旧缓存导致误判
        if self._last_controller is None:
            return self.round_success()

        if self._last_controller.is_game_window_ready:
            # 关闭游戏
            self._last_controller.close_game()
            return self.round_retry('检查是否关闭成功', wait=3)

        # 有时候游戏关闭了, 游戏占用的配置等文件没关闭, 故需等一会
        log.info('等待游戏占用文件释放(10s)...')
        return self.round_success(wait=10)

    @node_from(from_name='切换实例配置')
    @operation_node(name='切换账号', screenshot_before_round=False)
    def switch_account(self) -> OperationRoundResult:
        if len(self._instance_list) == 1:
            return self.round_success('无需切换账号')
        if self._op_to_switch_account is None:
            return self.round_fail('未实现切换账号')
        else:
            # return self.round_success(wait=1)  # 调试用
            return self.round_by_op_result(self._op_to_switch_account.execute())

    @node_from(from_name='关闭游戏')
    @operation_node(name='切换账号重新打开游戏', screenshot_before_round=False)
    def after_close_game(self) -> OperationRoundResult:
        if self.op_to_enter_game is None:
            return self.round_fail('未提供打开游戏方式')
        else:
            return self.round_by_op_result(self.op_to_enter_game.execute())

    @node_from(from_name='切换账号')
    @node_from(from_name='切换账号重新打开游戏')
    @operation_node(name='切换账号后处理', screenshot_before_round=False)
    def after_switch_account(self) -> OperationRoundResult:
        if self._instance_idx == self._instance_start_idx:  # 已经完成一轮了
            return self.round_success(OneDragonApp.STATUS_ALL_DONE)
        else:
            return self.round_success(OneDragonApp.STATUS_NEXT)

    def after_operation_done(self, result: OperationResult):
        Application.after_operation_done(self, result)
