from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_operation import BagelOperation

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelWaitWarehouse(BagelOperation):
    """处理结算后的拟态单质提示，确认仓库持续可见后交给物资操作。"""

    def __init__(self, ctx: ZContext) -> None:
        """最多等待三十秒；提示处理与仓库确认共用同一时限。"""
        super().__init__(ctx, op_name='贝果-等待结算仓库', timeout_seconds=30)
        self._warehouse_since: float | None = None
        self._last_observed: float | None = None
        self._warehouse_frames: int = 0

    def handle_init(self) -> None:
        """重复执行时清除前次仓库观察。"""
        super().handle_init()
        self._last_observed = None
        self._reset_warehouse()

    def handle_pause(self) -> None:
        """暂停前后的画面不能计作连续仓库帧。"""
        super().handle_pause()
        self._reset_warehouse()

    def _reset_warehouse(self) -> None:
        """提示或未知画面出现时重新累计仓库稳定条件。"""
        self._warehouse_since = None
        self._warehouse_frames = 0

    @operation_node(name='处理提示并确认仓库', is_start_node=True, timeout_seconds=30)
    def wait_warehouse(self) -> OperationRoundResult:
        """每轮优先处理专用提示；三张新截图跨越一秒才确认仓库。"""
        stamp = self.last_screenshot_time
        if self._last_observed is not None and stamp <= self._last_observed:
            return self.round_wait('等待结算仓库的新截图', wait=0.5)
        self._last_observed = stamp
        if self._has('标题', '贝果-拟态单质提示'):
            self._reset_warehouse()
            clicked = self.round_by_find_and_click_area(
                self.last_screenshot, '贝果-拟态单质提示', '确认',
                success_wait=0.5, retry_wait=0.5,
            )
            if clicked.is_fail:
                return clicked
            # 点击失败或按钮暂不可见时继续识别，仍受整个操作的三十秒时限约束。
            return self.round_wait('等待拟态单质提示关闭' if clicked.is_success else clicked.status)
        if not all(self._has(area, '贝果-仓库') for area in ('放入仓库', '返回研究站')):
            self._reset_warehouse()
            return self.round_wait('等待结算仓库', wait=0.5)
        if self._warehouse_since is None:
            self._warehouse_since = stamp
        self._warehouse_frames += 1
        if self._warehouse_frames >= 3 and stamp - self._warehouse_since >= 1:
            return self.round_success('已到结算仓库')
        return self.round_wait('确认结算仓库持续可见', wait=0.5)
