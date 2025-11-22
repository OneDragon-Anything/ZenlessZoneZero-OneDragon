from __future__ import annotations

from typing import ClassVar, TYPE_CHECKING

from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.battle_assistant.auto_battle import auto_battle_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.config.game_config import GamepadTypeEnum

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
            op_name=gt(auto_battle_const.APP_NAME),
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
        gamepad_type = self.ctx.battle_assistant_config.gamepad_type
        if gamepad_type == GamepadTypeEnum.NONE.value.value:
            self.ctx.controller.enable_keyboard()

            return self.round_success(status='无需手柄')
        elif not pc_button_utils.is_vgamepad_installed():
            self.ctx.controller.enable_keyboard()
            return self.round_fail(status='未安装虚拟手柄依赖')
        elif self.ctx.battle_assistant_config.gamepad_type == GamepadTypeEnum.XBOX.value.value:
            self.ctx.controller.enable_xbox()
            self.ctx.controller.btn_controller.set_key_press_time(self.ctx.game_config.xbox_key_press_time)
        elif self.ctx.battle_assistant_config.gamepad_type == GamepadTypeEnum.DS4.value.value:
            self.ctx.controller.enable_ds4()
            self.ctx.controller.btn_controller.set_key_press_time(self.ctx.game_config.ds4_key_press_time)
        return self.round_success(status='已安装虚拟手柄依赖')

    @node_from(from_name='手柄检测')
    @operation_node(name='加载自动战斗指令')
    def load_op(self) -> OperationRoundResult:
        """
        加载战斗指令
        :return:
        """
        self.ctx.auto_battle_context.init_auto_op(
            sub_dir='auto_battle',
            op_name=self.ctx.battle_assistant_config.auto_battle_config,
        )

        self.ctx.dispatch_event(
            AutoBattleApp.EVENT_OP_LOADED,
            self.ctx.auto_battle_context.auto_op,
        )
        self.ctx.auto_battle_context.start_auto_battle()

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
