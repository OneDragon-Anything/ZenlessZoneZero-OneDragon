from dataclasses import dataclass
from typing import ClassVar

import cv2
import numpy as np
import pyautogui
from cv2.typing import MatLike
from pygetwindow import Win32Window

from one_dragon.base.controller.pc_controller_base import PcControllerBase
from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.print_window_screencapper import (
    PrintWindowScreencapper,
)
from one_dragon.utils.log_utils import log


@dataclass(frozen=True)
class CloudGameWindowProbeResult:
    """云游戏窗口候选的截图探测结果。"""

    hwnd: int
    non_black_ratio: float
    contrast: float
    score: float
    is_valid: bool


class CloudGameWindowSelector:
    """从多个同名云游戏窗口中选择能够正常渲染画面的窗口。"""

    NON_BLACK_GRAY_THRESHOLD: ClassVar[int] = 8
    MIN_NON_BLACK_RATIO: ClassVar[float] = 0.01

    def __init__(self, controller: PcControllerBase) -> None:
        """初始化云游戏窗口选择器。

        Args:
            controller: 当前云游戏使用的 PC 控制器。
        """
        self.controller: PcControllerBase = controller
        self._confirmed_hwnd: int | None = None
        self._probe_game_win: PcGameWindow = PcGameWindow(
            controller.standard_width,
            controller.standard_height,
        )
        self._probe_screencapper: PrintWindowScreencapper = PrintWindowScreencapper(
            self._probe_game_win,
            controller.standard_width,
            controller.standard_height,
        )

    def select_window(self) -> int | None:
        """选择当前应由云游戏操作使用的窗口句柄。

        Returns:
            唯一候选或画面评分最高的有效候选句柄；没有有效候选时返回 None。
        """
        windows = self._get_exact_title_windows()
        candidate_hwnds = [int(window._hWnd) for window in windows]

        if len(candidate_hwnds) == 0:
            self._confirmed_hwnd = None
            log.warning(
                '未找到标题完全匹配的云游戏窗口 标题=%s',
                self.controller.game_win.win_title,
            )
            return None

        if len(candidate_hwnds) == 1:
            selected_hwnd = candidate_hwnds[0]
            self._confirmed_hwnd = selected_hwnd
            log.info('云游戏窗口只有一个候选，直接使用 HWND=%s', selected_hwnd)
            return selected_hwnd

        cached_probe: CloudGameWindowProbeResult | None = None
        confirmed_hwnd = self._confirmed_hwnd
        if (
            confirmed_hwnd is not None
            and self._can_reuse_confirmed_window(candidate_hwnds)
        ):
            cached_probe = self._probe_window(confirmed_hwnd)
            self._log_probe_result(cached_probe)
            if cached_probe.is_valid:
                log.info('复用已确认的云游戏窗口 HWND=%s', cached_probe.hwnd)
                return cached_probe.hwnd
            log.warning('已确认的云游戏窗口画面失效，重新探测全部候选')

        probe_results: list[CloudGameWindowProbeResult] = []
        for hwnd in candidate_hwnds:
            if cached_probe is not None and hwnd == cached_probe.hwnd:
                probe_results.append(cached_probe)
                continue
            probe_result = self._probe_window(hwnd)
            probe_results.append(probe_result)
            self._log_probe_result(probe_result)

        valid_results = [result for result in probe_results if result.is_valid]
        if len(valid_results) == 0:
            self._confirmed_hwnd = None
            self._log_all_candidates_invalid(probe_results)
            return None

        selected_result = max(valid_results, key=lambda result: result.score)
        self._confirmed_hwnd = selected_result.hwnd
        log.info(
            '选中云游戏窗口 HWND=%s 有效像素比例=%.2f%% 对比度=%.2f 得分=%.4f',
            selected_result.hwnd,
            selected_result.non_black_ratio * 100,
            selected_result.contrast,
            selected_result.score,
        )
        return selected_result.hwnd

    def _get_exact_title_windows(self) -> list[Win32Window]:
        """枚举标题与 controller 当前标题完全一致的窗口。

        Returns:
            标题完全一致的窗口列表；枚举失败时返回空列表。
        """
        win_title = self.controller.game_win.win_title
        if win_title is None:
            return []

        try:
            windows = pyautogui.getWindowsWithTitle(win_title)
        except Exception:
            log.error('枚举云游戏窗口失败 标题=%s', win_title, exc_info=True)
            return []
        return [window for window in windows if window.title == win_title]

    def _can_reuse_confirmed_window(self, candidate_hwnds: list[int]) -> bool:
        """判断已确认句柄是否仍可进入快速复用探测。

        Args:
            candidate_hwnds: 当前标题完全匹配的候选句柄。

        Returns:
            句柄仍在候选中且正式 controller 未被替换时返回 True。
        """
        if (
            self._confirmed_hwnd is None
            or self._confirmed_hwnd not in candidate_hwnds
        ):
            return False

        current_hwnd = self._get_controller_cached_hwnd()
        if current_hwnd == self._confirmed_hwnd:
            return True

        log.info(
            '正式 controller 的 HWND 已变化 原=%s 当前=%s，重新探测全部候选',
            self._confirmed_hwnd,
            current_hwnd,
        )
        return False

    def _get_controller_cached_hwnd(self) -> int | None:
        """读取正式窗口对象已经缓存的 HWND，不触发自动枚举。

        Returns:
            controller 当前缓存的 HWND；尚未缓存或句柄不可转换时返回 None。
        """
        cached_hwnd = getattr(self.controller.game_win, '_hWnd', None)
        if cached_hwnd is None:
            return None
        try:
            return int(cached_hwnd)
        except (TypeError, ValueError):
            return None

    def _probe_window(self, hwnd: int) -> CloudGameWindowProbeResult:
        """使用固定 PrintWindow 截图并计算候选画面质量。

        Args:
            hwnd: 待探测的窗口句柄。

        Returns:
            包含有效像素比例、对比度、得分与有效性的探测结果。
        """
        screenshot = self._capture_window(hwnd)
        if screenshot is None or screenshot.size == 0:
            return CloudGameWindowProbeResult(hwnd, 0, 0, 0, False)

        gray = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
        non_black_ratio = float(
            np.count_nonzero(gray > self.NON_BLACK_GRAY_THRESHOLD) / gray.size
        )
        contrast = float(np.std(gray))
        score = non_black_ratio + contrast / 255.0
        return CloudGameWindowProbeResult(
            hwnd=hwnd,
            non_black_ratio=non_black_ratio,
            contrast=contrast,
            score=score,
            is_valid=non_black_ratio >= self.MIN_NON_BLACK_RATIO,
        )

    def _capture_window(self, hwnd: int) -> MatLike | None:
        """使用临时窗口对象和独立模式 PrintWindow 截取候选。

        Args:
            hwnd: 待截图的窗口句柄。

        Returns:
            RGB 截图；窗口信息或截图获取失败时返回 None。
        """
        try:
            self._probe_game_win.update_hwnd(hwnd)
            rect = self._probe_game_win.win_rect
            if rect is None:
                return None
            return self._probe_screencapper.capture(rect, independent=True)
        except Exception:
            log.error('探测云游戏窗口截图失败 HWND=%s', hwnd, exc_info=True)
            return None

    def _log_probe_result(self, result: CloudGameWindowProbeResult) -> None:
        """记录单个候选的画面质量指标。

        Args:
            result: 候选窗口探测结果。
        """
        log.info(
            '云游戏窗口探测 HWND=%s 有效像素比例=%.2f%% 对比度=%.2f '
            '得分=%.4f 有效=%s',
            result.hwnd,
            result.non_black_ratio * 100,
            result.contrast,
            result.score,
            result.is_valid,
        )

    def _log_all_candidates_invalid(
        self,
        results: list[CloudGameWindowProbeResult],
    ) -> None:
        """记录全部候选均无效时的完整评分摘要。

        Args:
            results: 本轮所有候选窗口的探测结果。
        """
        summary = '; '.join(
            f'HWND={result.hwnd} '
            f'有效像素比例={result.non_black_ratio * 100:.2f}% '
            f'对比度={result.contrast:.2f} 得分={result.score:.4f}'
            for result in results
        )
        log.warning('所有云游戏窗口候选均无有效画面 %s', summary)
