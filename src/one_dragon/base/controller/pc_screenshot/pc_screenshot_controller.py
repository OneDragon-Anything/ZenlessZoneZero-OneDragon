from typing import Optional, Dict

from cv2.typing import MatLike

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.mss_screencapper import MssScreencapper
from one_dragon.base.controller.pc_screenshot.pil_screencapper import PilScreencapper
from one_dragon.base.controller.pc_screenshot.print_window_screencapper import PrintWindowScreencapper
from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log


class PcScreenshotController:
    """
    截图控制器
    使用策略模式管理不同的截图方法
    """

    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        self.game_win: PcGameWindow = game_win
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height

        self.strategies: Dict[str, ScreencapperBase] = {
            "print_window": PrintWindowScreencapper(game_win, standard_width, standard_height),
            "mss": MssScreencapper(game_win, standard_width, standard_height),
            "pil": PilScreencapper(game_win, standard_width, standard_height)
        }
        self.active_strategy_name: Optional[str] = None

    def get_screenshot(self, independent: bool = False) -> Optional[MatLike]:
        """
        根据初始化的方法获取截图
        :param independent: 是否独立截图（不进行初始化，使用临时的截图器）
        :return: 截图数组
        """
        if not self.active_strategy_name and not independent:
            log.error('截图方法尚未初始化，请先调用 init_screenshot()')
            return None

        rect: Rect = self.game_win.win_rect
        if rect is None:
            return None

        if independent:
            # 独立模式，按默认优先级尝试，不依赖已初始化的实例
            methods_to_try_names = self._get_method_priority_list("auto")
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
                return result

            except Exception:
                continue
        log.error("所有截图方法都失败了")
        return None

    def init_screenshot(self, method: str) -> Optional[str]:
        """
        初始化截图方法，带有回退机制
        :param method: 首选的截图方法 ("auto", "print_window", "mss", "pil")
        """
        self.cleanup_resources()

        methods_to_try = self._get_method_priority_list(method)

        for attempt_method in methods_to_try:
            strategy = self.strategies.get(attempt_method)
            if strategy and strategy.init():
                self.active_strategy_name = attempt_method
                if attempt_method != method:
                    log.debug(f"截图方法 '{method}' 初始化失败，回退到 '{attempt_method}'")
                else:
                    log.debug(f"截图方法 '{attempt_method}' 初始化成功")
                return attempt_method

        log.error(f"所有截图方法初始化都失败了，尝试的方法: {methods_to_try}")
        self.active_strategy_name = None
        return None

    def cleanup_resources(self):
        """
        清理所有截图策略的资源
        """
        for strategy in self.strategies.values():
            strategy.cleanup()
        self.active_strategy_name = None

    def cleanup(self):
        """
        清理资源
        """
        self.cleanup_resources()

    def _get_method_priority_list(self, method: str) -> list:
        """
        获取截图方法的优先级列表
        :param method: 首选方法 ("auto", "print_window", "mss", "pil")
        :return: 方法名称列表，按优先级排序
        """
        fallback_order = {
            "auto": ["print_window", "mss", "pil"],
            "print_window": ["print_window", "mss", "pil"],
            "mss": ["mss", "print_window", "pil"],
            "pil": ["pil", "print_window", "mss"]
        }

        return fallback_order.get(method, ["print_window", "mss", "pil"])
