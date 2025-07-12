import time

from typing import Optional

from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.battle_assistant.auto_battle_app import AutoBattleApp
from zzz_od.application.zzz_application import ZApplication
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.config.game_config import GamepadTypeEnum
from zzz_od.context.zzz_context import ZContext


class DodgeAssistantApp(ZApplication):

    def __init__(self, ctx: ZContext):
        """
        识别后进行闪避
        """
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='dodge_assistant',
            op_name=gt('闪避助手'),
            need_ocr=False
        )

        self.auto_op: Optional[AutoBattleOperator] = None

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
        if self.ctx.battle_assistant_config.gamepad_type == GamepadTypeEnum.NONE.value.value:
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
        result = auto_battle_utils.load_auto_op(self, 'dodge',
                                                self.ctx.battle_assistant_config.dodge_assistant_config)

        if result.is_success:
            self.ctx.dispatch_event(
                AutoBattleApp.EVENT_OP_LOADED,
                self.auto_op
            )
            self.auto_op.start_running_async()

        return result

    @node_from(from_name='加载自动战斗指令')
    @operation_node(name='闪避判断', mute=True)
    def check_dodge(self) -> OperationRoundResult:
        """
        识别当前画面 并进行点击
        :return:
        """
        now = time.time()

        screen = self.screenshot()
        self.auto_op.auto_battle_context.check_battle_state(screen, now)

        return self.round_wait(wait_round_time=self.ctx.battle_assistant_config.screenshot_interval)

    def _on_pause(self, e=None):
        ZApplication._on_pause(self, e)
        auto_battle_utils.stop_running(self.auto_op)

    def _on_resume(self, e=None):
        ZApplication._on_resume(self, e)
        auto_battle_utils.resume_running(self.auto_op)
