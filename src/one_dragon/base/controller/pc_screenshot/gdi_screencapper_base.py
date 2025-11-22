import ctypes
import threading
from dataclasses import dataclass

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log


@dataclass
class GdiCaptureContext:
    """GDI 截图上下文，包含截图所需的参数和资源"""

    hwnd: int
    width: int
    height: int
    src_x: int = 0
    src_y: int = 0
    hwndDC: int = 0
    mfcDC: int = 0
    saveBitMap: int = 0
    buffer: ctypes.c_void_p = None
    bmpinfo_buffer: ctypes.Array = None


class GdiScreencapperBase(ScreencapperBase):
    """
    GDI 截图方法的抽象基类
    封装 DC、位图等资源的管理逻辑
    """

    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        ScreencapperBase.__init__(self, game_win, standard_width, standard_height)
        self.ctx = GdiCaptureContext(hwnd=0, width=0, height=0)
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

                self.ctx.mfcDC = mfcDC
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
            if not (self.ctx.mfcDC or self.ctx.saveBitMap):
                self._clear_fields()
                return

            # 删除位图
            if self.ctx.saveBitMap:
                try:
                    ctypes.windll.gdi32.DeleteObject(self.ctx.saveBitMap)
                except Exception:
                    log.debug("删除 saveBitMap 失败", exc_info=True)

            # 删除兼容 DC
            if self.ctx.mfcDC:
                try:
                    ctypes.windll.gdi32.DeleteDC(self.ctx.mfcDC)
                except Exception:
                    log.debug("删除 mfcDC 失败", exc_info=True)

            self._clear_fields()

    def _clear_fields(self):
        """清空所有字段"""
        self.ctx.mfcDC = 0
        self.ctx.saveBitMap = 0
        self.ctx.buffer = None
        self.ctx.bmpinfo_buffer = None
        self.ctx.width = 0
        self.ctx.height = 0

    def _capture_shared(
        self, hwnd: int, width: int, height: int, src_x: int = 0, src_y: int = 0
    ) -> MatLike | None:
        """使用共享资源进行截图的通用流程

        Args:
            hwnd: 用于获取 DC 的窗口句柄 (0 表示屏幕)
            width: 截图宽度
            height: 截图高度
            src_x: 源区域左上角 X 坐标
            src_y: 源区域左上角 Y 坐标

        Returns:
            截图结果
        """
        with self._lock:
            if self.ctx.mfcDC == 0 and not self.init():
                return None

            hwndDC = ctypes.windll.user32.GetDC(hwnd)
            if not hwndDC:
                return None

            try:
                # 更新 context 中的临时参数
                self.ctx.hwnd = hwnd
                self.ctx.hwndDC = hwndDC
                self.ctx.src_x = src_x
                self.ctx.src_y = src_y

                # 检查是否需要重新创建位图资源
                if (
                    self.ctx.saveBitMap == 0
                    or self.ctx.width != width
                    or self.ctx.height != height
                ):
                    recreate_success = self._recreate_bitmap_resources(width, height)
                    if not recreate_success:
                        return None

                return self._capture_with_retry(width, height)
            finally:
                try:
                    ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
                except Exception:
                    log.debug("ReleaseDC 失败", exc_info=True)

    def _capture_with_retry(self, width: int, height: int) -> MatLike | None:
        """尝试执行截图操作，失败时自动重新初始化 mfcDC 并重试一次

        Args:
            width: 请求的截图宽度
            height: 请求的截图高度

        Returns:
            截图数组，失败返回 None
        """
        # 第一次尝试截图
        screenshot = self._capture_and_convert_bitmap(self.ctx)

        if screenshot is not None:
            return screenshot

        # 如果失败，尝试重新初始化 mfcDC 并重试
        if not self.init():
            return None

        # 重新初始化后重建位图资源
        recreate_success = self._recreate_bitmap_resources(width, height)
        if not recreate_success:
            return None

        return self._capture_and_convert_bitmap(self.ctx)

    def _recreate_bitmap_resources(self, width, height) -> bool:
        """重新创建位图资源

        Args:
            width: 位图宽度
            height: 位图高度
            hwndDC: 窗口设备上下文

        Returns:
            是否创建成功
        """
        # 删除旧位图
        if self.ctx.saveBitMap:
            try:
                ctypes.windll.gdi32.DeleteObject(self.ctx.saveBitMap)
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

        self.ctx.saveBitMap = saveBitMap
        self.ctx.buffer = buffer
        self.ctx.bmpinfo_buffer = bmpinfo_buffer
        self.ctx.width = width
        self.ctx.height = height
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
            dc_handle, bmpinfo_buffer, 0, ctypes.byref(pBits), 0, 0
        )

        if not saveBitMap:
            raise Exception('无法创建 DIBSection')

        return saveBitMap, pBits, bmpinfo_buffer

    def _capture_and_convert_bitmap(self, ctx: GdiCaptureContext) -> MatLike | None:
        """执行截图并转换为数组

        Args:
            ctx: 截图上下文

        Returns:
            截图数组，失败返回 None
        """
        if not all(
            [
                ctx.hwndDC,
                ctx.mfcDC,
                ctx.saveBitMap,
                ctx.buffer,
                ctx.bmpinfo_buffer,
            ]
        ):
            return None

        prev_obj = None
        try:
            prev_obj = ctypes.windll.gdi32.SelectObject(ctx.mfcDC, ctx.saveBitMap)

            # 调用具体的截图方法（由子类实现）
            if not self._do_capture(ctx):
                return None

            # 直接从内存构建 numpy 数组
            size = ctx.width * ctx.height * 4
            array_type = ctypes.c_ubyte * size
            buffer_array = ctypes.cast(ctx.buffer, ctypes.POINTER(array_type)).contents

            img_array = np.frombuffer(buffer_array, dtype=np.uint8).reshape((ctx.height, ctx.width, 4))
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
                    ctypes.windll.gdi32.SelectObject(ctx.mfcDC, prev_obj)
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

    def _do_capture(self, context: GdiCaptureContext) -> bool:
        """执行具体的截图操作
        Args:
            context: 截图上下文

        Returns:
            是否截图成功
        """
        raise NotImplementedError("子类必须实现 _do_capture 方法")

    def _capture_independent(
        self, hwnd: int, width: int, height: int, src_x: int = 0, src_y: int = 0
    ) -> MatLike | None:
        """独立模式截图，自管理资源

        Args:
            hwnd: 用于获取 DC 的窗口句柄 (0 表示屏幕)
            width: 截图宽度
            height: 截图高度
            src_x: 源区域左上角 X 坐标
            src_y: 源区域左上角 Y 坐标

        Returns:
            截图数组，失败返回 None
        """
        hwndDC = None
        mfcDC = None
        saveBitMap = None

        try:
            hwndDC = ctypes.windll.user32.GetDC(hwnd)
            if not hwndDC:
                raise Exception('无法获取设备上下文')

            mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                raise Exception('无法创建兼容设备上下文')

            saveBitMap, buffer, bmpinfo_buffer = self._create_bitmap_resources(width, height, hwndDC)

            ctx = GdiCaptureContext(
                hwnd=hwnd,
                width=width,
                height=height,
                src_x=src_x,
                src_y=src_y,
                hwndDC=hwndDC,
                mfcDC=mfcDC,
                saveBitMap=saveBitMap,
                buffer=buffer,
                bmpinfo_buffer=bmpinfo_buffer,
            )

            return self._capture_and_convert_bitmap(ctx)
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
                    ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
            except Exception:
                log.debug("独立模式资源释放失败", exc_info=True)
