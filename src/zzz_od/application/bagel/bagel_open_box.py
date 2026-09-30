from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_operation import BagelOperation

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelOpenBox(BagelOperation):
    """打开已到达的普通武备箱，等待物品揭示，不触发全部拾取。"""

    def __init__(self, ctx: ZContext) -> None:
        """导航结束后调用，不处理大小保险箱。"""
        super().__init__(ctx, op_name='贝果-打开普通武备箱', timeout_seconds=30)
        self.interact_attempts: int = 0
        self.last_interact_time: float = 0
        self._prompt_without_hud: int = 0

    def handle_init(self) -> None:
        """每次运行独立计数；是否补按 F 由当前画面和次数决定。"""
        super().handle_init()
        self.interact_attempts = 0
        self.last_interact_time = 0
        self._prompt_without_hud = 0

    def _press_interact(self) -> None:
        """记录交互时刻；补按也计入两次总上限。"""
        self.ctx.controller.interact(press=True, press_time=0.2, release=True)
        self.interact_attempts += 1
        self.last_interact_time = self.last_screenshot_time

    @operation_node(name='打开武备箱', is_start_node=True, node_max_retry_times=8)
    def open_box(self) -> OperationRoundResult:
        """已有搜查面板时跳过交互。喧响值被记分挡住时，武备箱提示还在就再看一帧后按 F。"""
        if self.is_bagel_result():
            return self.round_fail(self.STATUS_DEFEATED)
        if self.round_by_find_area(self.last_screenshot, '贝果-局内', '搜查容器标题').is_success:
            self._prompt_without_hud = 0
            return self.round_success()
        has_prompt = self.round_by_find_area(
            self.last_screenshot, '贝果-局内', '武备箱交互',
        ).is_success
        has_hud = self.round_by_find_area(
            self.last_screenshot, '贝果-局内', '喧响值',
        ).is_success
        if has_prompt and has_hud:
            self._prompt_without_hud = 0
            self._press_interact()
            return self.round_success(wait=0.5)
        if has_prompt:
            self._prompt_without_hud += 1
            if self._prompt_without_hud >= 2:
                self._press_interact()
                return self.round_success(wait=0.5)
            return self.round_retry('喧响值暂时对不上，再看武备箱提示', wait=0.3)
        self._prompt_without_hud = 0
        return self.round_retry('未发现武备箱交互提示', wait=0.3)

    @node_from(from_name='打开武备箱')
    @operation_node(name='等待武备箱搜查面板', timeout_seconds=25)
    def wait_search(self) -> OperationRoundResult:
        """面板还在时不按 F；面板关掉且箱前提示回来后，允许再按一次。"""
        if self.is_bagel_result():
            return self.round_fail(self.STATUS_DEFEATED)
        states = [
            self.round_by_find_area(self.last_screenshot, '贝果-局内', area).is_success
            for area in ('搜查容器标题', '搜查完成', '搜查安全箱')
        ]
        if states[0] and states[2] and (states[1] or self.round_by_find_area(
            self.last_screenshot, '贝果-局内', '搜查进行中',
        ).is_success):
            return self.round_success('已进入武备箱搜查')
        # 搜查面板上的 F 是全部拾取。只有面板已经不在、局内提示回来，才补按。
        if (
            not any(states)
            and self.last_screenshot_time - self.last_interact_time >= 2
            and all(
                self.round_by_find_area(self.last_screenshot, '贝果-局内', area).is_success
                for area in ('喧响值', '武备箱交互')
            )
        ):
            if self.interact_attempts >= 2:
                return self.round_fail('两次交互后仍未打开武备箱')
            self._press_interact()
            return self.round_wait('武备箱未打开，补按一次交互', wait=0.5)
        return self.round_wait('等待武备箱搜查', wait=0.5)
