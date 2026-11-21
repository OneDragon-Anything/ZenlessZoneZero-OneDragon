import sys

import cv2
from cv2.typing import MatLike

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.pil_screencapper import PilScreencapper
from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.envs.env_config import ScreenshotMethodEnum
from one_dragon.utils.log_utils import log

if sys.platform == 'win32':
    from one_dragon.base.controller.pc_screenshot.bitblt_screencapper import (
        BitBltScreencapper,
    )
    from one_dragon.base.controller.pc_screenshot.print_window_screencapper import (
        PrintWindowScreencapper,
    )
elif sys.platform == 'darwin':
    import Quartz


class PcScreenshotController:
    """
    截图控制器
    使用策略模式管理不同的截图方法
    """

    def __init__(
        self, game_win: PcGameWindow, standard_width: int, standard_height: int
    ):
        self.game_win: PcGameWindow = game_win
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height

        self.strategies: dict[str, ScreencapperBase] = {
            ScreenshotMethodEnum.PIL.value.value: PilScreencapper(
                game_win, standard_width, standard_height
            ),
        }
        if sys.platform == 'win32':
            self.strategies.update({
                ScreenshotMethodEnum.PRINT_WINDOW.value.value: PrintWindowScreencapper(
                    game_win, standard_width, standard_height
                ),
                ScreenshotMethodEnum.BITBLT.value.value: BitBltScreencapper(
                    game_win, standard_width, standard_height
                ),
            })
        self.active_strategy_name: str | None = None
        self._mac_screenshot_permission_warning_logged: bool = False

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

        if sys.platform == 'darwin':
            if not Quartz.CGPreflightScreenCaptureAccess():
                if not self._mac_screenshot_permission_warning_logged:
                    log.error(
                        'macOS 当前运行的一条龙进程没有屏幕录制权限；'
                        '请在“系统设置 → 隐私权与安全性 → 屏幕与系统录音”中授权实际运行程序'
                    )
                    self._mac_screenshot_permission_warning_logged = True
                return None
            self._mac_screenshot_permission_warning_logged = False

        rect: Rect = self.game_win.win_rect
        if rect is None or rect.width <= 0 or rect.height <= 0:
            return None

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

                if result.ndim == 3 and result.shape[2] == 4:
                    result = cv2.cvtColor(result, cv2.COLOR_RGBA2RGB)

                if not independent and self.active_strategy_name != method_name:
                    self.active_strategy_name = method_name

                if resize and (
                    result.shape[1] != self.standard_width
                    or result.shape[0] != self.standard_height
                ):
                    result = cv2.resize(result, (self.standard_width, self.standard_height))

                return result

            except Exception:
                continue
        if sys.platform == 'darwin':
            log.error('macOS 截图失败，请在“系统设置 → 隐私与安全性 → 屏幕录制”中授权')
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
        ] if sys.platform == 'win32' else [ScreenshotMethodEnum.PIL.value.value]

        if method == ScreenshotMethodEnum.AUTO.value.value or method not in self.strategies:
            return default_priority.copy()

        priority_list = [method]

        for m in default_priority:
            if m not in priority_list:
                priority_list.append(m)

        return priority_list
