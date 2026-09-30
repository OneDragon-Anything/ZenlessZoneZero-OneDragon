"""独立开发工具的试跑线程与可回查记录。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QThread, Signal

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_run_flow import BagelRunFlow, release_flow_inputs

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

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
    ) -> None:
        """接收不可变快照，不读取运行期间可能被保存的草稿。"""
        super().__init__(parent)
        self.instance_idx: int = instance_idx
        self.flow: BagelFlow = flow
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
        """记录持久化失败则停止，不能把没有记录的试跑当作验收。"""
        with self.record_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        self.observed.emit(event)

    def run(self) -> None:
        """初始化服务并执行步骤，线程结束前清理本次运行。"""
        outcome = '试跑已取消'
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
            )
            result = self.operation.execute()
            outcome = f'{"完成" if result.success else "停止"}：{result.status}\n记录：{self.record_path}'
        except Exception as error:
            log.error('贝果流程试跑异常', exc_info=True)
            outcome = f'试跑异常：{error}\n记录：{self.record_path}'
        finally:
            try:
                if self.owns_run:
                    try:
                        release_flow_inputs(self.ctx)
                    finally:
                        self.ctx.run_context.stop_running()
                        self.owns_run = False
            except Exception as error:
                log.error('贝果试跑清理输入失败', exc_info=True)
                outcome = f'试跑清理失败：{error}'
            try:
                if self.record_path.exists():
                    self._record({'kind': 'trial_finished', 'status': outcome})
            except OSError:
                log.error('贝果试跑结束记录写入失败', exc_info=True)
                outcome = f'{outcome}\n结束记录写入失败，请查看日志。'
            self.completed.emit(outcome)

    def stop(self) -> None:
        """请求停止，输入和运行状态由工作线程收尾。"""
        self.stop_requested.set()
        if self.owns_run:
            self.ctx.run_context.stop_running()
