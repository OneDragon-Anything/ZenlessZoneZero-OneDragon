import cv2
import ctypes
import numpy as np
import pyautogui
import time

from concurrent.futures import ThreadPoolExecutor
from cv2.typing import MatLike
from mss.base import MSSBase
from PIL.Image import Image
from typing import Optional

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import thread_utils
from one_dragon.utils.log_utils import log

SCREENSHOT_EXECUTOR = ThreadPoolExecutor(thread_name_prefix='screenshot', max_workers=1)


class PcScreenshot:
    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        self.game_win: PcGameWindow = game_win
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height
        self.initialized_method: Optional[str] = None

        # MSS 实例
        self.mss_instance: Optional[MSSBase] = None

        # Print Window 资源
        self.print_window_hwndDC: Optional[int] = None
        self.print_window_mfcDC: Optional[int] = None
        self.print_window_saveBitMap: Optional[int] = None
        self.print_window_buffer: Optional[ctypes.Array] = None
        self.print_window_bmpinfo_buffer: Optional[ctypes.Array] = None
        self.print_window_width: int = 0
        self.print_window_height: int = 0

    def get_screenshot(self, independent: bool = False) -> MatLike | None:
        """
        根据初始化的方法获取截图
        :param independent: 是否独立截图（不进行初始化）
        :return: 截图数组
        """
        if not self.initialized_method and not independent:
            log.error('截图方法尚未初始化，请先调用 init_screenshot()')
            return None

        rect: Rect = self.game_win.win_rect
        if rect is None:
            return None

        if self.initialized_method == "mss":
            return self.get_screenshot_mss(rect, independent)
        elif self.initialized_method == "print_window":
            return self.get_screenshot_print_window(rect, independent)
        else:  # 独立截图
            result = self.get_screenshot_print_window(rect, independent)
            if result is None:
                return self.get_screenshot_mss(rect, independent)
            return result

    def async_init_screenshot(self, method: str):
        """
        异步初始化截图方法
        :param method: 首选的截图方法 ("mss", "print_window", "auto")
        """
        f = SCREENSHOT_EXECUTOR.submit(self._init_screenshot_with_wait, method)
        f.add_done_callback(thread_utils.handle_future_result)

    def _init_screenshot_with_wait(self, method: str):
        """
        等待窗口准备好再初始化截图
        :param method: 首选的截图方法
        :return: 初始化结果
        """
        check_interval: float = 0.5
        while True:
            if self.game_win.is_win_valid:
                break
            time.sleep(check_interval)

        return self.init_screenshot(method)

    def init_screenshot(self, method: str):
        """
        初始化截图方法，带有回退机制
        :param method: 首选的截图方法 ("mss", "print_window", "auto")
        """
        # 定义方法优先级
        fallback_order = {
            "mss": ["mss", "print_window"],
            "print_window": ["print_window", "mss"],
            "auto": ["print_window", "mss"]
        }

        methods_to_try = fallback_order.get(method, ["print_window", "mss"])

        for attempt_method in methods_to_try:
            success = False

            if attempt_method == "mss":
                success = self.init_mss()
            elif attempt_method == "print_window":
                success = self.init_print_window()

            if success:
                self.initialized_method = attempt_method
                if attempt_method != method:
                    log.info(f"截图方法 '{method}' 初始化失败，回退到 '{attempt_method}'")
                else:
                    log.debug(f"截图方法 '{attempt_method}' 初始化成功")
                return attempt_method

        log.error(f"所有截图方法初始化都失败了，尝试的方法: {methods_to_try}")
        return None

    def init_mss(self):
        """初始化MSS截图方法"""
        if self.mss_instance is not None:
            try:
                self.mss_instance.close()
            except Exception:
                pass
            self.mss_instance = None

        try:
            from mss import mss
            self.mss_instance = mss()
            return True
        except Exception as e:
            log.debug(f'MSS初始化失败: {str(e)}')
            return False

    def init_print_window(self):
        """初始化Print Window截图方法，预加载资源"""
        try:
            hwnd = self.game_win.get_hwnd()
            if not hwnd:
                raise Exception('未找到目标窗口，无法初始化Print Window')

            # 获取窗口设备上下文
            hwndDC = ctypes.windll.user32.GetWindowDC(hwnd)
            if not hwndDC:
                raise Exception('无法获取窗口设备上下文')

            # 创建兼容的设备上下文
            mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
                raise Exception('无法创建兼容设备上下文')

            # 保存预加载的基础资源
            self.print_window_hwndDC = hwndDC
            self.print_window_mfcDC = mfcDC
            # 窗口大小相关的资源将在实际截图时创建
            self.print_window_saveBitMap = None
            self.print_window_buffer = None
            self.print_window_bmpinfo_buffer = None
            self.print_window_width = 0
            self.print_window_height = 0

            self.initialized_method = 'print_window'
            return True

        except Exception as e:
            log.debug(f'Print Window 截图方法初始化失败: {e}')
            return False

    def get_screenshot_mss(self, rect: Rect, independent: bool = False) -> MatLike | None:
        """
        截图 如果分辨率和默认不一样则进行缩放
        :return: 截图
        """
        before_screenshot_time = time.time()

        left = rect.x1
        top = rect.y1
        width = rect.width
        height = rect.height

        if self.mss_instance is not None:
            monitor = {"top": top, "left": left, "width": width, "height": height}
            try:
                if independent:
                    from mss import mss
                    with mss() as mss_instance:
                        screenshot = cv2.cvtColor(np.array(mss_instance.grab(monitor)), cv2.COLOR_BGRA2RGB)
                else:
                    screenshot = cv2.cvtColor(np.array(self.mss_instance.grab(monitor)), cv2.COLOR_BGRA2RGB)
            except Exception:
                if not independent:
                    # 重新初始化MSS实例
                    if self.init_mss():
                        try:
                            screenshot = cv2.cvtColor(np.array(self.mss_instance.grab(monitor)), cv2.COLOR_BGRA2RGB)
                        except Exception:
                            pass
        else:
            img: Image = pyautogui.screenshot(region=(left, top, width, height))
            screenshot = np.array(img)

        if self.game_win.is_win_scale:
            result = cv2.resize(screenshot, (self.standard_width, self.standard_height))
        else:
            result = screenshot

        after_screenshot_time = time.time()
        log.debug(f"MSS 截图耗时:{after_screenshot_time - before_screenshot_time}")
        return result

    def get_screenshot_print_window(self, rect: Rect, independent: bool = False) -> MatLike | None:
        """
        Print Window 获取窗口截图
        :param independent: 是否独立截图
        """
        before_screenshot_time = time.time()

        hwnd = self.game_win.get_hwnd()
        if not hwnd:
            log.warning('未找到目标窗口，无法截图')
            return None

        width = rect.width
        height = rect.height

        if width <= 0 or height <= 0:
            log.warning(f'窗口大小无效: {width}x{height}')
            return None

        # 如果是独立模式，使用独立的资源管理
        if independent:
            return self._get_screenshot_print_window_independent(hwnd, width, height, before_screenshot_time)

        # 使用预加载的基础资源，动态创建窗口大小相关的资源
        try:
            # 检查是否需要重新创建窗口大小相关的资源
            if (self.print_window_saveBitMap is None or
                self.print_window_width != width or
                self.print_window_height != height):

                # 清理旧的窗口大小相关资源
                if self.print_window_saveBitMap:
                    ctypes.windll.gdi32.DeleteObject(self.print_window_saveBitMap)

                # 创建新的位图资源
                saveBitMap, buffer, bmpinfo_buffer = self._create_bitmap_resources(width, height)

                # 保存新的资源
                self.print_window_saveBitMap = saveBitMap
                self.print_window_buffer = buffer
                self.print_window_bmpinfo_buffer = bmpinfo_buffer
                self.print_window_width = width
                self.print_window_height = height

            # 执行截图
            return self._capture_window_to_bitmap(hwnd, width, height,
                                                  self.print_window_hwndDC,
                                                  self.print_window_mfcDC,
                                                  self.print_window_saveBitMap,
                                                  self.print_window_buffer,
                                                  self.print_window_bmpinfo_buffer,
                                                  before_screenshot_time)

        except Exception as e:
            log.debug(f'Print Window截图失败: {e}')
            # 回退到独立模式
            return self._get_screenshot_print_window_independent(hwnd, width, height, before_screenshot_time)

    def _create_bmpinfo_buffer(self, width, height):
        """
        创建位图信息结构
        :param width: 窗口宽度
        :param height: 窗口高度
        :return: bmpinfo_buffer
        """
        bmpinfo_buffer = ctypes.create_string_buffer(40)
        # 设置结构体大小 (4字节)
        ctypes.c_uint32.from_address(ctypes.addressof(bmpinfo_buffer)).value = 40
        # 设置宽度 (4字节，偏移4)
        ctypes.c_int32.from_address(ctypes.addressof(bmpinfo_buffer) + 4).value = width
        # 设置高度 (4字节，偏移8) - 负数表示从上到下
        ctypes.c_int32.from_address(ctypes.addressof(bmpinfo_buffer) + 8).value = -height
        # 设置位面数 (2字节，偏移12)
        ctypes.c_uint16.from_address(ctypes.addressof(bmpinfo_buffer) + 12).value = 1
        # 设置位深度 (2字节，偏移14)
        ctypes.c_uint16.from_address(ctypes.addressof(bmpinfo_buffer) + 14).value = 32
        # 设置压缩方式 (4字节，偏移16) - 0表示BI_RGB无压缩
        ctypes.c_uint32.from_address(ctypes.addressof(bmpinfo_buffer) + 16).value = 0
        return bmpinfo_buffer

    def _create_bitmap_resources(self, width, height):
        """
        创建位图相关资源
        :param width: 窗口宽度
        :param height: 窗口高度
        :return: (saveBitMap, buffer, bmpinfo_buffer)
        """
        # 创建兼容位图
        saveBitMap = ctypes.windll.gdi32.CreateCompatibleBitmap(self.print_window_hwndDC, width, height)
        if not saveBitMap:
            raise Exception('无法创建兼容位图')

        # 创建缓冲区
        buffer_size = width * height * 4
        buffer = ctypes.create_string_buffer(buffer_size)

        # 创建位图信息结构
        bmpinfo_buffer = self._create_bmpinfo_buffer(width, height)

        return saveBitMap, buffer, bmpinfo_buffer

    def _capture_window_to_bitmap(self, hwnd, width, height, hwndDC, mfcDC, saveBitMap, buffer, bmpinfo_buffer, before_screenshot_time):
        """
        执行窗口截图的核心逻辑（通用版本，支持传入不同的DC句柄）
        :param hwnd: 窗口句柄
        :param width: 窗口宽度
        :param height: 窗口高度
        :param hwndDC: 窗口设备上下文
        :param mfcDC: 兼容设备上下文
        :param saveBitMap: 位图句柄
        :param buffer: 数据缓冲区
        :param bmpinfo_buffer: 位图信息结构
        :param before_screenshot_time: 截图开始时间
        :return: 截图数组
        """
        # 选择位图到设备上下文
        ctypes.windll.gdi32.SelectObject(mfcDC, saveBitMap)

        # 复制窗口内容到位图 - 使用Print Window获取后台窗口内容
        result = ctypes.windll.user32.PrintWindow(hwnd, mfcDC, 0x00000002)  # PW_CLIENTONLY
        if not result:
            # 如果Print Window失败，尝试使用BitBlt
            log.debug("Print Window 失败，尝试使用 BitBlt")
            ctypes.windll.gdi32.BitBlt(mfcDC, 0, 0, width, height,
                                       hwndDC, 0, 0, 0x00CC0020)  # SRCCOPY

        # 获取DIB数据
        lines = ctypes.windll.gdi32.GetDIBits(hwndDC, saveBitMap,
                                              0, height, buffer,
                                              bmpinfo_buffer, 0)  # DIB_RGB_COLORS

        if lines == 0:
            log.warning('无法获取位图数据')
            return None

        # 转换为numpy数组
        img_array = np.frombuffer(buffer, dtype=np.uint8)
        img_array = img_array.reshape((height, width, 4))

        # 转换BGRA为RGB
        screenshot = cv2.cvtColor(img_array, cv2.COLOR_BGRA2RGB)

        # 缩放到标准分辨率
        if self.game_win.is_win_scale:
            screenshot = cv2.resize(screenshot, (self.standard_width, self.standard_height))

        after_screenshot_time = time.time()
        log.debug(f"Print Window 截图耗时:{after_screenshot_time - before_screenshot_time}")
        return screenshot

    def _get_screenshot_print_window_independent(self, hwnd, width, height, before_screenshot_time) -> MatLike | None:
        """
        独立模式Print Window截图，自管理资源
        :param hwnd: 窗口句柄
        :param width: 窗口宽度
        :param height: 窗口高度
        :param before_screenshot_time: 截图开始时间
        :return: 截图数组
        """
        # 独立创建所有需要的资源，不依赖预加载状态
        hwndDC = None
        mfcDC = None
        saveBitMap = None

        try:
            # 获取窗口设备上下文
            hwndDC = ctypes.windll.user32.GetWindowDC(hwnd)
            if not hwndDC:
                raise Exception('无法获取窗口设备上下文')

            # 创建兼容的设备上下文
            mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                raise Exception('无法创建兼容设备上下文')

            # 创建兼容位图
            saveBitMap = ctypes.windll.gdi32.CreateCompatibleBitmap(hwndDC, width, height)
            if not saveBitMap:
                raise Exception('无法创建兼容位图')

            # 创建缓冲区
            buffer_size = width * height * 4
            buffer = ctypes.create_string_buffer(buffer_size)

            # 使用通用方法创建位图信息结构
            bmpinfo_buffer = self._create_bmpinfo_buffer(width, height)

            # 使用通用截图方法
            return self._capture_window_to_bitmap(hwnd, width, height, hwndDC, mfcDC,
                                                saveBitMap, buffer, bmpinfo_buffer,
                                                before_screenshot_time)

        except Exception as e:
            log.debug(f'独立模式Print Window截图失败: {e}')
            return None

        finally:
            # 清理独立创建的资源，不影响预加载状态
            if saveBitMap:
                ctypes.windll.gdi32.DeleteObject(saveBitMap)
            if mfcDC:
                ctypes.windll.gdi32.DeleteDC(mfcDC)
            if hwndDC:
                ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
