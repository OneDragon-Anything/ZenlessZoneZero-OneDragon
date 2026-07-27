import copy
import time
from typing import ClassVar

from cv2.typing import MatLike

from one_dragon.base.controller.pc_controller_base import PcControllerBase
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.cloud_game_window_selector import (
    CloudGameWindowSelector,
)
from zzz_od.operation.zzz_operation import ZOperation


class CloudGameQueue(ZOperation):
    """
    云游戏排队操作类
    """

    WINDOW_PROBE_TIMEOUT_SECONDS: ClassVar[float] = 10

    def __init__(self, ctx: ZContext) -> None:
        """初始化云游戏排队操作。

        Args:
            ctx: 绝区零运行上下文。
        """
        ZOperation.__init__(
            self, ctx, op_name=gt("云游戏排队"), need_check_game_win=False
        )
        self._window_selector: CloudGameWindowSelector | None = None
        self._window_selector_controller: PcControllerBase | None = None
        self._window_probe_failure_since: float | None = None

    def handle_init(self) -> None:
        """重置本次执行的连续窗口探测失败计时。"""
        self._window_probe_failure_since = None

    def screenshot(self) -> MatLike | None:
        """为云游戏 PC controller 选择正确 HWND 后统一截图。

        Returns:
            controller 获取到的截图；没有有效云游戏窗口或截图失败时返回 None。
        """
        controller = self.ctx.controller
        if not isinstance(controller, PcControllerBase):
            self._window_probe_failure_since = None
            return super().screenshot()

        selector = self._get_window_selector(controller)
        selected_hwnd = selector.select_window()
        if selected_hwnd is None:
            self.last_screenshot_time = time.time()
            self.last_screenshot = None
            return None

        controller.set_window_hwnd(selected_hwnd)
        screenshot = super().screenshot()
        if screenshot is not None:
            self._window_probe_failure_since = None
        else:
            log.warning('已选中云游戏窗口但常规截图失败 HWND=%s', selected_hwnd)
        return screenshot

    def _execute_one_round(self) -> OperationRoundResult:
        """在 PC 云游戏节点执行前拦截无效截图并应用超时策略。

        Returns:
            正常节点结果，或等待有效窗口、窗口探测超时的结果。
        """
        current_node = self._current_node
        if (
            not isinstance(self.ctx.controller, PcControllerBase)
            or current_node is None
            or not current_node.screenshot_before_round
        ):
            return super()._execute_one_round()

        screenshot = self.screenshot()
        if screenshot is None:
            return self._window_probe_failure_result()

        node_without_screenshot = copy.copy(current_node)
        node_without_screenshot.screenshot_before_round = False
        self._current_node = node_without_screenshot
        try:
            return super()._execute_one_round()
        finally:
            self._current_node = current_node

    def _get_window_selector(
        self,
        controller: PcControllerBase,
    ) -> CloudGameWindowSelector:
        """获取与当前 controller 绑定的窗口选择器。

        Args:
            controller: 当前上下文中的 PC controller。

        Returns:
            可复用的云游戏窗口选择器。
        """
        if (
            self._window_selector is None
            or self._window_selector_controller is not controller
        ):
            self._window_selector = CloudGameWindowSelector(controller)
            self._window_selector_controller = controller
        return self._window_selector

    def _window_probe_failure_result(self) -> OperationRoundResult:
        """根据连续截图失败时长返回等待或明确失败。

        Returns:
            连续失败不足 10 秒时返回等待，达到 10 秒时返回失败。
        """
        now = time.monotonic()
        if self._window_probe_failure_since is None:
            self._window_probe_failure_since = now

        failure_seconds = now - self._window_probe_failure_since
        if failure_seconds >= self.WINDOW_PROBE_TIMEOUT_SECONDS:
            return self.round_fail(status='未找到有效云游戏窗口')
        return self.round_wait(status='等待有效云游戏窗口', wait=1)

    @node_from(from_name="画面识别", status="国服PC云-点击空白区域关闭")
    @operation_node(name="画面识别", node_max_retry_times=60, is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        result = self.round_by_find_area(
            self.last_screenshot, "云游戏", "国服PC云-切换窗口"
        )
        if result.is_fail:
            return self.round_retry(status="未知画面", wait=1)

        result = self.round_by_find_and_click_area(
            self.last_screenshot, "云游戏", "国服PC云-点击空白区域关闭"
        )
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_area(
            self.last_screenshot, "云游戏", "国服PC云-排队中"
        )
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_and_click_area(
            self.last_screenshot, "云游戏", "国服PC云-开始游戏"
        )
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_area(
            self.last_screenshot, "打开游戏", "点击进入游戏"
        )
        if result.is_success:
            return self.round_success(result.status)

        return self.round_retry(status="未知画面", wait=1)

    @node_from(from_name="画面识别", status="国服PC云-开始游戏")
    @operation_node(name="国服PC云-插队或排队", node_max_retry_times=10)
    def cn_pc_cloud_start_or_queue(self) -> OperationRoundResult:
        """
        国服PC云-插队或排队
        :return:
        """
        screen = self.last_screenshot
        enter_game_result = self.round_by_find_area(
            screen, "打开游戏", "点击进入游戏"
        )
        if enter_game_result.is_success:
            return self.round_success(status=enter_game_result.status, wait=1)

        result_bang = self.round_by_find_area(
            screen, "云游戏", "国服PC云-邦邦点快速队列"
        )
        result_exit = self.round_by_find_area(screen, "云游戏", "国服PC云-排队中")
        if result_bang.is_success:
            if self.ctx.game_account_config.prefer_bangbang_points:
                result = self.round_by_find_and_click_area(
                    screen, "云游戏", "国服PC云-邦邦点快速队列"
                )
                if result.is_success:
                    return self.round_success(result.status)
            else:
                result = self.round_by_find_and_click_area(
                    screen, "云游戏", "国服PC云-普通队列"
                )
                if result.is_success:
                    return self.round_success(result.status)
        elif result_exit.is_success:
            return self.round_success(result_exit.status, wait=1)

        return self.round_retry(status="未知画面", wait=1)

    @node_from(from_name="国服PC云-插队或排队", status="国服PC云-排队中")
    @node_from(from_name="国服PC云-插队或排队", status="国服PC云-邦邦点快速队列")
    @node_from(from_name="国服PC云-插队或排队", status="国服PC云-普通队列")
    @node_from(from_name="画面识别", status="国服PC云-排队中")
    @node_from(from_name="国服PC云-排队中转", status="排队中转")
    @operation_node(name="国服PC云-排队")
    def cn_pc_cloud_queue(self) -> OperationRoundResult:
        """
        国服PC云-排队
        :return:
        """
        # OCR识别"国服PC云-排队人数"区域的值
        queue_count_area = self.ctx.screen_loader.get_area(
            "云游戏", "国服PC云-排队人数"
        )
        queue_count_part = cv2_utils.crop_image_only(
            self.last_screenshot, queue_count_area.rect
        )
        queue_count_text = self.ctx.ocr.run_ocr_single_line(
            queue_count_part, strict_one_line=False
        )

        # OCR识别"国服PC云-预计等待时间"区域的值
        wait_time_area = self.ctx.screen_loader.get_area(
            "云游戏", "国服PC云-预计等待时间"
        )
        wait_time_part = cv2_utils.crop_image_only(
            self.last_screenshot, wait_time_area.rect
        )
        wait_time_text = self.ctx.ocr.run_ocr_single_line(
            wait_time_part, strict_one_line=False
        )

        log.info(
            f"国服PC云排队信息 - 排队人数: {queue_count_text}, 预计等待时间: {wait_time_text}分钟"
        )

        enter_game_result = self.round_by_find_area(
            self.last_screenshot, "打开游戏", "点击进入游戏"
        )
        if enter_game_result.is_success:
            return self.round_success(status="点击进入游戏", wait=1)
        else:
            return self.round_wait(status="等待排队", wait=5)

    @node_from(from_name="国服PC云-排队", status="等待排队")
    @operation_node(name="国服PC云-排队中转")
    def cn_pc_cloud_queue_transfer(self) -> OperationRoundResult:
        """
        国服PC云-排队中转节点
        :return:
        """
        return self.round_wait(status="排队中转")
