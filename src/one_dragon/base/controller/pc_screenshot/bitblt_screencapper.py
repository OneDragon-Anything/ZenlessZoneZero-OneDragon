import ctypes

import cv2
from cv2.typing import MatLike

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.gdi_screencapper_base import (
    CAPTUREBLT,
    SRCCOPY,
    GdiScreencapperBase,
)
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log


class BitBltScreencapperBase(GdiScreencapperBase):
    """BitBlt 截图的基类，封装 CAPTUREBLT 自动回退逻辑"""

    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        """初始化 BitBlt 截图器基类

        Args:
            game_win: 游戏窗口对象
            standard_width: 标准宽度
            standard_height: 标准高度
        """
        GdiScreencapperBase.__init__(self, game_win, standard_width, standard_height)
        self.use_captureblt = True

    def _do_bitblt(self, dest_dc, dest_x, dest_y, width, height,
                   src_dc, src_x, src_y) -> bool:
        """执行 BitBlt 操作，自动处理 CAPTUREBLT 标志

        Args:
            dest_dc: 目标设备上下文
            dest_x: 目标 X 坐标
            dest_y: 目标 Y 坐标
            width: 宽度
            height: 高度
            src_dc: 源设备上下文
            src_x: 源 X 坐标
            src_y: 源 Y 坐标

        Returns:
            是否成功
        """
        blt_flags = SRCCOPY | CAPTUREBLT if self.use_captureblt else SRCCOPY
        result = ctypes.windll.gdi32.BitBlt(
            dest_dc, dest_x, dest_y, width, height,
            src_dc, src_x, src_y, blt_flags
        )

        # 如果使用 CAPTUREBLT 失败，尝试不使用该标志重试
        if not result and self.use_captureblt:
            result = ctypes.windll.gdi32.BitBlt(
                dest_dc, dest_x, dest_y, width, height,
                src_dc, src_x, src_y, SRCCOPY
            )
            if result:
                self.use_captureblt = False

        return result != 0


class BitBltScreencapper(BitBltScreencapperBase):
    """使用 BitBlt API 直接截取窗口的策略"""

    def _do_capture(self, hwnd, width, height, hwndDC, mfcDC) -> bool:
        """使用 BitBlt API 执行截图

        Args:
            hwnd: 窗口句柄
            width: 截图宽度
            height: 截图高度
            hwndDC: 设备上下文
            mfcDC: 内存设备上下文

        Returns:
            是否截图成功
        """
        return self._do_bitblt(mfcDC, 0, 0, width, height, hwndDC, 0, 0)


class BitBltFullscreenScreencapper(BitBltScreencapperBase):
    """使用 BitBlt API 先截取全屏再裁剪到窗口区域的策略

    适用于某些窗口模式下 BitBlt 直接截取效果不佳的情况
    """

    @staticmethod
    def _get_virtual_screen_info() -> tuple[int, int, int, int]:
        """获取虚拟屏幕信息

        Returns:
            (left, top, width, height) 虚拟屏幕的位置和尺寸
        """
        left = ctypes.windll.user32.GetSystemMetrics(76)    # SM_XVIRTUALSCREEN
        top = ctypes.windll.user32.GetSystemMetrics(77)     # SM_YVIRTUALSCREEN
        width = ctypes.windll.user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
        height = ctypes.windll.user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        return left, top, width, height

    def _do_capture(self, hwnd, width, height, hwndDC, mfcDC) -> bool:
        """使用 BitBlt API 执行全屏截图

        Args:
            hwnd: 窗口句柄（0 表示全屏）
            width: 截图宽度
            height: 截图高度
            hwndDC: 设备上下文
            mfcDC: 内存设备上下文

        Returns:
            是否截图成功
        """
        # 获取虚拟屏幕起点作为源偏移量
        src_x, src_y, _, _ = self._get_virtual_screen_info()
        return self._do_bitblt(mfcDC, 0, 0, width, height, hwndDC, src_x, src_y)

    def init(self) -> bool:
        """初始化全屏截图资源

        Returns:
            是否初始化成功
        """
        self.cleanup()

        try:
            # 获取屏幕 DC (0 表示整个屏幕)
            hwndDC = ctypes.windll.user32.GetDC(0)
            if not hwndDC:
                raise Exception('无法获取屏幕设备上下文')

            mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                ctypes.windll.user32.ReleaseDC(0, hwndDC)
                raise Exception('无法创建兼容设备上下文')

            self.hwndDC = hwndDC
            self.mfcDC = mfcDC
            self.hwnd_for_dc = 0  # 全屏模式使用 0
            return True
        except Exception:
            log.debug(f"初始化 {self.__class__.__name__} 失败", exc_info=True)
            self.cleanup()
            return False

    def capture(self, rect: Rect, independent: bool = False) -> MatLike | None:
        """获取全屏截图并裁剪到窗口区域

        Args:
            rect: 截图区域（窗口在屏幕上的坐标）
            independent: 是否独立截图

        Returns:
            截图数组，失败返回 None
        """
        if independent:
            return self._capture_independent(rect)

        # 使用实例级锁保护对共享 GDI 资源的使用
        with self._lock:
            if self.hwndDC is None or self.mfcDC is None:
                if not self.init():
                    return None

            # 获取虚拟屏幕信息（支持多屏，坐标可能为负）
            v_left, v_top, v_width, v_height = self._get_virtual_screen_info()

            screenshot = self._capture_with_retry(0, v_width, v_height)
            if screenshot is None:
                # 如果第一次失败，尝试重新初始化并重试一次
                if not self.init():
                    return None
                screenshot = self._capture_with_retry(0, v_width, v_height)

            if screenshot is None:
                return None

            # 裁剪到窗口区域
            return self._crop_to_window(screenshot, rect, v_left, v_top, v_width, v_height)

    def _crop_to_window(self, fullscreen: MatLike, rect: Rect,
                        virtual_left: int, virtual_top: int,
                        virtual_width: int, virtual_height: int) -> MatLike | None:
        """将全屏截图裁剪到窗口区域

        Args:
            fullscreen: 全屏截图
            rect: 窗口区域（屏幕绝对坐标）
            virtual_left: 虚拟屏幕左上角 X 坐标（可能为负）
            virtual_top: 虚拟屏幕左上角 Y 坐标（可能为负）
            virtual_width: 虚拟屏幕总宽度
            virtual_height: 虚拟屏幕总高度

        Returns:
            裁剪后的截图，失败返回 None
        """
        # 将窗口的绝对坐标转换为虚拟屏幕图像中的相对坐标
        x1 = max(0, min(rect.x1 - virtual_left, virtual_width))
        y1 = max(0, min(rect.y1 - virtual_top, virtual_height))
        x2 = max(0, min(rect.x2 - virtual_left, virtual_width))
        y2 = max(0, min(rect.y2 - virtual_top, virtual_height))

        if x2 <= x1 or y2 <= y1:
            return None

        screenshot = fullscreen[y1:y2, x1:x2]

        if self.game_win.is_win_scale:
            screenshot = cv2.resize(screenshot, (self.standard_width, self.standard_height))

        return screenshot

    def _capture_independent(self, rect: Rect) -> MatLike | None:
        """独立模式全屏截图

        Args:
            rect: 截图区域

        Returns:
            截图数组，失败返回 None
        """
        hwndDC = None
        mfcDC = None
        saveBitMap = None

        try:
            hwndDC = ctypes.windll.user32.GetDC(0)
            if not hwndDC:
                raise Exception('无法获取屏幕设备上下文')

            # 获取虚拟屏幕信息（支持多屏，坐标可能为负）
            v_left, v_top, v_width, v_height = self._get_virtual_screen_info()

            mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                raise Exception('无法创建兼容设备上下文')

            saveBitMap, buffer, bmpinfo_buffer = self._create_bitmap_resources(
                v_width, v_height, hwndDC
            )

            fullscreen = self._capture_window_to_bitmap(
                0, v_width, v_height, hwndDC, mfcDC,
                saveBitMap, buffer, bmpinfo_buffer
            )

            if fullscreen is None:
                return None

            return self._crop_to_window(fullscreen, rect, v_left, v_top, v_width, v_height)

        except Exception:
            log.debug("独立模式全屏截图失败", exc_info=True)
            return None

        finally:
            try:
                if saveBitMap:
                    ctypes.windll.gdi32.DeleteObject(saveBitMap)
                if mfcDC:
                    ctypes.windll.gdi32.DeleteDC(mfcDC)
                if hwndDC:
                    ctypes.windll.user32.ReleaseDC(0, hwndDC)
            except Exception:
                log.debug("独立模式资源释放失败", exc_info=True)
