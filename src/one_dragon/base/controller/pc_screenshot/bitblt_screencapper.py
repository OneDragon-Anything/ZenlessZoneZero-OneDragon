from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.gdi_screencapper_base import GdiScreencapperBase
from one_dragon.base.geometry.rectangle import Rect

class BitBltScreencapper(GdiScreencapperBase):
    """
    使用 BitBlt + GetDIBits 的截图实现。
    与 PrintWindowScreencapper 保持一致的接口。
    """
    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        GdiScreencapperBase.__init__(self, game_win, standard_width, standard_height)
        self._init_name = "BitBlt"

    def capture(self, rect: Rect, independent: bool = False) -> Optional[MatLike]:
        return self.capture_common(rect, independent, use_printwindow=False, pw_flags=None, retry=False)
