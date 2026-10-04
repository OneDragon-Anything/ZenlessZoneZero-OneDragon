from __future__ import annotations

import time
from typing import TYPE_CHECKING

import cv2
import numpy as np

from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_slots import slot_crop

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.geometry.point import Point
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


def carried_slot_state(screen: MatLike, center: Point) -> bool | None:
    """识别物品或灰色空槽；黑屏、遮挡和过渡图像保留为未知。

    备战空武备槽有灰色图案，方差超过普通背包空格，不能单靠方差判断。
    """
    crop = slot_crop(screen, center, half=30)
    if crop is None or crop.shape != (60, 60, 3):
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    bright = float(np.mean(gray > 90))
    if float(np.std(gray)) >= 30 and bright >= 0.08:
        return True
    high = float(np.percentile(gray, 95))
    if 12 <= high <= 80 and bright < 0.01:
        return False
    return None


class BagelTransferOperation(BagelOperation):
    """转存共用的双击操作、稳定帧检查和失败进度记录。"""

    def __init__(self, ctx: ZContext, op_name: str) -> None:
        """调用者负责选择源物品并核对转存结果。"""
        super().__init__(ctx, op_name=op_name, timeout_seconds=180)
        self.moved: int = 0
        self.source_label: str = ''
        self.observation: str = ''
        self.pending: bool = False
        self.read_misses: int = 0
        self.pending_checks: int = 0
        self.pending_started: float = 0
        self.pause_generation: int = 0
        self._stable_image: MatLike | None = None
        self._stable_signature: tuple[object, ...] | None = None

    def handle_init(self) -> None:
        """重新执行只依据当前截图，不继承旧坐标与进度。"""
        super().handle_init()
        self.moved = 0
        self.source_label = ''
        self.observation = ''
        self.pending = False
        self.read_misses = 0
        self.pending_checks = 0
        self.pending_started = 0
        self.pause_generation = 0
        self._stable_image = None
        self._stable_signature = None

    def handle_pause(self) -> None:
        """标记双击中途的暂停，恢复后不补发第二次点击。"""
        super().handle_pause()
        self.pause_generation += 1
        self._stable_image = None

    def handle_resume(self) -> None:
        """暂停时间不计入等待，已点击入仓的物品只继续核验。"""
        super().handle_resume()
        self.pending_started = time.monotonic()
        self._stable_image = None

    def transfer_fail(self, reason: str) -> OperationRoundResult:
        """向上保留具体位置和已完成格数，基类负责保存现场。"""
        return self.round_fail(
            f'启动清空失败：{self.source_label or "核对画面"}，{reason}；已转存 {self.moved} 格；{self.observation}',
        )

    def read_again(self, reason: str) -> OperationRoundResult:
        """识别不全只读图，连续五帧失败即停止。"""
        self.read_misses += 1
        if self.read_misses >= 5:
            return self.transfer_fail(reason)
        return self.round_wait(reason, wait=0.5)

    def wait_transfer(self, reason: str) -> OperationRoundResult:
        """结果未确认时等待，不再次发送输入。"""
        self.pending_checks += 1
        if self.pending_checks >= 10 or time.monotonic() - self.pending_started >= 5:
            return self.transfer_fail(reason)
        return self.round_wait(reason, wait=0.5)

    def stable_slots(
        self, centers: tuple[Point, ...], signature: tuple[object, ...],
    ) -> bool:
        """数值与相关格子连续两帧一致才允许操作或报告完成。"""
        previous = self._stable_image
        same = previous is not None and self._stable_signature == signature
        self._stable_image = self.last_screenshot.copy()
        self._stable_signature = signature
        if not same:
            return False
        for center in centers:
            before = slot_crop(previous, center)
            after = slot_crop(self.last_screenshot, center)
            if before is None or after is None or before.shape != after.shape:
                return False
            if float(np.abs(before.astype(np.float32) - after.astype(np.float32)).mean()) >= 4:
                return False
        return True

    def double_click_item(self, center: Point, label: str) -> OperationRoundResult:
        """向同一槽位发送一组快速双击，由调用者核验结果及决定是否重试。"""
        if not self.ctx.run_context.is_context_running:
            return self.round_wait('等待运行恢复后重新识别', wait=0.5)
        generation = self.pause_generation
        # 连续卸装实测：识别后立即双击会只开关详情，留出间隔后再发送输入。
        time.sleep(0.5)
        if generation != self.pause_generation or not self.ctx.run_context.is_context_running:
            self._stable_image = None
            return self.round_wait('等待运行恢复后重新识别', wait=0.5)
        self.source_label = label
        self.pending = True
        self.pending_checks = 0
        self.pending_started = time.monotonic()
        self._stable_image = None
        if not self.ctx.controller.click(center, press_time=0.08):
            return self.transfer_fail('双击物品的第一次点击失败')
        time.sleep(0.11)
        if generation != self.pause_generation or not self.ctx.run_context.is_context_running:
            return self.transfer_fail('双击物品被中断，未发送第二次点击')
        if not self.ctx.controller.click(center, press_time=0.08):
            return self.transfer_fail('双击物品的第二次点击失败')
        self.pending_started = time.monotonic()
        return self.round_wait(f'等待{label}双击转入仓库', wait=0.5)

    def finish_transfer(self) -> None:
        """仅在子操作确认物品去向后推进进度。"""
        self.moved += 1
        self.pending = False
        self.read_misses = 0
        self._stable_image = None
