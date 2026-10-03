from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import cv2
import numpy as np

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_const import SAFE_UNLOCK_HITS
from zzz_od.application.bagel.bagel_operation import BagelOperation

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelUnlockSafe(BagelOperation):
    """打开电子保险箱：按 F 解锁并等待搜查面板，不重复交互。"""

    STATUS_READY: str = '已打开光圈解锁界面'
    STATUS_UNLOCKED: str = '电子保险箱搜索完成'

    def __init__(self, ctx: ZContext, phase: str = 'full') -> None:
        """按阶段执行交互或解锁；旧调用默认保留完整流程。"""
        if phase not in ('full', 'interact', 'unlock'):
            raise ValueError('未知保险箱操作阶段')
        super().__init__(ctx, op_name='贝果-解锁电子保险箱', timeout_seconds=45)
        self.phase: str = phase
        self.hits_done: int = 0
        self.ring_armed: bool = False

    def handle_init(self) -> None:
        """每次运行重置解锁进度。"""
        super().handle_init()
        self.hits_done = 0
        self.ring_armed = False

    def _press_timing(self) -> None:
        """精确点按；F 与 Space 等价，沿用交互键。"""
        self.ctx.controller.interact(press=True, press_time=0.05, release=True)
        self.hits_done += 1

    def _search_ready(self) -> bool:
        """电子保险箱面板进入搜查中或搜索结果且安全箱可见。"""
        return (
            all(self.round_by_find_area(
                self.last_screenshot, '贝果-局内', area,
            ).is_success for area in ('电子保险箱标题', '搜查安全箱'))
            and any(self.round_by_find_area(
                self.last_screenshot, '贝果-局内', area,
            ).is_success for area in ('搜查进行中', '搜查完成'))
        )

    @operation_node(name='进入大保险解锁', is_start_node=True)
    def enter_unlock(self) -> OperationRoundResult:
        """已有搜查面板则跳过；否则在电子保险箱提示处按一次 F。"""
        if self.is_bagel_result():
            return self.round_fail(self.STATUS_DEFEATED)
        if self._search_ready():
            return self.round_success(self.STATUS_UNLOCKED)
        if self.round_by_find_area(self.last_screenshot, '贝果-局内', '大保险解锁提示').is_success:
            return self.round_success(self.STATUS_READY if self.phase == 'interact' else '已在解锁界面')
        if self.phase == 'unlock':
            return self.round_fail('请先打开电子保险箱光圈解锁界面')
        if (
            not self.round_by_find_area(
                self.last_screenshot, '战斗画面', '按键-普通攻击',
            ).is_success
            or not self.round_by_find_area(
                self.last_screenshot, '贝果-局内', '电子保险箱交互',
            ).is_success
        ):
            return self.round_fail('未发现电子保险箱交互提示')
        self.ctx.controller.interact(press=True, press_time=0.2, release=True)
        return self.round_success('已按F进入解锁', wait=0.02)

    @node_from(from_name='进入大保险解锁', status='已按F进入解锁')
    @operation_node(name='等待解锁界面', timeout_seconds=8)
    def wait_unlock_ui(self) -> OperationRoundResult:
        """确认精确点按提示后按每轮光圈扩张进度点按。"""
        if self.is_bagel_result():
            return self.round_fail(self.STATUS_DEFEATED)
        if self._search_ready():
            return self.round_success(self.STATUS_UNLOCKED)
        if self.round_by_find_area(self.last_screenshot, '贝果-局内', '大保险解锁提示').is_success:
            return self.round_success(self.STATUS_READY if self.phase == 'interact' else '已在解锁界面')
        return self.round_wait('等待大保险解锁界面', wait=0.02)

    @node_from(from_name='进入大保险解锁', status='已在解锁界面')
    @node_from(from_name='等待解锁界面', status='已在解锁界面')
    @operation_node(name='时序点按解锁', timeout_seconds=20)
    def timing_hits(self) -> OperationRoundResult:
        """每轮先看到小圈，再在命中半径内点按一次，避免固定间隔逐轮漂移。"""
        if not self.round_by_find_area(
            self.last_screenshot, '贝果-局内', '大保险解锁提示',
        ).is_success:
            if self.is_bagel_result():
                return self.round_fail(self.STATUS_DEFEATED)
            if self._search_ready():
                return self.round_success(self.STATUS_UNLOCKED)
            return self.round_fail('解锁界面消失，无法点按')
        if self.hits_done >= SAFE_UNLOCK_HITS:
            return self.round_success('点按完成')
        ring = unlock_ring(self.last_screenshot)
        if ring is None:
            return self.round_wait('等待下一轮光圈', wait=0.02)
        color, radius = ring
        if radius <= 120:
            self.ring_armed = True
        hit_radius = 180 if color == '红' else 160
        if self.ring_armed and hit_radius <= radius <= 220:
            self._press_timing()
            self.ring_armed = False
            return self.round_wait(f'{color}圈点按 {self.hits_done}/{SAFE_UNLOCK_HITS}', wait=0.02)
        return self.round_wait('等待光圈进入命中范围', wait=0.02)

    @node_from(from_name='时序点按解锁', status='点按完成')
    @node_from(from_name='进入大保险解锁', status=STATUS_UNLOCKED)
    @node_from(from_name='等待解锁界面', status=STATUS_UNLOCKED)
    @node_from(from_name='时序点按解锁', status=STATUS_UNLOCKED)
    @operation_node(name='等待电子保险箱搜查面板', timeout_seconds=20)
    def wait_search(self) -> OperationRoundResult:
        """解锁成功后进入电子保险箱搜查；不补按 F，避免全部拾取。"""
        if self.is_bagel_result():
            return self.round_fail(self.STATUS_DEFEATED)
        if self._search_ready():
            return self.round_success(self.STATUS_UNLOCKED)
        if self.round_by_find_area(self.last_screenshot, '贝果-局内', '电子保险箱标题').is_success:
            return self.round_wait('等待电子保险箱搜查状态', wait=0.5)
        if self.round_by_find_area(self.last_screenshot, '贝果-局内', '大保险解锁提示').is_success:
            return self.round_wait('解锁中，等待进入搜查', wait=0.5)
        return self.round_wait('等待电子保险箱面板', wait=0.5)


@lru_cache(maxsize=1)
def _ring_sample_maps() -> tuple[np.ndarray, np.ndarray]:
    """沿 1080p 解锁圆盘的同心圆采样，复用坐标减少逐帧计算。"""
    angles = np.arange(360) * np.pi / 180
    radii = np.arange(15, 236)[:, None]
    return (
        (960 + radii * np.cos(angles)).astype(np.float32),
        (543 + radii * np.sin(angles)).astype(np.float32),
    )


def unlock_ring(screen: np.ndarray) -> tuple[str, float] | None:
    """返回扩张光圈颜色和外缘半径；零散背景颜色不足以组成圆周。"""
    map_x, map_y = _ring_sample_maps()
    sampled = cv2.remap(screen, map_x, map_y, cv2.INTER_LINEAR)
    hue, saturation, value = cv2.split(cv2.cvtColor(sampled, cv2.COLOR_RGB2HSV))
    bright = (saturation >= 95) & (value >= 140)
    candidates: list[tuple[float, str, float]] = []
    for name, color in (
        ('红', (hue <= 10) | (hue >= 165)),
        ('黄', (hue >= 10) & (hue <= 40)),
    ):
        coverage = (bright & color).mean(axis=1)
        valid = np.flatnonzero(coverage > 0.4)
        if len(valid):
            candidates.append((float(coverage.max()), name, float(valid[-1] + 15)))
    if not candidates:
        return None
    _, name, radius = max(candidates)
    return name, radius
