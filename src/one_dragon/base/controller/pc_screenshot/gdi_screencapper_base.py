import ctypes
import threading

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log


class GdiScreencapperBase(ScreencapperBase):
    """
    GDI 截图方法的抽象基类
    封装 DC、位图等资源的管理逻辑
    """

    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        ScreencapperBase.__init__(self, game_win, standard_width, standard_height)
        self.mfcDC: int | None = None
        self.saveBitMap: int | None = None
        self.buffer: ctypes.c_void_p | None = None
        self.bmpinfo_buffer: ctypes.Array | None = None
        self.width: int = 0
        self.height: int = 0
        self._lock = threading.RLock()

    def init(self) -> bool:
        """初始化 GDI 截图方法，预加载资源

        Returns:
            是否初始化成功
        """
        self.cleanup()

        try:
            # 使用屏幕 DC 来创建兼容 DC，这样可以避免窗口跨屏幕移动导致 DC 不兼容的问题
            # 同时也解决了共享模式下 mfcDC 与实时获取的 hwndDC 可能不匹配的问题
            temp_dc = ctypes.windll.user32.GetDC(0)
            if not temp_dc:
                raise Exception('无法获取屏幕设备上下文')

            try:
                mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(temp_dc)
                if not mfcDC:
                    raise Exception('无法创建兼容设备上下文')

                self.mfcDC = mfcDC
                return True
            finally:
                # 立即释放临时 DC
                ctypes.windll.user32.ReleaseDC(0, temp_dc)
        except Exception:
            log.debug(f"初始化 {self.__class__.__name__} 失败", exc_info=True)
            self.cleanup()
            return False

    def cleanup(self):
        """清理 GDI 相关资源"""
        with self._lock:
            # 如果没有任何资源，直接清理字段并返回
            if not (self.mfcDC or self.saveBitMap):
                self._clear_fields()
                return

            # 删除位图
            if self.saveBitMap:
                try:
                    ctypes.windll.gdi32.DeleteObject(self.saveBitMap)
                except Exception:
                    log.debug("删除 saveBitMap 失败", exc_info=True)

            # 删除兼容 DC
            if self.mfcDC:
                try:
                    ctypes.windll.gdi32.DeleteDC(self.mfcDC)
                except Exception:
                    log.debug("删除 mfcDC 失败", exc_info=True)

            self._clear_fields()

    def _clear_fields(self):
        """清空所有字段"""
        self.mfcDC = None
        self.saveBitMap = None
        self.buffer = None
        self.bmpinfo_buffer = None
        self.width = 0
        self.height = 0

    def _capture_shared(self, hwnd_for_dc: int, width: int, height: int) -> MatLike | None:
        """使用共享资源进行截图的通用流程

        Args:
            hwnd_for_dc: 用于获取 DC 的窗口句柄 (0 表示屏幕)
            width: 截图宽度
            height: 截图高度

        Returns:
            截图结果
        """
        with self._lock:
            if self.mfcDC is None and not self.init():
                return None

            hwndDC = ctypes.windll.user32.GetDC(hwnd_for_dc)
            if not hwndDC:
                return None

            try:
                return self._capture_with_retry(hwnd_for_dc, width, height, hwndDC)
            finally:
                try:
                    ctypes.windll.user32.ReleaseDC(hwnd_for_dc, hwndDC)
                except Exception:
                    log.debug("ReleaseDC 失败", exc_info=True)

    def _capture_with_retry(self, hwnd, width, height, hwndDC) -> MatLike | None:
        """尝试执行截图操作，失败时自动重新初始化 mfcDC 并重试一次

        Args:
            hwnd: 窗口句柄
            width: 截图宽度
            height: 截图高度
            hwndDC: 窗口设备上下文

        Returns:
            截图数组，失败返回 None
        """
        # 检查是否需要重新创建位图资源
        if (self.saveBitMap is None or self.width != width or self.height != height):
            recreate_success = self._recreate_bitmap_resources(width, height, hwndDC)
            if not recreate_success:
                return None

        # 第一次尝试截图
        screenshot = self._capture_and_convert_bitmap(
            hwnd, width, height,
            hwndDC, self.mfcDC, self.saveBitMap,
            self.buffer, self.bmpinfo_buffer
        )

        if screenshot is not None:
            return screenshot

        # 如果失败，尝试重新初始化 mfcDC 并重试
        if not self.init():
            return None

        # 重新初始化后重建位图资源
        recreate_success = self._recreate_bitmap_resources(width, height, hwndDC)
        if not recreate_success:
            return None

        return self._capture_and_convert_bitmap(
            hwnd, width, height,
            hwndDC, self.mfcDC, self.saveBitMap,
            self.buffer, self.bmpinfo_buffer
        )

    def _recreate_bitmap_resources(self, width, height, hwndDC) -> bool:
        """重新创建位图资源

        Args:
            width: 位图宽度
            height: 位图高度
            hwndDC: 窗口设备上下文

        Returns:
            是否创建成功
        """
        # 删除旧位图
        if self.saveBitMap:
            try:
                ctypes.windll.gdi32.DeleteObject(self.saveBitMap)
            except Exception:
                log.debug("删除旧 saveBitMap 失败", exc_info=True)

        # 使用屏幕 DC 创建位图，确保与 mfcDC (也是基于屏幕 DC 创建) 兼容
        # 避免因为 hwndDC 与 mfcDC 不兼容导致 SelectObject 失败
        screen_dc = ctypes.windll.user32.GetDC(0)
        if not screen_dc:
            log.error("无法获取屏幕 DC")
            return False

        try:
            saveBitMap, buffer, bmpinfo_buffer = self._create_bitmap_resources(width, height, screen_dc)
        except Exception as e:
            log.debug("创建位图资源失败: %s", e, exc_info=True)
            return False
        finally:
            ctypes.windll.user32.ReleaseDC(0, screen_dc)

        self.saveBitMap = saveBitMap
        self.buffer = buffer
        self.bmpinfo_buffer = bmpinfo_buffer
        self.width = width
        self.height = height
        return True

    def _create_bitmap_resources(self, width, height, dc_handle):
        """创建位图相关资源

        Args:
            width: 位图宽度
            height: 位图高度
            dc_handle: 设备上下文句柄

        Returns:
            (saveBitMap, buffer, bmpinfo_buffer) 元组
        """
        # 创建位图信息结构
        bmpinfo_buffer = ctypes.create_string_buffer(40)
        ctypes.c_uint32.from_address(ctypes.addressof(bmpinfo_buffer)).value = 40
        ctypes.c_int32.from_address(ctypes.addressof(bmpinfo_buffer) + 4).value = width
        ctypes.c_int32.from_address(ctypes.addressof(bmpinfo_buffer) + 8).value = -height
        ctypes.c_uint16.from_address(ctypes.addressof(bmpinfo_buffer) + 12).value = 1
        ctypes.c_uint16.from_address(ctypes.addressof(bmpinfo_buffer) + 14).value = 32
        ctypes.c_uint32.from_address(ctypes.addressof(bmpinfo_buffer) + 16).value = 0

        pBits = ctypes.c_void_p()

        # DIB_RGB_COLORS = 0
        saveBitMap = ctypes.windll.gdi32.CreateDIBSection(
            dc_handle,
            bmpinfo_buffer,
            0,
            ctypes.byref(pBits),
            0,
            0
        )

        if not saveBitMap:
            raise Exception('无法创建 DIBSection')

        return saveBitMap, pBits, bmpinfo_buffer

    def _capture_and_convert_bitmap(self, hwnd, width, height,
                                    hwndDC, mfcDC, saveBitMap,
                                    buffer, bmpinfo_buffer) -> MatLike | None:
        """执行截图并转换为数组

        Args:
            hwnd: 窗口句柄
            width: 截图宽度
            height: 截图高度
            hwndDC: 窗口设备上下文
            mfcDC: 内存设备上下文
            saveBitMap: 位图句柄
            buffer: 数据缓冲区指针
            bmpinfo_buffer: 位图信息缓冲区

        Returns:
            截图数组，失败返回 None
        """
        if not all([hwndDC, mfcDC, saveBitMap, buffer, bmpinfo_buffer]):
            return None

        prev_obj = None
        try:
            prev_obj = ctypes.windll.gdi32.SelectObject(mfcDC, saveBitMap)

            # 调用具体的截图方法（由子类实现）
            if not self._do_capture(hwnd, width, height, hwndDC, mfcDC):
                return None

            # 直接从内存构建 numpy 数组
            size = width * height * 4
            array_type = ctypes.c_ubyte * size
            buffer_array = ctypes.cast(buffer, ctypes.POINTER(array_type)).contents

            img_array = np.frombuffer(buffer_array, dtype=np.uint8).reshape((height, width, 4))
            screenshot = cv2.cvtColor(img_array, cv2.COLOR_BGRA2RGB)

            if self.game_win.is_win_scale:
                screenshot = cv2.resize(screenshot, (self.standard_width, self.standard_height))

            return screenshot
        except Exception:
            log.debug("从位图构建截图失败", exc_info=True)
            return None
        finally:
            try:
                if prev_obj is not None:
                    ctypes.windll.gdi32.SelectObject(mfcDC, prev_obj)
            except Exception:
                log.debug("恢复原始 DC 对象失败", exc_info=True)

    def capture(self, rect: Rect, independent: bool = False) -> MatLike | None:
        """获取全屏截图并裁剪到窗口区域

        Args:
            rect: 截图区域（窗口在屏幕上的坐标）
            independent: 是否独立截图

        Returns:
            截图数组，失败返回 None
        """
        raise NotImplementedError("子类必须实现 capture 方法")

    def _do_capture(self, hwnd, width, height, hwndDC, mfcDC) -> bool:
        """执行具体的截图操作
        Args:
            hwnd: 窗口句柄
            width: 截图宽度
            height: 截图高度
            hwndDC: 窗口设备上下文
            mfcDC: 内存设备上下文

        Returns:
            是否截图成功
        """
        raise NotImplementedError("子类必须实现 _do_capture 方法")

    def _capture_independent(self, hwnd_for_dc: int, width: int, height: int) -> MatLike | None:
        """独立模式截图，自管理资源

        Args:
            hwnd_for_dc: 用于获取 DC 的窗口句柄 (0 表示屏幕)
            width: 截图宽度
            height: 截图高度

        Returns:
            截图数组，失败返回 None
        """
        hwndDC = None
        mfcDC = None
        saveBitMap = None

        try:
            hwndDC = ctypes.windll.user32.GetDC(hwnd_for_dc)
            if not hwndDC:
                raise Exception('无法获取设备上下文')

            mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                raise Exception('无法创建兼容设备上下文')

            saveBitMap, buffer, bmpinfo_buffer = self._create_bitmap_resources(width, height, hwndDC)

            return self._capture_and_convert_bitmap(hwnd_for_dc, width, height, hwndDC, mfcDC,
                                                    saveBitMap, buffer, bmpinfo_buffer)
        except Exception:
            log.debug("独立模式截图失败", exc_info=True)
            return None
        finally:
            try:
                if saveBitMap:
                    ctypes.windll.gdi32.DeleteObject(saveBitMap)
                if mfcDC:
                    ctypes.windll.gdi32.DeleteDC(mfcDC)
                if hwndDC:
                    ctypes.windll.user32.ReleaseDC(hwnd_for_dc, hwndDC)
            except Exception:
                log.debug("独立模式资源释放失败", exc_info=True)
