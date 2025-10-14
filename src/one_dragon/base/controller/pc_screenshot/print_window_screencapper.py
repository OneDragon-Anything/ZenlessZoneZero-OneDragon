import ctypes
from typing import Optional

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect
import threading
from one_dragon.utils.log_utils import log

# WinAPI / GDI constants
PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002
PW_FLAGS = PW_CLIENTONLY | PW_RENDERFULLCONTENT
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0

class PrintWindowScreencapper(ScreencapperBase):
    """
    使用 PrintWindow API 进行截图的策略
    """

    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        ScreencapperBase.__init__(self, game_win, standard_width, standard_height)
        self.hwndDC: Optional[int] = None
        self.mfcDC: Optional[int] = None
        self.saveBitMap: Optional[int] = None
        self.buffer: Optional[ctypes.Array] = None
        self.bmpinfo_buffer: Optional[ctypes.Array] = None
        self.width: int = 0
        self.height: int = 0
        self.hwnd_for_dc: Optional[int] = None  # 保存获取DC时的句柄，用于正确释放DC
        # 保护对共享 GDI 资源的并发访问
        # 使用可重入锁以支持在持锁上下文中安全调用内部方法（capture 已持锁）
        self._lock = threading.RLock()

    def init(self) -> bool:
        """初始化Print Window截图方法，预加载资源"""
        self.cleanup()

        try:
            hwnd = self.game_win.get_hwnd()
            if not hwnd:
                raise Exception('未找到目标窗口，无法初始化Print Window')

            hwndDC = ctypes.windll.user32.GetDC(hwnd)
            if not hwndDC:
                raise Exception('无法获取窗口设备上下文')

            mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
                raise Exception('无法创建兼容设备上下文')

            self.hwndDC = hwndDC
            self.mfcDC = mfcDC
            self.hwnd_for_dc = hwnd
            return True
        except Exception as e:
            log.exception("初始化 PrintWindow 失败: %s", e)
            self.cleanup()
            return False

    def capture(self, rect: Rect, independent: bool = False) -> Optional[MatLike]:
        """
        Print Window 获取窗口截图
        :param rect: 截图区域
        :param independent: 是否独立截图（独立模式不使用实例级共享资源）
        """
        hwnd = self.game_win.get_hwnd()
        if not hwnd:
            return None

        width = rect.width
        height = rect.height

        if width <= 0 or height <= 0:
            return None

        if independent:
            return self._capture_independent(hwnd, width, height)

        # 使用实例级锁保护对共享 GDI 资源的使用（hwndDC / mfcDC / saveBitMap）
        with self._lock:
            if self.hwndDC is None or self.mfcDC is None:
                if not self.init():
                    return None

            screenshot = self._capture_with_retry(hwnd, width, height)
            if screenshot is not None:
                return screenshot

            # 如果第一次失败，尝试重新初始化并重试一次
            if not self.init():
                return None

            return self._capture_with_retry(hwnd, width, height)

    def cleanup(self):
        """
        清理Print Window相关资源
        """
        with self._lock:
            # 如果没有任何资源，直接清理字段并返回
            if not (self.hwndDC or self.mfcDC or self.saveBitMap):
                self.hwndDC = None
                self.mfcDC = None
                self.saveBitMap = None
                self.buffer = None
                self.bmpinfo_buffer = None
                self.width = 0
                self.height = 0
                self.hwnd_for_dc = None
                return

            # 如果位图存在，确保它不是被选中的状态，然后删除
            if self.saveBitMap:
                if self.mfcDC and getattr(self, "_selected_prev", None) is not None:
                    try:
                        ctypes.windll.gdi32.SelectObject(self.mfcDC, self._selected_prev)
                    except Exception:
                        log.exception("cleanup: 恢复原始对象失败")
                    finally:
                        self._selected_prev = None

                try:
                    ctypes.windll.gdi32.DeleteObject(self.saveBitMap)
                except Exception:
                    log.exception("删除 saveBitMap 失败")

            # 删除兼容 DC
            if self.mfcDC:
                try:
                    ctypes.windll.gdi32.DeleteDC(self.mfcDC)
                except Exception:
                    log.exception("删除 mfcDC 失败")

            # 释放窗口 DC
            if self.hwndDC and self.hwnd_for_dc:
                try:
                    ctypes.windll.user32.ReleaseDC(self.hwnd_for_dc, self.hwndDC)
                except Exception:
                    log.exception("ReleaseDC 失败")

            # 清空字段
            self.hwndDC = None
            self.mfcDC = None
            self.saveBitMap = None
            self.buffer = None
            self.bmpinfo_buffer = None
            self.width = 0
            self.height = 0
            self.hwnd_for_dc = None

    def _capture_with_retry(self, hwnd, width, height) -> Optional[MatLike]:
        """
        尝试执行一次截图操作
        """
        needs_create = (self.saveBitMap is None
                        or self.width != width
                        or self.height != height)
        if needs_create:
            # 短临界区：只在创建/替换位图资源时持锁，使用双重检查模式
            with self._lock:
                if (self.saveBitMap is None
                        or self.width != width
                        or self.height != height):
                    # 如果我们有旧的 saveBitMap，确保它没有被选入 DC 后再删除
                    if self.saveBitMap:
                        if self.mfcDC and getattr(self, "_selected_prev", None) is not None:
                            try:
                                ctypes.windll.gdi32.SelectObject(self.mfcDC, self._selected_prev)
                            except Exception:
                                log.exception("替换位图前恢复原始对象失败")
                            finally:
                                self._selected_prev = None
                        try:
                            ctypes.windll.gdi32.DeleteObject(self.saveBitMap)
                        except Exception:
                            log.exception("删除旧 saveBitMap 失败")

                    try:
                        saveBitMap, buffer, bmpinfo_buffer = self._create_bitmap_resources(width, height)
                    except Exception as e:
                        log.exception("创建位图资源失败: %s", e)
                        return None

                    self.saveBitMap = saveBitMap
                    self.buffer = buffer
                    self.bmpinfo_buffer = bmpinfo_buffer
                    self.width = width
                    self.height = height

        return self._capture_window_to_bitmap(hwnd, width, height,
                                              self.hwndDC, self.mfcDC, self.saveBitMap,
                                              self.buffer, self.bmpinfo_buffer)

    def _capture_independent(self, hwnd, width, height) -> Optional[MatLike]:
        """
        独立模式Print Window截图，自管理资源
        """
        hwndDC = None
        mfcDC = None
        saveBitMap = None

        try:
            hwndDC = ctypes.windll.user32.GetDC(hwnd)
            if not hwndDC:
                raise Exception('无法获取窗口设备上下文')

            mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                raise Exception('无法创建兼容设备上下文')

            saveBitMap, buffer, bmpinfo_buffer = self._create_bitmap_resources(width, height, hwndDC)

            return self._capture_window_to_bitmap(hwnd, width, height, hwndDC, mfcDC,
                                                  saveBitMap, buffer, bmpinfo_buffer)
        except Exception as e:
            log.exception("独立模式截图失败: %s", e)
            return None
        finally:
            try:
                if saveBitMap:
                    ctypes.windll.gdi32.DeleteObject(saveBitMap)
                if mfcDC:
                    ctypes.windll.gdi32.DeleteDC(mfcDC)
                if hwndDC:
                    ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
            except Exception:
                # 释放时尽量不要抛出
                log.exception("独立模式资源释放失败")

    def _create_bitmap_resources(self, width, height, dc_handle=None):
        """
        创建位图相关资源
        """
        if dc_handle is None:
            dc_handle = self.hwndDC

        saveBitMap = ctypes.windll.gdi32.CreateCompatibleBitmap(dc_handle, width, height)
        if not saveBitMap:
            raise Exception('无法创建兼容位图')

        buffer_size = width * height * 4
        buffer = ctypes.create_string_buffer(buffer_size)

        bmpinfo_buffer = self._create_bmpinfo_buffer(width, height)

        return saveBitMap, buffer, bmpinfo_buffer

    def _create_bmpinfo_buffer(self, width, height):
        """
        创建位图信息结构
        """
        bmpinfo_buffer = ctypes.create_string_buffer(40)
        ctypes.c_uint32.from_address(ctypes.addressof(bmpinfo_buffer)).value = 40
        ctypes.c_int32.from_address(ctypes.addressof(bmpinfo_buffer) + 4).value = width
        ctypes.c_int32.from_address(ctypes.addressof(bmpinfo_buffer) + 8).value = -height
        ctypes.c_uint16.from_address(ctypes.addressof(bmpinfo_buffer) + 12).value = 1
        ctypes.c_uint16.from_address(ctypes.addressof(bmpinfo_buffer) + 14).value = 32
        ctypes.c_uint32.from_address(ctypes.addressof(bmpinfo_buffer) + 16).value = 0
        return bmpinfo_buffer

    def _capture_window_to_bitmap(self, hwnd, width, height,
                                  hwndDC, mfcDC, saveBitMap,
                                  buffer, bmpinfo_buffer) -> Optional[MatLike]:
        """
        执行窗口截图的核心逻辑。
        要点：
         - 在 SelectObject 时保存原始对象并在结束时恢复，避免位图被持续选入 DC 导致 DeleteObject 失败。
         - 使用与位图关联的 DC 调用 GetDIBits（mfcDC）。
        """
        if not all([hwndDC, mfcDC, saveBitMap, buffer, bmpinfo_buffer]):
            log.error("无效参数传入 _capture_window_to_bitmap")
            return None

        prev_obj = None
        try:
            prev_obj = ctypes.windll.gdi32.SelectObject(mfcDC, saveBitMap)
            # 记录被替换前的对象，便于在需要时安全恢复（例如在替换/删除位图前）
            try:
                with self._lock:
                    self._selected_prev = prev_obj
            except Exception:
                # 记录但不终止流程
                log.exception("记录选中前对象句柄失败")
            # 使用命名常量（仅使用 PrintWindow，不回退 BitBlt）
            result = ctypes.windll.user32.PrintWindow(hwnd, mfcDC, PW_FLAGS)
            if not result:
                log.error("PrintWindow 调用失败: hwnd=%s", hwnd)
                return None

            # 注意：GetDIBits 的第一个参数应为位图所关联的 DC（mfcDC）
            lines = ctypes.windll.gdi32.GetDIBits(mfcDC, saveBitMap,
                                                  0, height, buffer,
                                                  bmpinfo_buffer, DIB_RGB_COLORS)
            if lines != height:
                log.error("GetDIBits 返回行数不匹配: %s != %s", lines, height)
                return None

            img_array = np.frombuffer(buffer, dtype=np.uint8).reshape((height, width, 4))
            screenshot = cv2.cvtColor(img_array, cv2.COLOR_BGRA2RGB)

            if self.game_win.is_win_scale:
                screenshot = cv2.resize(screenshot, (self.standard_width, self.standard_height))

            return screenshot
        except Exception as e:
            log.exception("从位图构建截图失败: %s", e)
            return None
        finally:
            try:
                if prev_obj is not None:
                    ctypes.windll.gdi32.SelectObject(mfcDC, prev_obj)
            except Exception:
                # 恢复失败也不要抛出
                log.exception("恢复原始 DC 对象失败")
            # 清理实例级记录
            try:
                with self._lock:
                    self._selected_prev = None
            except Exception:
                log.exception("清理 _selected_prev 失败")
