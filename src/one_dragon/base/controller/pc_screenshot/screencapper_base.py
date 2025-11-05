from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.geometry.rectangle import Rect


class ScreencapperBase:
    """截图方法的抽象基类"""

    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        self.game_win: PcGameWindow = game_win
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height

    def init(self) -> bool:
        """初始化截图器

        Returns:
            是否初始化成功
        """
        raise NotImplementedError

    def capture(self, rect: Rect, independent: bool = False) -> Optional[MatLike]:
        """执行截图

        Args:
            rect: 截图区域
            independent: 是否独立截图

        Returns:
            截图图像，失败返回 None
        """
        raise NotImplementedError

    def cleanup(self):
        """清理截图器使用的资源"""
        raise NotImplementedError
