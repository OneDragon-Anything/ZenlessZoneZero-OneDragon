"""独立开发工具的测试运行线程与可回查记录。"""

from __future__ import annotations

import ctypes
import json
import time
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QThread, Signal

from one_dragon.base.operation.one_dragon_context import ContextKeyboardEventEnum
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow, release_flow_inputs

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from one_dragon.base.operation.context_event_bus import ContextEventItem
    from zzz_od.application.bagel.bagel_fixed_map import BagelFixedMap
    from zzz_od.application.bagel.bagel_flow import BagelFlow
    from zzz_od.context.zzz_context import ZContext


class FlowTrialWorker(QThread):
    """在线程中初始化服务，所有事件写入本次独立 JSONL 文件。"""

    observed = Signal(object)
    completed = Signal(str)

    def __init__(
        self,
        instance_idx: int,
        flow: BagelFlow,
        step_ids: tuple[str, ...],
        ctx: ZContext | None = None,
        parent: QWidget | None = None,
        map_snapshot: BagelFixedMap | None = None,
    ) -> None:
        """接收不可变快照，不读取运行期间可能被保存的草稿。"""
        super().__init__(parent)
        self.instance_idx: int = instance_idx
        self.flow: BagelFlow = flow
        self.map_snapshot: BagelFixedMap | None = map_snapshot
        self.step_ids: tuple[str, ...] = step_ids
        self.ctx: ZContext | None = ctx
        self.owns_run: bool = False
        self.stop_requested: Event = Event()
        self.operation: BagelRunFlow | None = None
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.record_path: Path = (
            Path(os_utils.get_work_dir())
            / '.log'
            / 'bagel_trials'
            / f'{stamp}-{uuid4().hex[:8]}.jsonl'
        )

    def _record(self, event: dict[str, object]) -> None:
        """记录持久化失败则停止，不能把没有记录的测试运行当作验收。"""
        with self.record_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        self.observed.emit(event)

    def _wait_for_mouse_release(self) -> bool:
        """切窗前等待左键持续松开，避免启动点击或双击跟随焦点进入游戏。"""
        started = time.monotonic()
        released_at: float | None = None
        while not self.stop_requested.is_set():
            now = time.monotonic()
            if now - started >= 5:
                return False
            if ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                released_at = None
            else:
                if released_at is None:
                    released_at = now
                elif now - released_at >= 0.3:
                    return True
            if self.stop_requested.wait(0.02):
                return False
        return False

    def run(self) -> None:
        """初始化服务并执行步骤，线程结束前清理本次运行。"""
        outcome = '测试运行已取消'
        try:
            if self.stop_requested.is_set():
                return
            self.record_path.parent.mkdir(parents=True, exist_ok=True)
            self._record(
                {
                    'kind': 'snapshot',
                    'flow': self.flow.to_dict(),
                    'step_ids': self.step_ids,
                }
            )
            if self.ctx is None:
                from zzz_od.context.zzz_context import ZContext

                self.ctx = ZContext()
            self.ctx.listen_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)
            if self.ctx.controller is None:
                if self.instance_idx not in {
                    item.idx for item in self.ctx.one_dragon_config.instance_list
                }:
                    raise ValueError('请选择已经配置的账号编号')
                self.ctx.current_instance_idx = self.instance_idx
                self.ctx.reload_instance_config()
                self.ctx.screen_loader.reload()
                self.ctx.init_ocr()
                self.ctx.init_controller()
            if self.stop_requested.is_set():
                return
            if not self._wait_for_mouse_release():
                if not self.stop_requested.is_set():
                    outcome = '未启动：鼠标左键持续按下，请松开后重新执行。'
                return
            if (
                self.ctx.current_instance_idx != self.instance_idx
                or not self.ctx.run_context.start_running()
            ):
                outcome = '未启动：账号不一致、任务占用或游戏窗口不可用。'
                return
            self.owns_run = True
            if self.stop_requested.is_set():
                return
            self.operation = BagelRunFlow(
                self.ctx,
                self.flow,
                step_ids=self.step_ids,
                on_event=self._record,
                map_snapshot=self.map_snapshot,
            )
            result = self.operation.execute()
            outcome = f'{"完成" if result.success else "停止"}：{result.status}\n记录：{self.record_path}'
        except Exception as error:
            log.error('贝果流程测试运行异常', exc_info=True)
            outcome = f'测试运行异常：{error}\n记录：{self.record_path}'
        finally:
            if self.ctx is not None:
                self.ctx.unlisten_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)
            try:
                if self.owns_run:
                    try:
                        release_flow_inputs(self.ctx)
                    finally:
                        self.ctx.run_context.stop_running()
                        self.owns_run = False
            except Exception as error:
                log.error('贝果测试运行清理输入失败', exc_info=True)
                outcome = f'测试运行清理失败：{error}'
            try:
                if self.record_path.exists():
                    self._record({'kind': 'trial_finished', 'status': outcome})
            except OSError:
                log.error('贝果测试运行结束记录写入失败', exc_info=True)
                outcome = f'{outcome}\n结束记录写入失败，请查看日志。'
            self.completed.emit(outcome)

    def _on_key_press(self, event: ContextEventItem) -> None:
        """沿用主程序的按键事件，准备阶段也能用全局停止键取消。"""
        if self.ctx is not None and event.data == self.ctx.key_stop_running:
            self.stop_requested.set()

    def stop(self) -> None:
        """请求停止，输入和运行状态由工作线程收尾。"""
        self.stop_requested.set()
        if self.owns_run:
            self.ctx.run_context.stop_running()
