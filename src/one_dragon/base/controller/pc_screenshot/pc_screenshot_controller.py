from __future__ import annotations

import threading
import time

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.bitblt_screencapper import (
    BitBltScreencapper,
)
from one_dragon.base.controller.pc_screenshot.pil_screencapper import PilScreencapper
from one_dragon.base.controller.pc_screenshot.print_window_screencapper import (
    PrintWindowScreencapper,
)
from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.envs.env_config import ScreenshotMethodEnum
from one_dragon.utils.log_utils import log


class PcScreenshotController:
    """
    截图控制器
    使用策略模式管理不同的截图方法
    """

    #: 缓存窗口（秒）：游戏约 30 帧，每帧约 33 毫秒，窗口内重复索取直接返缓存。
    #: 索取侧多快都不会超过这个产出速度，10 个线程同时要图也只截一次。
    SCREENSHOT_CACHE_SECONDS: float = 1.0 / 30.0

    def __init__(
        self, game_win: PcGameWindow, standard_width: int, standard_height: int
    ):
        self.game_win: PcGameWindow = game_win
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height

        self.strategies: dict[str, ScreencapperBase] = {
            ScreenshotMethodEnum.PRINT_WINDOW.value.value: PrintWindowScreencapper(game_win, standard_width, standard_height),
            ScreenshotMethodEnum.BITBLT.value.value: BitBltScreencapper(game_win, standard_width, standard_height),
            ScreenshotMethodEnum.PIL.value.value: PilScreencapper(game_win, standard_width, standard_height),
        }
        self.active_strategy_name: str | None = None
        self._cache_lock: threading.Lock = threading.Lock()
        """截图缓存锁：多线程同时要图时，窗口内只截一次，其余等锁后命中缓存。"""
        self._cache: dict[tuple[bool, bool, int, int, int, int], tuple[float, MatLike]] = {}
        """截图缓存：键为（独立模式，是否缩放，窗口矩形），值为（截取时刻，成图）。
        独立与主线分开存，两边取屏方法不同，不串味。成图设只读，
        调用方全是读（裁剪、识别、写盘），原地改图会直接报错，不悄悄污染。"""

    def get_screenshot(self, independent: bool = False, resize: bool = True) -> MatLike | None:
        """根据初始化的方法获取截图

        Args:
            independent: 是否独立截图（不进行初始化，使用临时的截图器）
            resize: 是否缩放到标准分辨率

        Returns:
            截图数组，失败返回 None
        """
        if not self.active_strategy_name and not independent:
            log.error("截图方法尚未初始化，请先调用 init_screenshot()")
            return None

        rect: Rect = self.game_win.win_rect
        if rect is None or rect.width <= 0 or rect.height <= 0:
            return None

        cache_key: tuple[bool, bool, int, int, int, int] = (
            independent, resize, rect.x1, rect.y1, rect.width, rect.height,
        )
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                cached_at, cached_image = cached
                if time.monotonic() - cached_at < self.SCREENSHOT_CACHE_SECONDS:
                    # 窗口内命中：直接返只读引用，不拷贝。调用方全是读，
                    # 原地改图会直接报错。外层时间戳照常打新时间，
                    # 窗口内本来就是同一帧。
                    return cached_image
            # 锁内截：10 个线程同时到也只截一次，后到的等锁后直接命中。
            result = self._capture(rect, independent, resize)
            if result is not None:
                if isinstance(result, np.ndarray):
                    result.setflags(write=False)
                self._cache[cache_key] = (time.monotonic(), result)
                return result
            return None

    def _capture(self, rect: Rect, independent: bool, resize: bool) -> MatLike | None:
        """真正走取屏策略截一张图；缓存未命中时才调。"""
        if independent:
            # 独立模式，按默认优先级尝试，不依赖已初始化的实例
            methods_to_try_names = self._get_method_priority_list(ScreenshotMethodEnum.AUTO.value.value)
        else:
            # 从已激活的策略开始尝试
            methods_to_try_names = self._get_method_priority_list(self.active_strategy_name)

        for method_name in methods_to_try_names:
            try:
                strategy = self.strategies.get(method_name)
                if not strategy:
                    continue

                result = strategy.capture(rect, independent)
                if result is None:
                    continue

                if not independent and self.active_strategy_name != method_name:
                    self.active_strategy_name = method_name

                if resize and self.game_win.is_win_scale:
                    result = cv2.resize(result, (self.standard_width, self.standard_height))

                return result

            except Exception:
                continue
        return None

    def init_screenshot(self, method: str) -> str | None:
        """初始化截图方法，带有回退机制

        Args:
            method: 首选的截图方法

        Returns:
            成功初始化的方法名称，全部失败返回 None
        """
        # 如果请求的方法与当前活动策略相同，跳过重新初始化
        if (
            self.active_strategy_name is not None
            and method != ScreenshotMethodEnum.AUTO.value.value
            and method == self.active_strategy_name
        ):
            return self.active_strategy_name

        self.cleanup_resources()

        methods_to_try = self._get_method_priority_list(method)

        for attempt_method in methods_to_try:
            strategy = self.strategies.get(attempt_method)
            if strategy and strategy.init():
                self.active_strategy_name = attempt_method
                return attempt_method

        self.active_strategy_name = None
        return None

    def cleanup_resources(self):
        """清理所有截图策略的资源"""
        for strategy in self.strategies.values():
            strategy.cleanup()
        self.active_strategy_name = None

    def cleanup(self):
        """清理资源"""
        self.cleanup_resources()

    def _get_method_priority_list(self, method: str) -> list:
        """获取截图方法的优先级列表

        Args:
            method: 首选方法

        Returns:
            方法名称列表，按优先级排序
        """
        default_priority = [
            ScreenshotMethodEnum.PRINT_WINDOW.value.value,
            ScreenshotMethodEnum.BITBLT.value.value,
            ScreenshotMethodEnum.PIL.value.value,
        ]

        if method == ScreenshotMethodEnum.AUTO.value.value or method not in self.strategies:
            return default_priority.copy()

        priority_list = [method]

        for m in default_priority:
            if m not in priority_list:
                priority_list.append(m)

        return priority_list
