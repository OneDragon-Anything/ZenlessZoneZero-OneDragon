import time
from typing import ClassVar

from one_dragon.base.controller.pc_controller_base import PcControllerBase
from one_dragon.base.operation.operation_base import OperationBase
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.cloud_game_window_selector import (
    CloudGameWindowSelector,
)
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame


class ZOperationMixin:
    """绝区零操作通用能力。"""

    CLOUD_GAME_NOT_ENTERED_AREA_LIST: list[tuple[str, str]] = [
        ('云游戏', '国服PC云-点击空白区域关闭'),
        ('云游戏', '国服PC云-排队中'),
        ('云游戏', '国服PC云-开始游戏'),
        ('云游戏', '国服PC云-邦邦点快速队列'),
        ('云游戏', '国服PC云-普通队列'),
        ('云游戏', '国服PC云-切换窗口'),
        ('打开游戏', '点击进入游戏'),
    ]

    _ctx: ZContext
    _op_to_enter_game: OperationBase | None
    CLOUD_WINDOW_CHECK_TIMEOUT_SECONDS: ClassVar[float] = 10
    _cloud_window_selector: CloudGameWindowSelector | None = None
    _cloud_window_check_started_at: float | None = None
    _cloud_window_check_execution: float | None = None

    @property
    def ctx(self) -> ZContext:
        return self._ctx

    @ctx.setter
    def ctx(self, value: ZContext) -> None:
        self._ctx = value

    @property
    def op_to_enter_game(self) -> OperationBase:
        if self._op_to_enter_game is None:
            self._op_to_enter_game = OpenAndEnterGame(self.ctx)
        return self._op_to_enter_game

    @op_to_enter_game.setter
    def op_to_enter_game(self, value: OperationBase | None) -> None:
        self._op_to_enter_game = value

    def check_game_initialized(self) -> OperationRoundResult:
        """检查游戏是否完成初始化，云游戏未进入时视为未就绪。"""
        if not self.ctx.game_account_config.is_cloud_game:
            return self.round_success()

        controller = self.ctx.controller
        selected_hwnd: int | None = None
        if isinstance(controller, PcControllerBase):
            if (
                self._cloud_window_selector is None
                or self._cloud_window_selector.controller is not controller
            ):
                self._cloud_window_selector = CloudGameWindowSelector(controller)
                self._cloud_window_check_started_at = None
            if self._cloud_window_check_execution != self.operation_start_time:
                self._cloud_window_check_execution = self.operation_start_time
                self._cloud_window_check_started_at = None
            selected_hwnd = self._cloud_window_selector.select_window()
            if selected_hwnd is None:
                return self._cloud_window_check_failure()
            controller.set_window_hwnd(selected_hwnd)

        screen = self.screenshot()
        if isinstance(controller, PcControllerBase) and selected_hwnd is not None:
            probe = CloudGameWindowSelector.evaluate_screenshot(selected_hwnd, screen)
            if not probe.is_valid:
                return self._cloud_window_check_failure()
            self._cloud_window_check_started_at = None
        for screen_name, area_name in self.CLOUD_GAME_NOT_ENTERED_AREA_LIST:
            result = self.round_by_find_area(screen, screen_name, area_name)
            if result.is_success:
                return self.round_fail(result.status)

        return self.round_success()

    def _cloud_window_check_failure(self) -> OperationRoundResult:
        """等待有效云游戏画面，连续失败 10 秒后转入进入游戏流程。"""
        now = time.monotonic()
        if self._cloud_window_check_started_at is None:
            self._cloud_window_check_started_at = now
        if now - self._cloud_window_check_started_at >= self.CLOUD_WINDOW_CHECK_TIMEOUT_SECONDS:
            self._cloud_window_check_started_at = None
            return self.round_fail('未找到有效云游戏窗口')
        return self.round_wait('等待有效云游戏窗口', wait=1)
