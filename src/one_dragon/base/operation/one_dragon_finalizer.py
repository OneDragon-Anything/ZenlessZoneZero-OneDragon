from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from one_dragon.utils import cmd_utils

if TYPE_CHECKING:
    from one_dragon.base.operation.application.application_run_context import (
        ApplicationRunResult,
    )
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


@dataclass(slots=True)
class AfterDoneRequest:
    """结束后动作请求。"""

    close_game: bool = False
    shutdown_seconds: int | None = None
    hibernate: bool = False
    sleep: bool = False


def execute_after_done(
    ctx: OneDragonContext,
    run_result: ApplicationRunResult | None,
    request: AfterDoneRequest,
) -> None:
    """执行结束后动作。"""
    from one_dragon.base.operation.application.application_run_context import (
        RunFinishReason,
    )

    if (
        run_result is None
        or run_result.finish_reason != RunFinishReason.COMPLETED
        or not (
            request.close_game
            or request.shutdown_seconds is not None
            or request.hibernate
            or request.sleep
        )
    ):
        return

    if request.close_game and ctx.controller is not None:
        ctx.controller.close_game()
    if request.shutdown_seconds is not None:
        cmd_utils.shutdown_sys(request.shutdown_seconds)
    if request.hibernate:
        cmd_utils.hibernate_sys()
    if request.sleep:
        cmd_utils.sleep_sys()
