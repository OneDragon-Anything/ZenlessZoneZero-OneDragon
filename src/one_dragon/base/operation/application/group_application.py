from typing import ClassVar, Optional

from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfig,
)
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt


class GroupApplication(Application):

    STATUS_ALL_DONE: ClassVar[str] = '全部结束'
    STATUS_NEXT: ClassVar[str] = '下一个'

    def __init__(
        self,
        ctx: OneDragonContext,
        group_id: str,
        op_to_enter_game: Optional[Operation] = None,
    ):
        Application.__init__(
            self,
            ctx=ctx,
            app_id=f'group_{group_id}',
            op_name='%s %s' % (gt('执行应用组'), group_id),
            op_to_enter_game=op_to_enter_game,
        )
        self._group_id: str = group_id

        self._group_config: Optional[ApplicationGroupConfig] = None
        self._current_app_idx: int = 0  # 当前运行的app 下标
        self._fail_app_idx_list: list[int] = []  # 失败的app下标 未实现重试功能

    @operation_node(name='获取应用组配置', is_start_node=True)
    def get_group_config(self) -> OperationRoundResult:
        """
        找出需要运行的app
        """
        self._group_config = self.ctx.app_group_manager.get_group_config(
            instance_idx=self.ctx.current_instance_idx,
            group_id=self._group_id,
        )
        if self._group_config is None:
            return self.round_fail(status=f"未找到应用组 {self._group_id}")

        self._current_app_idx = 0
        return self.round_success()

    @node_from(from_name='获取应用组配置')
    @node_from(from_name='执行应用')  # STATUS_ALL_DONE 以外的情况，都需要继续循环
    @operation_node(name='执行应用')
    def run_app(self) -> OperationRoundResult:
        """
        运行任务
        :return:
        """

        if self._current_app_idx < 0 or self._current_app_idx >= len(self._group_config.app_list):
            return self.round_success(status=GroupApplication.STATUS_ALL_DONE)

        config_item = self._group_config.app_list[self._current_app_idx]
        app = self.ctx.run_context.get_application(
            app_id=config_item.app_id,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self._group_id,
        )
        self._current_app_idx += 1
        if app is None:
            return self.round_fail(status=f"未找到应用 {config_item.app_id}")
        if not config_item.enabled:
            return self.round_success(status=f'应用未启用 {app.op_name}')
        run_record = self.ctx.run_context.get_run_record(
            app_id=app.app_id,
            instance_idx=self.ctx.current_instance_idx,
        )
        if run_record is not None:
            run_record.check_and_update_status()
            if run_record.is_done:
                return self.round_success(status=f'应用已完成 {app.op_name}')

        old_group_id = self.ctx.run_context.current_group_id
        old_app_id = self.ctx.run_context.current_app_id
        self.ctx.run_context.current_group_id = self._group_id
        self.ctx.run_context.current_app_id = app.app_id

        app_result = app.execute()

        self.ctx.run_context.current_group_id = old_group_id
        self.ctx.run_context.current_app_id = old_app_id

        if not app_result.success:
            self._fail_app_idx_list.append(self._current_app_idx - 1)

        return self.round_success(status=GroupApplication.STATUS_NEXT)

    @node_from(from_name='执行应用', status=STATUS_ALL_DONE)
    @operation_node(name='所有应用完成后')
    def after_all_done(self) -> OperationRoundResult:
        return self.round_success(status=GroupApplication.STATUS_ALL_DONE)
