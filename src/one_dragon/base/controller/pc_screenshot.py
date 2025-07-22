import time
import cv2
import ctypes
import numpy as np
import pyautogui
import comtypes
import comtypes.client
from ctypes import windll, byref

from typing import Optional
from PIL.Image import Image
from cv2.typing import MatLike
from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.utils.log_utils import log
from one_dragon.base.geometry.rectangle import Rect

# DXGI screenshot using D3DShot library
try:
    import d3dshot
    D3DSHOT_AVAILABLE = True
    log.debug("D3DShot library loaded successfully")
except ImportError as e:
    D3DSHOT_AVAILABLE = False
    log.debug(f"D3DShot library not available: {e}")

# Fallback DXGI and WGC COM interface definitions (for future use)
try:
    # DXGI interfaces
    from comtypes import GUID

    # DXGI constants
    DXGI_FORMAT_B8G8R8A8_UNORM = 87
    DXGI_USAGE_RENDER_TARGET_OUTPUT = 0x20
    DXGI_USAGE_READ_BACK = 0x40

    # Windows Graphics Capture constants
    GRAPHICS_CAPTURE_ACCESS_KIND_PROGRAMMATIC = 0

    # Define required GUIDs
    IID_IDXGIFactory1 = GUID('{770aae78-f26f-4dba-a829-253c83d1b387}')
    IID_IDXGIAdapter = GUID('{2411e7e1-12ac-4ccf-bd14-9798e8534dc0}')
    IID_IDXGIOutput = GUID('{ae02eedb-c735-4690-8d52-5a8dc20213aa}')
    IID_IDXGIOutput1 = GUID('{00cddea8-939b-4b83-a340-a685226666cc}')
    IID_ID3D11Device = GUID('{db6f6ddb-ac77-4e88-8253-819df9bbf140}')
    IID_ID3D11DeviceContext = GUID('{c0bfa96c-e089-44fb-8eaf-26f8796190da}')
    IID_ID3D11Texture2D = GUID('{6f15aaf2-d208-4e89-9ab4-489535d34f9c}')

    DXGI_AVAILABLE = True
except ImportError as e:
    DXGI_AVAILABLE = False
    log.warning(f"DXGI/WGC dependencies not available: {e}. Manual DXGI implementation will be disabled.")


class PcScreenshot:
    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        self.game_win: PcGameWindow = game_win
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height
        self.sct: Optional[mss] = None

        # DXGI resources
        self.dxgi_factory = None
        self.dxgi_adapter = None
        self.dxgi_output = None
        self.dxgi_output1 = None
        self.d3d11_device = None
        self.d3d11_context = None
        self.desktop_duplication = None

        # WGC resources
        self.wgc_capture_item = None
        self.wgc_d3d_device = None
        self.wgc_frame_pool = None
        self.wgc_capture_session = None

        # Store the successfully initialized method
        self.initialized_method: Optional[str] = None

        # D3DShot instance for DXGI screenshot
        self.d3dshot_instance = None

    def get_screenshot(self, independent: bool = False) -> MatLike | None:
        """
        根据初始化的方法获取截图
        :param independent: 是否独立截图（不进行缩放）
        :return: 截图数组
        """
        if not self.initialized_method:
            log.error('截图方法尚未初始化，请先调用 init_screenshot()')
            return None

        if self.initialized_method == "mss":
            return self.get_screenshot_mss(independent)
        elif self.initialized_method == "dxgi":
            return self.get_screenshot_dxgi(independent)
        elif self.initialized_method == "wgc":
            return self.get_screenshot_wgc(independent)
        elif self.initialized_method == "print_window":
            return self.get_screenshot_print_window(independent)
        else:
            log.error(f'未知的截图方法: {self.initialized_method}')
            return None

    def init_screenshot(self, method: str):
        """
        初始化截图方法，带有回退机制
        :param method: 首选的截图方法 ("mss", "dxgi", "wgc", "auto")
        """
        # 定义方法优先级
        fallback_order = {
            "wgc": ["wgc", "dxgi", "mss", "print_window"],
            "dxgi": ["dxgi", "wgc", "mss", "print_window"],
            "mss": ["mss", "print_window"],
            "print_window": ["print_window"],
            "auto": ["wgc", "dxgi", "mss", "print_window"]
        }

        methods_to_try = fallback_order.get(method, ["mss"])

        for attempt_method in methods_to_try:
            success = False

            if attempt_method == "mss":
                success = self.init_mss()
            elif attempt_method == "dxgi":
                success = self.init_dxgi()
            elif attempt_method == "wgc":
                success = self.init_wgc()
            elif attempt_method == "print_window":
                success = True  # PrintWindow doesn't need initialization

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
        if self.sct is not None:
            try:
                self.sct.close()
            except Exception:
                pass
            self.sct = None

        try:
            from mss import mss
            self.sct = mss()
            return True
        except Exception as e:
            log.debug(f'MSS初始化失败: {str(e)}')
            return False

    def init_dxgi(self):
        """初始化DXGI资源 - 使用D3DShot库"""
        if not D3DSHOT_AVAILABLE:
            log.debug('D3DShot库不可用，无法使用DXGI截图')
            return False

        # 清理旧资源
        self.cleanup_dxgi()

        try:
            # 创建D3DShot实例
            self.d3dshot_instance = d3dshot.create(capture_output="numpy")
            if self.d3dshot_instance is None:
                log.debug('D3DShot实例创建失败')
                return False

            log.debug('DXGI初始化成功（使用D3DShot库）')
            return True

        except Exception as e:
            log.debug(f'DXGI初始化失败: {str(e)}')
            self.cleanup_dxgi()
            return False

    def cleanup_dxgi(self):
        """清理DXGI资源"""
        # 清理D3DShot实例
        if self.d3dshot_instance:
            try:
                # D3DShot通常会自动清理资源，但我们可以显式设置为None
                self.d3dshot_instance = None
                log.debug('D3DShot实例已清理')
            except Exception as e:
                log.debug(f'D3DShot实例清理异常: {e}')

        # 清理传统DXGI资源（如果存在）
        if hasattr(self, 'desktop_duplication') and self.desktop_duplication:
            try:
                self.desktop_duplication.Release()
            except:
                pass
            self.desktop_duplication = None

        if hasattr(self, 'd3d11_context') and self.d3d11_context:
            try:
                self.d3d11_context.Release()
            except:
                pass
            self.d3d11_context = None

        if hasattr(self, 'd3d11_device') and self.d3d11_device:
            try:
                self.d3d11_device.Release()
            except:
                pass
            self.d3d11_device = None

        if hasattr(self, 'dxgi_output1') and self.dxgi_output1:
            try:
                self.dxgi_output1.Release()
            except:
                pass
            self.dxgi_output1 = None

        if hasattr(self, 'dxgi_output') and self.dxgi_output:
            try:
                self.dxgi_output.Release()
            except:
                pass
            self.dxgi_output = None

        if hasattr(self, 'dxgi_adapter') and self.dxgi_adapter:
            try:
                self.dxgi_adapter.Release()
            except:
                pass
            self.dxgi_adapter = None

        if hasattr(self, 'dxgi_factory') and self.dxgi_factory:
            try:
                self.dxgi_factory.Release()
            except:
                pass
            self.dxgi_factory = None

        try:
            comtypes.CoUninitialize()
        except:
            pass

    def init_wgc(self):
        """初始化WGC资源"""
        if not DXGI_AVAILABLE:
            return False

        hwnd = self.game_win.get_hwnd()
        if not hwnd:
            return False

        # 清理旧资源
        self.cleanup_wgc()

        try:
            # 检查Windows版本
            import sys
            if sys.getwindowsversion().build < 17763:  # Windows 10 1809
                return False

            # 导入Windows Runtime
            try:
                from winrt.windows.graphics.capture import GraphicsCaptureItem
                from winrt.windows.graphics.directx import DirectXPixelFormat
                from winrt.windows.graphics.directx.direct3d11 import Direct3DDevice
                from winrt.windows.graphics.capture import Direct3D11CaptureFramePool
            except ImportError:
                return False

            # 初始化COM
            comtypes.CoInitialize()

            # 创建GraphicsCaptureItem
            self.wgc_capture_item = GraphicsCaptureItem.create_from_window_handle(hwnd)
            if not self.wgc_capture_item:
                return False

            # 创建Direct3D设备
            self.wgc_d3d_device = Direct3DDevice.create_from_d3d11_device(None)
            if not self.wgc_d3d_device:
                return False

            # 获取窗口大小
            size = self.wgc_capture_item.size
            if size.width <= 0 or size.height <= 0:
                return False

            # 创建帧池
            self.wgc_frame_pool = Direct3D11CaptureFramePool.create(
                self.wgc_d3d_device,
                DirectXPixelFormat.B8G8R8A8_UINT_NORMALIZED,
                1,  # 缓冲区数量
                size
            )
            if not self.wgc_frame_pool:
                return False

            # 创建捕获会话
            self.wgc_capture_session = self.wgc_frame_pool.create_capture_session(self.wgc_capture_item)
            if not self.wgc_capture_session:
                return False

            return True

        except Exception as e:
            log.debug(f'WGC初始化失败: {str(e)}')
            self.cleanup_wgc()
            return False

    def cleanup_wgc(self):
        """清理WGC资源"""
        try:
            if self.wgc_capture_session:
                self.wgc_capture_session.close()
                self.wgc_capture_session = None
        except:
            pass

        try:
            if self.wgc_frame_pool:
                self.wgc_frame_pool.close()
                self.wgc_frame_pool = None
        except:
            pass

        try:
            if self.wgc_d3d_device:
                # WinRT对象通常不需要显式释放
                self.wgc_d3d_device = None
        except:
            pass

        try:
            if self.wgc_capture_item:
                # WinRT对象通常不需要显式释放
                self.wgc_capture_item = None
        except:
            pass

        try:
            comtypes.CoUninitialize()
        except:
            pass

    def get_screenshot_mss(self, independent: bool = False) -> MatLike | None:
        """
        截图 如果分辨率和默认不一样则进行缩放
        :return: 截图
        """
        rect: Rect = self.game_win.win_rect
        if rect is None:
            return None

        left = rect.x1
        top = rect.y1
        width = rect.width
        height = rect.height

        if self.sct is not None:
            monitor = {"top": top, "left": left, "width": width, "height": height}
            if independent:
                try:
                    from mss import mss
                    with mss() as sct:
                        before_screenshot_time = time.time()
                        log.debug(f"MSS 截图开始时间:{before_screenshot_time}")
                        screenshot = cv2.cvtColor(np.array(sct.grab(monitor)), cv2.COLOR_BGRA2RGB)
                except Exception:
                    pass
            else:
                before_screenshot_time = time.time()
                log.debug(f"MSS 截图开始时间:{before_screenshot_time}")
                screenshot = cv2.cvtColor(np.array(self.sct.grab(monitor)), cv2.COLOR_BGRA2RGB)
        else:
            img: Image = pyautogui.screenshot(region=(left, top, width, height))
            screenshot = np.array(img)

        if self.game_win.is_win_scale:
            result = cv2.resize(screenshot, (self.standard_width, self.standard_height))
        else:
            result = screenshot

        after_screenshot_time = time.time()
        log.debug(f"MSS 截图结束时间:{after_screenshot_time}\n耗时:{after_screenshot_time - before_screenshot_time}")
        return result

    def get_screenshot_print_window(self, independent: bool = False) -> MatLike | None:
        """
        PrintWindow 获取窗口截图
        """
        before_screenshot_time = time.time()
        log.debug(f"PrintWindow 截图开始时间:{before_screenshot_time}")
        hwnd = self.game_win.get_hwnd()
        if not hwnd:
            log.warning('未找到目标窗口，无法截图')
            return None

        rect: Rect = self.game_win.win_rect
        if rect is None:
            return None

        width = rect.width
        height = rect.height

        if width <= 0 or height <= 0:
            log.warning(f'窗口大小无效: {width}x{height}')
            return None

        # 获取窗口设备上下文
        hwndDC = ctypes.windll.user32.GetWindowDC(hwnd)
        if not hwndDC:
            log.warning('无法获取窗口设备上下文')
            return None

        # 创建兼容的设备上下文和位图
        mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
        if not mfcDC:
            log.warning('无法创建兼容设备上下文')
            ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
            return None

        saveBitMap = ctypes.windll.gdi32.CreateCompatibleBitmap(hwndDC, width, height)
        if not saveBitMap:
            log.warning('无法创建兼容位图')
            ctypes.windll.gdi32.DeleteDC(mfcDC)
            ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
            return None

        try:
            # 选择位图到设备上下文
            ctypes.windll.gdi32.SelectObject(mfcDC, saveBitMap)

            # 复制窗口内容到位图 - 使用PrintWindow获取后台窗口内容
            result = ctypes.windll.user32.PrintWindow(hwnd, mfcDC, 0x00000002)  # PW_CLIENTONLY
            if not result:
                # 如果PrintWindow失败，尝试使用BitBlt
                log.debug("PrintWindow 失败，尝试使用 BitBlt")
                ctypes.windll.gdi32.BitBlt(mfcDC, 0, 0, width, height, hwndDC, 0, 0, 0x00CC0020)  # SRCCOPY

            # 创建缓冲区
            buffer_size = width * height * 4
            buffer = ctypes.create_string_buffer(buffer_size)

            # 使用简化的位图信息结构 - 直接创建一个40字节的结构
            # BITMAPINFOHEADER 的大小固定为40字节
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

            # 获取DIB数据
            lines = ctypes.windll.gdi32.GetDIBits(hwndDC, saveBitMap, 0, height, buffer,
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
            log.debug(f"PrintWindow 截图结束时间:{after_screenshot_time}\n耗时:{after_screenshot_time - before_screenshot_time}")
            return screenshot

        finally:
            # 清理资源，先创建的后释放
            ctypes.windll.gdi32.DeleteObject(saveBitMap)
            ctypes.windll.gdi32.DeleteDC(mfcDC)
            ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)

    def get_screenshot_dxgi(self, independent: bool = False) -> MatLike | None:
        """
        使用DXGI进行截图 - 使用D3DShot库实现
        :param independent: 是否独立截图（不进行缩放）
        :return: 截图数组
        """
        if not D3DSHOT_AVAILABLE:
            log.warning('D3DShot库不可用，无法使用DXGI截图')
            return None

        # 检查D3DShot实例是否已初始化
        if not self.d3dshot_instance:
            if not self.init_dxgi():
                log.warning('DXGI初始化失败')
                return None

        try:
            before_screenshot_time = time.time()
            log.debug(f"DXGI 截图开始时间:{before_screenshot_time}")

            # 使用D3DShot获取截图
            screenshot = self.d3dshot_instance.screenshot()
            if screenshot is None:
                log.warning('D3DShot截图失败，尝试重新初始化')
                if self.init_dxgi():
                    screenshot = self.d3dshot_instance.screenshot()
                    if screenshot is None:
                        log.warning('重新初始化后D3DShot截图仍失败')
                        return None
                else:
                    log.warning('D3DShot重新初始化失败')
                    return None

            # D3DShot返回numpy数组，确保格式正确
            if hasattr(screenshot, 'shape') and len(screenshot.shape) == 3:
                # 如果是BGR格式，转换为RGB
                if screenshot.shape[2] == 3:
                    # D3DShot默认返回RGB格式，无需转换
                    pass
                elif screenshot.shape[2] == 4:
                    # 如果是BGRA，转换为RGB
                    screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2RGB)
            else:
                log.warning('D3DShot返回的截图格式不正确')
                return None

            # 获取游戏窗口区域进行裁剪（如果需要）
            rect = self.game_win.win_rect
            if rect and not independent:
                height, width = screenshot.shape[:2]
                # 裁剪到游戏窗口区域
                x1, y1, x2, y2 = rect.x1, rect.y1, rect.x2, rect.y2
                if 0 <= x1 < width and 0 <= y1 < height and x1 < x2 <= width and y1 < y2 <= height:
                    screenshot = screenshot[y1:y2, x1:x2]

            # 缩放到标准分辨率
            if not independent and self.game_win.is_win_scale:
                screenshot = cv2.resize(screenshot, (self.standard_width, self.standard_height))

            after_screenshot_time = time.time()
            log.debug(f"DXGI 截图结束时间:{after_screenshot_time}\n耗时:{after_screenshot_time - before_screenshot_time}")

            return screenshot

        except Exception as e:
            log.error(f'DXGI截图失败: {str(e)}')
            return None

    def get_screenshot_wgc(self, independent: bool = False) -> MatLike | None:
        """
        使用Windows Graphics Capture (WGC) 进行截图 - Windows 10 1903+
        :param independent: 是否独立截图（不进行缩放）
        :return: 截图数组
        """
        if not DXGI_AVAILABLE:
            log.warning('WGC不可用，请安装comtypes库')
            return None

        hwnd = self.game_win.get_hwnd()
        if not hwnd:
            log.warning('未找到目标窗口，无法使用WGC截图')
            return None

        # 初始化WGC资源（如果尚未初始化）
        if not self.wgc_capture_session:
            if not self.init_wgc():
                log.warning('WGC初始化失败')
                return None

        try:
            before_screenshot_time = time.time()
            log.debug(f"WGC 截图开始时间:{before_screenshot_time}")

            # 导入需要的模块
            try:
                from winrt.windows.graphics.imaging import BitmapEncoder
                from winrt.windows.storage.streams import InMemoryRandomAccessStream
            except ImportError:
                log.warning('WGC需要winrt库支持，请安装: pip install winrt')
                return None

            # 设置帧到达事件处理
            frame_data = {'frame': None, 'event': None}

            def on_frame_arrived(sender, args):
                try:
                    frame = sender.try_get_next_frame()
                    if frame:
                        frame_data['frame'] = frame
                        if frame_data['event']:
                            frame_data['event'].set()
                except Exception as e:
                    log.debug(f'帧处理异常: {str(e)}')

            # 注册事件处理器
            import threading
            frame_data['event'] = threading.Event()
            self.wgc_frame_pool.frame_arrived += on_frame_arrived

            # 开始捕获
            self.wgc_capture_session.start_capture()

            # 等待帧到达（最多等待5秒）
            if not frame_data['event'].wait(timeout=5.0):
                log.warning('等待WGC帧超时')
                return None

            # 获取捕获的帧
            frame = frame_data['frame']
            if not frame:
                log.warning('未获取到WGC帧')
                return None

            # 获取表面
            surface = frame.surface
            if not surface:
                log.warning('未获取到WGC表面')
                return None

            # 创建内存流
            stream = InMemoryRandomAccessStream()

            # 创建位图编码器
            encoder = BitmapEncoder.create_async(
                BitmapEncoder.png_encoder_id,
                stream
            ).get()

            # 设置像素数据
            encoder.set_software_bitmap(surface)

            # 完成编码
            encoder.flush_async().get()

            # 读取流数据
            stream.seek(0)
            buffer = stream.read_buffer(stream.size)

            # 转换为bytes
            data = bytes(buffer)

            # 使用PIL解码PNG数据
            from PIL import Image
            import io

            pil_image = Image.open(io.BytesIO(data))

            # 转换为numpy数组
            img_array = np.array(pil_image)

            # 如果是RGBA，转换为RGB
            if img_array.shape[2] == 4:
                screenshot = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
            else:
                screenshot = img_array

            # 处理窗口区域和缩放
            if not independent:
                rect = self.game_win.win_rect
                if rect and self.game_win.is_win_scale:
                    screenshot = cv2.resize(screenshot, (self.standard_width, self.standard_height))

            # 清理临时资源
            stream.close()

            after_screenshot_time = time.time()
            log.debug(f"WGC 截图结束时间:{after_screenshot_time}\n耗时:{after_screenshot_time - before_screenshot_time}")

            return screenshot

        except Exception as e:
            log.error(f'WGC截图失败: {str(e)}')
            return None
