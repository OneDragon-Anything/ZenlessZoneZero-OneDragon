from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from one_dragon.utils import cmd_utils, os_utils
from one_dragon.utils.log_utils import log

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
    run_script: bool = False
    """是否运行自定义脚本 一条龙正常结束或失败结束时触发 手动停止不触发"""
    script_path: str = ''
    """脚本路径 (.bat/.cmd/.exe) 绝对路径或相对程序根目录的相对路径"""


def execute_after_done(
    ctx: OneDragonContext,
    run_result: ApplicationRunResult | None,
    request: AfterDoneRequest,
) -> None:
    """执行结束后动作。"""
    from one_dragon.base.operation.application.application_run_context import (
        RunFinishReason,
    )

    if run_result is None:
        return

    # 运行脚本:正常结束或失败结束时触发,手动停止(STOPPED)和未跑起来(NOT_STARTED)不触发
    if request.run_script and run_result.finish_reason in (
        RunFinishReason.COMPLETED,
        RunFinishReason.FAILED,
    ):
        _run_script(ctx, request.script_path)

    # 关游戏/关机/休眠/睡眠 只在正常完成时触发
    if (
        run_result.finish_reason != RunFinishReason.COMPLETED
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


def _close_game_before_run_script(ctx: OneDragonContext) -> None:
    """运行脚本前关闭游戏窗口 让脚本(如 BetterGI)接管。

    只发一次关闭消息后短暂等待;超时也不阻塞 后续脚本自行处理。
    """
    controller = ctx.controller if ctx is not None else None
    if controller is None or not controller.is_game_window_ready:
        return

    controller.close_game()
    for _ in range(6):  # 最多等 3 秒
        time.sleep(0.5)
        if not controller.is_game_window_ready:
            break


def _run_script(ctx: OneDragonContext, script_path: str) -> None:
    """先关闭游戏窗口 再运行结束后脚本 相对路径基于程序根目录。

    通过 cmd 非阻塞启动,不等待脚本结束;脚本找不到或启动失败只记日志 不影响后续动作。
    """
    _close_game_before_run_script(ctx)

    path = Path(script_path)
    if not path.is_absolute():
        path = Path(os_utils.get_work_dir()) / path
    if not path.is_file():
        log.error('结束后动作【运行指定脚本】未找到脚本 %s', str(path))
        return

    log.info('结束后动作【运行指定脚本】启动 %s', str(path))
    # CREATE_NO_WINDOW:隐藏承接脚本的 cmd 窗口,脚本自己 start 出来的程序不受影响;
    # CREATE_BREAKAWAY_FROM_JOB:开发模式由启动器用进程组管理时,让脚本脱离 jobobject,
    # 避免启动器进程退出后脚本连带被杀(参考 OpenGame 的做法)。
    creation_flags: int = subprocess.CREATE_NO_WINDOW
    if not getattr(sys, 'frozen', False):
        creation_flags |= subprocess.CREATE_BREAKAWAY_FROM_JOB

    try:
        subprocess.Popen(
            ['cmd', '/c', str(path)],
            cwd=os_utils.get_work_dir(),
            creationflags=creation_flags,
        )
    except Exception:
        log.error('结束后动作【运行指定脚本】启动失败 %s', str(path), exc_info=True)
