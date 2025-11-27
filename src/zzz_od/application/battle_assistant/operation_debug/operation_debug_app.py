from typing import List, Optional

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.loader import ConditionalOperatorLoader
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from zzz_od.application.battle_assistant.operation_debug import operation_debug_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.config.game_config import GamepadTypeEnum
from zzz_od.context.zzz_context import ZContext


class OperationDebugApp(ZApplication):

    def __init__(self, ctx: ZContext):
        """
        识别后进行闪避
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=operation_debug_const.APP_ID,
            op_name=operation_debug_const.APP_NAME,
        )

        self.ops: Optional[List[AtomicOp]] = None
        self.op_idx: int = 0

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
    @operation_node(name='加载动作指令')
    def load_op(self) -> OperationRoundResult:
        """
        加载战斗指令
        :return:
        """
        template_name = self.ctx.battle_assistant_config.debug_operation_config

        try:
            # 直接加载操作模板文件
            template_data = ConditionalOperatorLoader.load_yaml_config(
                sub_dir=['auto_battle_operation'],
                template_name=template_name,
                read_from_merged=False
            )

            # 创建一个临时的 AutoBattleOperator 实例来获取 atomic_op
            op = AutoBattleOperator(self.ctx.auto_battle_context, 'auto_battle', '全配队通用')

            # 从模板数据中提取操作
            operations = template_data.get('operations', [])
            if len(operations) == 0:
                return self.round_fail('操作模板中没有找到可执行的操作')

            # 创建一个 ConditionalOperatorLoader 实例来处理模板展开
            loader = ConditionalOperatorLoader(
                sub_dir=['auto_battle_operation'],
                template_name=template_name,
                operation_template_sub_dir=['auto_battle_operation'],
                state_handler_template_sub_dir=['auto_battle_state_handler'],
                read_from_merged=False
            )

            self.ops = []
            for operation_data in operations:
                operation_def = OperationDef(operation_data)
                # 使用 load_template_for_operation 来递归展开所有模板引用
                expanded_operations = loader.load_template_for_operation(
                    operation_def, set()
                )
                for expanded_op in expanded_operations:
                    self.ops.append(op.get_atomic_op(expanded_op))

            self.op_idx = 0
            return self.round_success()
        except Exception:
            log.error('指令模板加载失败', exc_info=True)
            return self.round_fail()

    @node_from(from_name='加载动作指令')
    @operation_node(name='执行指令')
    def run_operations(self) -> OperationRoundResult:
        """
        执行指令
        :return:
        """
        self.ops[self.op_idx].execute()
        self.op_idx += 1
        if self.op_idx >= len(self.ops):
            if self.ctx.battle_assistant_config.debug_operation_repeat:
                self.op_idx = 0
                return self.round_wait()
            else:
                return self.round_success()
        else:
            return self.round_wait()
