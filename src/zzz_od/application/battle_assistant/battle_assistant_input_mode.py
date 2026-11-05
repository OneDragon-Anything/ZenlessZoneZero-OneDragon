from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


def apply_battle_assistant_input_mode(ctx: ZContext) -> tuple[bool, str]:
    """启用 macOS 前台键鼠输入。"""
    ctx.controller.enable_foreground_mode()
    ctx.controller.active_window()
    return True, '前台模式-键鼠'
