from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.gdi_screencapper_base import GdiScreencapperBase
from one_dragon.base.geometry.rectangle import Rect

# WinAPI / GDI constants
PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002
PW_FLAGS = PW_CLIENTONLY | PW_RENDERFULLCONTENT

class PrintWindowScreencapper(GdiScreencapperBase):
    """
    使用 PrintWindow API 进行截图的策略
    """
    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        GdiScreencapperBase.__init__(self, game_win, standard_width, standard_height)
        self._init_name = "PrintWindow"

    def capture(self, rect: Rect, independent: bool = False) -> Optional[MatLike]:
        return self.capture_common(rect, independent, use_printwindow=True, pw_flags=PW_FLAGS, retry=True)
