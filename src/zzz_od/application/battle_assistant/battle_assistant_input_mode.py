from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.controller.pc_button import pc_button_utils
from zzz_od.config.game_config import GamepadTypeEnum

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


def apply_battle_assistant_input_mode(ctx: ZContext) -> tuple[bool, str]:
    """按游戏助手临时后台开关和全局后台配置切换 controller。"""
    config = ctx.battle_assistant_config

    if config.background_mode:
        gamepad_type = ctx.game_config.background_gamepad_type

        if not pc_button_utils.is_vgamepad_installed():
            ctx.controller.enable_foreground_mode()
            return False, '未安装虚拟手柄依赖'

        if gamepad_type == GamepadTypeEnum.DS4.value.value:
            ctx.controller.enable_background_mode(GamepadTypeEnum.DS4.value.value)
            ctx.controller.btn_controller.set_key_press_time(ctx.game_config.ds4_key_press_time)
            return True, '后台模式-DS4'

        ctx.controller.enable_background_mode(GamepadTypeEnum.XBOX.value.value)
        ctx.controller.btn_controller.set_key_press_time(ctx.game_config.xbox_key_press_time)
        return True, '后台模式-Xbox'

    ctx.controller.enable_foreground_mode()
    ctx.controller.active_window()
    return True, '前台模式-键鼠'
