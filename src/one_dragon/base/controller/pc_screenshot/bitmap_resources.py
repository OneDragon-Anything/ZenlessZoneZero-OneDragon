import ctypes
from typing import Optional, Tuple
import numpy as np
import cv2
from cv2.typing import MatLike

# 常量
DIB_RGB_COLORS = 0
BI_RGB = 0
SRCCOPY = 0x00CC0020


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", ctypes.c_uint32 * 3),
    ]


class BitmapResourceMixin:
    """
    Mixin 提供位图资源创建与缓冲区转换工具。

    设计要点：
      - 对像素缓冲区使用 CreateDIBSection（ctypes），以减少不必要的内存拷贝。
      - 不负责释放 DC 或位图句柄；调用方须负责调用 DeleteObject / DeleteDC / ReleaseDC。
      - 不做并发控制；在并发场景下，调用方应在外部加锁。
    """

    def _create_bmpinfo_buffer(self, width: int, height: int) -> BITMAPINFO:
        """
        创建并返回用于 GetDIBits 的 BITMAPINFO（32bpp, top-down）。

        返回值：
          - BITMAPINFO 实例（调用方需保持对象存活直到不再调用 GetDIBits）
        """
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = int(width)
        bmi.bmiHeader.biHeight = -int(height)  # top-down DIB，方便直接按行读取
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bmi.bmiHeader.biSizeImage = 0
        bmi.bmiHeader.biXPelsPerMeter = 0
        bmi.bmiHeader.biYPelsPerMeter = 0
        bmi.bmiHeader.biClrUsed = 0
        bmi.bmiHeader.biClrImportant = 0
        return bmi

    def _create_bitmap_resources(self, width: int, height: int, hwndDC: Optional[int] = None) -> Tuple[int, ctypes.Array, BITMAPINFO]:
        """
        使用 CreateDIBSection 创建 HBITMAP 并返回 (hBitmap, buffer_array, bmi)。

        参数:
          - width, height: 位图尺寸（像素）
          - hwndDC: 可选 DC 句柄，CreateDIBSection 的 hdc 参数（可为 0）

        返回:
          - saveBitMap: HBITMAP 句柄
          - buffer: ctypes 字节数组（size = width * height * 4），直接映射到位图像素内存
          - bmpinfo_buffer: BITMAPINFO 实例，用于 GetDIBits
        抛出:
          - 在创建失败时抛出 Exception
        """
        bmi = self._create_bmpinfo_buffer(width, height)

        ppvBits = ctypes.c_void_p()
        hdc_val = int(hwndDC) if hwndDC else 0

        hBitmap = ctypes.windll.gdi32.CreateDIBSection(
            hdc_val,
            ctypes.byref(bmi),
            DIB_RGB_COLORS,
            ctypes.byref(ppvBits),
            None,
            0
        )
        if not hBitmap:
            raise Exception("CreateDIBSection 失败")

        if not ppvBits.value:
            # 清理已创建对象再抛出异常
            try:
                ctypes.windll.gdi32.DeleteObject(hBitmap)
            except Exception:
                pass
            raise Exception("CreateDIBSection 未返回像素指针")

        size = int(width) * int(height) * 4
        buffer = (ctypes.c_ubyte * size).from_address(ppvBits.value)

        return hBitmap, buffer, bmi

    def _release_bitmap_resources(self, saveBitMap: Optional[int], mfcDC: Optional[int] = None) -> None:
        """
        辅助释放位图资源（DeleteObject/DeleteDC）。遇到异常时尽量忽略以便在 finally 中安全调用。
        注意：调用方仍需负责 ReleaseDC(hwnd, hwndDC)（如果适用）。
        """
        try:
            if saveBitMap:
                ctypes.windll.gdi32.DeleteObject(int(saveBitMap))
        except Exception:
            pass
        try:
            if mfcDC:
                ctypes.windll.gdi32.DeleteDC(int(mfcDC))
        except Exception:
            pass

    def buffer_to_ndarray(self, buffer: ctypes.Array, width: int, height: int) -> np.ndarray:
        """
        将 ctypes 字节缓冲区转换为 numpy ndarray (height, width, 4)，dtype=uint8。

        不改变像素的排列（调用方负责颜色空间转换，例如 BGRA->RGB）。
        """
        size = int(width) * int(height) * 4
        arr = np.ctypeslib.as_array(buffer)
        if arr.size != size:
            raise ValueError("buffer 大小与宽高不匹配")
        img = arr.reshape((height, width, 4))
        return img

    def _capture_bitmap_to_image(
        self,
        hwnd: int,
        width: int,
        height: int,
        hwndDC: int,
        mfcDC: int,
        saveBitMap: int,
        buffer: ctypes.Array,
        bmpinfo_buffer: BITMAPINFO,
        *,
        use_printwindow: bool = True,
        pw_flags: int = 0x00000003,
        is_win_scale: bool = False,
        standard_width: int = 0,
        standard_height: int = 0
    ) -> Optional[MatLike]:
        """
        从已准备好的 DC/位图执行截图（PrintWindow 或 BitBlt），并返回 OpenCV 可用的 RGB ndarray。

        参数说明见注释。返回 None 表示失败。
        """
        if not all([hwndDC, mfcDC, saveBitMap, buffer, bmpinfo_buffer]):
            return None

        prev_obj = None
        try:
            prev_obj = ctypes.windll.gdi32.SelectObject(int(mfcDC), int(saveBitMap))
            # 使用 PrintWindow 或 BitBlt 获取像素到兼容 DC 中的位图
            if use_printwindow:
                result = ctypes.windll.user32.PrintWindow(int(hwnd), int(mfcDC), int(pw_flags))
                if not result:
                    return None
            else:
                res = ctypes.windll.gdi32.BitBlt(int(mfcDC), 0, 0, int(width), int(height), int(hwndDC), 0, 0, SRCCOPY)
                if not res:
                    return None

            # 将位图内容写入 buffer（GetDIBits）
            lines = ctypes.windll.gdi32.GetDIBits(
                int(mfcDC),
                int(saveBitMap),
                0,
                int(height),
                ctypes.cast(buffer, ctypes.c_void_p),
                ctypes.byref(bmpinfo_buffer),
                DIB_RGB_COLORS
            )
            if lines != int(height):
                return None

            img_array = self.buffer_to_ndarray(buffer, width, height)
            screenshot = cv2.cvtColor(img_array, cv2.COLOR_BGRA2RGB)

            if is_win_scale and standard_width and standard_height:
                screenshot = cv2.resize(screenshot, (standard_width, standard_height))

            return screenshot
        except Exception:
            return None
        finally:
            try:
                if prev_obj is not None:
                    ctypes.windll.gdi32.SelectObject(int(mfcDC), int(prev_obj))
            except Exception:
                pass