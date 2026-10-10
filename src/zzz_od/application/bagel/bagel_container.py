"""容器靠近与开箱共享的预算和画面判断。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from zzz_od.application.bagel.bagel_const import (
    CONTAINER_HOLD_TYPES,
    CONTAINER_PROMPT_AREAS,
    CONTAINER_TITLE_AREAS,
    MECH_HOLD_PRESS_TIME,
)
from zzz_od.application.bagel.bagel_operation import BagelOperation

if TYPE_CHECKING:
    from collections.abc import Callable

    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class ContainerRecovery:
    """一次容器动作的预算，子操作初始化不能重置。"""

    STATUS_REAPPROACH: str = '容器提示消失，需要重新靠近'
    TIME_LIMIT: float = 30
    APPROACH_LIMIT: int = 2
    INTERACT_LIMIT: int = 3

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """使用执行器的有效耗时计时，独立操作默认使用单调时钟。"""
        self.clock: Callable[[], float] = clock
        self.started_at: float | None = None
        self.approaches: int = 0
        self.interactions: int = 0
        self.last_interact_at: float | None = None
        self.last_input_frame: float | None = None

    def start(self) -> None:
        """首次进入箱前确认时开始计时。"""
        if self.started_at is None:
            self.started_at = self.clock()

    def error(self) -> str | None:
        """时间耗尽后禁止继续输入，仍允许识别已经打开的面板。"""
        if self.started_at is not None and self.clock() - self.started_at >= self.TIME_LIMIT:
            return '容器靠近与开箱恢复超过30秒'
        return None

    def request_approach(self) -> str | None:
        """申请额外重新靠近，首次靠近不占此次数。"""
        self.start()
        reason = self.error()
        if reason:
            return reason
        if self.approaches >= self.APPROACH_LIMIT:
            return '容器重新靠近已达2次上限'
        if self.interactions >= self.INTERACT_LIMIT:
            return '容器开箱交互已达3次上限'
        self.approaches += 1
        return None


def container_state(operation: BagelOperation, target: str) -> str:
    """先检查面板，避免把搜查中的 F 当成开箱提示。"""
    def has(area: str, screen: str = '贝果-局内') -> bool:
        """只读取当前截图。"""
        return operation._has(area, screen)

    # 任何一种容器的搜查面板标题出现，都算「面板已开」。
    # 三种标题在同一位置、不同文案，因此要逐个判，不能只判目标那一种 ——
    # 面板已开时目标名可能对不上（如标题渲染慢一帧）。
    titles = {name: has(area) for name, area in CONTAINER_TITLE_AREAS.items()}
    unlocking = has('大保险解锁提示')
    slots = has('搜查安全箱')
    searching = has('搜查进行中') or has('搜查完成')
    if target == 'safe' and unlocking and not titles['box'] and not titles['mech']:
        return 'ready'
    mine = titles.get(target, False)
    others = any(hit for name, hit in titles.items() if name != target)
    if mine and not others and slots and searching:
        return 'ready'
    if any(titles.values()) or unlocking or slots or searching:
        return 'panel'
    if not has('按键-普通攻击', '战斗画面'):
        return 'unknown'
    prompt = CONTAINER_PROMPT_AREAS.get(target)
    if prompt is None:
        raise ValueError(f'未知容器目标：{target}')
    return 'prompt' if has(prompt) and has('交互F键') else 'missing'


class BagelContainerOperation(BagelOperation):
    """共用开箱输入与观察规则，移动由流程执行器协调。"""

    def __init__(
        self, ctx: ZContext, target: str, op_name: str,
        recovery: ContainerRecovery | None = None,
    ) -> None:
        """独立执行自建预算；流程执行复用传入的预算。"""
        super().__init__(ctx, op_name=op_name)
        self.target: str = target
        self._owns_recovery: bool = recovery is None
        self.recovery: ContainerRecovery = recovery or ContainerRecovery(lambda: self.operation_usage_time)
        self._missing_since: float | None = None

    def handle_init(self) -> None:
        """仅独立执行重置预算，流程重建操作保留次数和时限。"""
        super().handle_init()
        if self._owns_recovery:
            self.recovery = ContainerRecovery(lambda: self.operation_usage_time)
        self._missing_since = None

    def interact_container(
        self, sent_status: str | None = None,
        observation_wait: float = 0.25, wait_after_interact: float = 0.25,
    ) -> OperationRoundResult:
        """识别面板、限次补按；保险箱连续解锁可缩短观察等待。"""
        if self.is_bagel_result():
            return self.round_fail(self.STATUS_DEFEATED)
        state = container_state(self, self.target)
        if state == 'ready':
            return self.round_success('容器已打开')
        self.ctx.controller.stop_moving_forward()
        self.recovery.start()
        reason = self.recovery.error()
        if reason:
            return self.round_recoverable_fail(reason)
        if state in ('panel', 'unknown'):
            self._missing_since = None
            return self.round_wait('等待容器面板或局内画面确认', wait=observation_wait)
        if self.recovery.last_input_frame is not None and self.last_screenshot_time <= self.recovery.last_input_frame:
            return self.round_wait('等待交互后的新截图', wait=min(0.15, observation_wait))
        now = self.recovery.clock()
        if self.recovery.last_interact_at is not None and now - self.recovery.last_interact_at < 2:
            return self.round_wait('等待开箱交互结果', wait=observation_wait)
        if self.recovery.interactions >= self.recovery.INTERACT_LIMIT:
            return self.round_recoverable_fail('容器开箱交互已达3次上限')
        if state == 'missing':
            if self._missing_since is None:
                self._missing_since = now
            if now - self._missing_since < 0.5:
                return self.round_wait('等待目标交互提示恢复', wait=observation_wait)
            return self.round_recoverable_fail(ContainerRecovery.STATUS_REAPPROACH)
        self._missing_since = None
        # 识别耗时也计入预算，在实际输入前再次检查。
        reason = self.recovery.error()
        if reason:
            return self.round_recoverable_fail(reason)
        # 输入前占用次数；控制器在发送后抛错也不能额外获得一次 F。
        self.recovery.interactions += 1
        self.recovery.last_interact_at = self.recovery.clock()
        self.recovery.last_input_frame = max(time.time(), self.last_screenshot_time)
        # 机械保险箱要按住交互键才开，按不够则箱子不响应；其余容器是点按。
        hold = self.target in CONTAINER_HOLD_TYPES
        self.ctx.controller.interact(
            press=True, press_time=MECH_HOLD_PRESS_TIME if hold else 0.2, release=True,
        )
        self.recovery.last_interact_at = self.recovery.clock()
        self.recovery.last_input_frame = max(time.time(), self.last_screenshot_time)
        return self.round_success(sent_status, wait=wait_after_interact)
