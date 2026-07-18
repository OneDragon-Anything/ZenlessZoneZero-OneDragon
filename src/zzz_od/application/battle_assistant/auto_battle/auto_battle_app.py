from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.battle_assistant.auto_battle import auto_battle_const
from zzz_od.application.battle_assistant.battle_assistant_input_mode import (
    apply_battle_assistant_input_mode,
)
from zzz_od.application.zzz_application import ZApplication

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class AutoBattleApp(ZApplication):

    EVENT_OP_LOADED: ClassVar[str] = '指令已加载'

    def __init__(self, ctx: ZContext):
        """
        识别后进行闪避
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=auto_battle_const.APP_ID,
            op_name=auto_battle_const.APP_NAME,
        )

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        pass

    @operation_node(name='手柄检测', is_start_node=True)
    def check_gamepad(self) -> OperationRoundResult:
        """
        检测手柄
        :return:
        """
        success, status = apply_battle_assistant_input_mode(self.ctx)
        return self.round_success(status=status) if success else self.round_fail(status=status)

    @node_from(from_name='手柄检测')
    @operation_node(name='加载自动战斗指令')
    def load_op(self) -> OperationRoundResult:
        """
        加载战斗指令
        :return:
        """
        try:
            self.ctx.auto_battle_context.init_auto_op(
                sub_dir='auto_battle',
                op_name=self.ctx.battle_assistant_config.auto_battle_config,
            )
            self.ctx.auto_battle_context.auto_ultimate_enabled = self.ctx.battle_assistant_config.auto_ultimate_enabled
        except Exception:
            # 捕获异常，显式返回 Fail，防止框架自动重试
            return self.round_fail(status='加载指令失败')

        self.ctx.dispatch_event(
            AutoBattleApp.EVENT_OP_LOADED,
            self.ctx.auto_battle_context.auto_op,
        )
        self.ctx.auto_battle_context.start_auto_battle()
        # 只有在手动使用自动战斗指令时，才使用配置中的开关
        # 其他指令调用 start_auto_battle 时，会使用默认值 True
        self.ctx.auto_battle_context.auto_ultimate_enabled = self.ctx.battle_assistant_config.auto_ultimate_enabled

        return self.round_success()

    @node_from(from_name='加载自动战斗指令')
    @operation_node(name='画面识别', mute=True)
    def check_screen(self) -> OperationRoundResult:
        """
        识别当前画面 并进行点击
        :return:
        """
        self.ctx.auto_battle_context.check_battle_state(self.last_screenshot, self.last_screenshot_time)
        return self.round_wait(wait_round_time=self.ctx.battle_assistant_config.screenshot_interval)

    def handle_pause(self, e=None):
        self.ctx.auto_battle_context.stop_auto_battle()

    def handle_resume(self, e=None):
        if self.current_node.node is not None and self.current_node.node.cn == '画面识别':
            self.ctx.auto_battle_context.resume_auto_battle()
