"""
按进程捕获音频（WASAPI Process Loopback）

只录制指定进程（含其子进程）发出的声音，不受默认输出设备、其他程序声音的影响。
要求 Windows 10 2004（build 19041）及以上。

参考: https://learn.microsoft.com/windows/win32/api/audioclientactivationparams/
"""

import ctypes
import sys
import threading
import uuid
from ctypes import wintypes

import numpy as np

_HRESULT = ctypes.c_long

_S_OK = 0
_S_FALSE = 1
_E_NOINTERFACE = ctypes.c_long(0x80004002).value
_E_POINTER = ctypes.c_long(0x80004003).value
_RPC_E_CHANGED_MODE = ctypes.c_long(0x80010106).value

_COINIT_MULTITHREADED = 0x0
_VT_BLOB = 65
_WAVE_FORMAT_PCM = 1

_AUDCLNT_SHAREMODE_SHARED = 0
_AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
_AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000
_AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY = 0x08000000
_AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM = 0x80000000
_AUDCLNT_BUFFERFLAGS_SILENT = 0x2

_AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1
_PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE = 0

_VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK = 'VAD\\Process_Loopback'

# 支持 Process Loopback 的最低系统版本
_MIN_WINDOWS_BUILD = 19041

# IAudioClient 虚函数表下标
_AUDIO_CLIENT_INITIALIZE = 3
_AUDIO_CLIENT_START = 10
_AUDIO_CLIENT_STOP = 11
_AUDIO_CLIENT_SET_EVENT_HANDLE = 13
_AUDIO_CLIENT_GET_SERVICE = 14

# IAudioCaptureClient 虚函数表下标
_CAPTURE_GET_BUFFER = 3
_CAPTURE_RELEASE_BUFFER = 4
_CAPTURE_GET_NEXT_PACKET_SIZE = 5

# IActivateAudioInterfaceAsyncOperation 虚函数表下标
_ASYNC_OP_GET_ACTIVATE_RESULT = 3

# IUnknown 虚函数表下标
_UNKNOWN_QUERY_INTERFACE = 0
_UNKNOWN_RELEASE = 2


class _GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', wintypes.DWORD),
        ('Data2', wintypes.WORD),
        ('Data3', wintypes.WORD),
        ('Data4', ctypes.c_ubyte * 8),
    ]


def _guid(value: str) -> _GUID:
    return _GUID.from_buffer_copy(uuid.UUID(value).bytes_le)


_IID_IUNKNOWN = _guid('00000000-0000-0000-C000-000000000046')
_IID_IAGILE_OBJECT = _guid('94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90')
_IID_IACTIVATE_COMPLETION_HANDLER = _guid('41D949AB-9862-444A-80F6-C261334DA5EB')
_IID_IAUDIO_CLIENT = _guid('1CB9AD4C-DBFA-4C32-B178-C2F568A703B2')
_IID_IAUDIO_CAPTURE_CLIENT = _guid('C8ADBD64-E71E-48A0-A4DE-185C395CD317')


class _AudioClientProcessLoopbackParams(ctypes.Structure):
    _fields_ = [
        ('TargetProcessId', wintypes.DWORD),
        ('ProcessLoopbackMode', ctypes.c_int),
    ]


class _AudioClientActivationParams(ctypes.Structure):
    _fields_ = [
        ('ActivationType', ctypes.c_int),
        ('ProcessLoopbackParams', _AudioClientProcessLoopbackParams),
    ]


class _Blob(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_ulong),
        ('pBlobData', ctypes.c_void_p),
    ]


class _PropVariant(ctypes.Structure):
    _fields_ = [
        ('vt', ctypes.c_ushort),
        ('wReserved1', ctypes.c_ushort),
        ('wReserved2', ctypes.c_ushort),
        ('wReserved3', ctypes.c_ushort),
        ('blob', _Blob),
    ]


class _WaveFormatEx(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('wFormatTag', wintypes.WORD),
        ('nChannels', wintypes.WORD),
        ('nSamplesPerSec', wintypes.DWORD),
        ('nAvgBytesPerSec', wintypes.DWORD),
        ('nBlockAlign', wintypes.WORD),
        ('wBitsPerSample', wintypes.WORD),
        ('cbSize', wintypes.WORD),
    ]


_QueryInterfaceFunc = ctypes.WINFUNCTYPE(_HRESULT, ctypes.c_void_p, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))
_AddRefFunc = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
_ReleaseFunc = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
_ActivateCompletedFunc = ctypes.WINFUNCTYPE(_HRESULT, ctypes.c_void_p, ctypes.c_void_p)


class _CompletionHandlerVtbl(ctypes.Structure):
    _fields_ = [
        ('QueryInterface', _QueryInterfaceFunc),
        ('AddRef', _AddRefFunc),
        ('Release', _ReleaseFunc),
        ('ActivateCompleted', _ActivateCompletedFunc),
    ]


class _CompletionHandlerObject(ctypes.Structure):
    _fields_ = [('lpVtbl', ctypes.POINTER(_CompletionHandlerVtbl))]


class ProcessAudioCaptureError(RuntimeError):
    """进程音频捕获失败"""


class _ActivateCompletionHandler:
    """
    用 Python 实现的 IActivateAudioInterfaceCompletionHandler COM 对象。
    同时声明支持 IAgileObject，让系统在任意线程直接回调，不需要消息循环。
    对象生命周期由 Python 管理，引用计数只做记录。
    """

    def __init__(self) -> None:
        self.done: threading.Event = threading.Event()
        self._ref_count: int = 1
        self._vtbl: _CompletionHandlerVtbl = _CompletionHandlerVtbl(
            _QueryInterfaceFunc(self._query_interface),
            _AddRefFunc(self._add_ref),
            _ReleaseFunc(self._release),
            _ActivateCompletedFunc(self._activate_completed),
        )
        self._obj: _CompletionHandlerObject = _CompletionHandlerObject(ctypes.pointer(self._vtbl))

    @property
    def ptr(self) -> ctypes.c_void_p:
        return ctypes.c_void_p(ctypes.addressof(self._obj))

    def _query_interface(self, this: int | None, riid: 'ctypes._Pointer[_GUID]', ppv: 'ctypes._Pointer[ctypes.c_void_p]') -> int:
        if not ppv:
            return _E_POINTER
        iid = bytes(riid.contents)
        if iid in (bytes(_IID_IUNKNOWN), bytes(_IID_IAGILE_OBJECT), bytes(_IID_IACTIVATE_COMPLETION_HANDLER)):
            ppv[0] = this
            self._add_ref(this)
            return _S_OK
        ppv[0] = None
        return _E_NOINTERFACE

    def _add_ref(self, this: int | None) -> int:
        self._ref_count += 1
        return self._ref_count

    def _release(self, this: int | None) -> int:
        self._ref_count = max(self._ref_count - 1, 0)
        return self._ref_count

    def _activate_completed(self, this: int | None, operation: int | None) -> int:
        self.done.set()
        return _S_OK


def _check_hr(hr: int, action: str) -> None:
    if hr < 0:
        raise ProcessAudioCaptureError(f'{action} 失败 HRESULT=0x{hr & 0xFFFFFFFF:08X}')


def _com_call(ptr: ctypes.c_void_p, index: int, argtypes: list[type], *args: object) -> int:
    """按虚函数表下标调用 COM 方法"""
    vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    func = ctypes.WINFUNCTYPE(_HRESULT, ctypes.c_void_p, *argtypes)(vtbl[index])
    return func(ptr, *args)


def _com_release(ptr: ctypes.c_void_p) -> None:
    if ptr:
        _com_call(ptr, _UNKNOWN_RELEASE, [])


def is_process_audio_capture_supported() -> bool:
    """当前系统是否支持按进程捕获音频"""
    if sys.platform != 'win32':
        return False
    return sys.getwindowsversion().build >= _MIN_WINDOWS_BUILD


def get_pid_by_hwnd(hwnd: int | None) -> int | None:
    """
    获取窗口所属进程的 PID
    :param hwnd: 窗口句柄
    :return: PID，窗口无效时返回 None
    """
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return pid.value if pid.value != 0 else None


class ProcessAudioCapture:
    """
    捕获指定进程（含子进程）的音频，输出 float32、范围 [-1, 1] 的数据。

    用法:
        with ProcessAudioCapture(pid, 32000, 2) as capture:
            data = capture.read(100)  # shape: (帧数, 声道数)

    COM 按线程初始化，open / read / close 需要在同一个线程调用。
    """

    def __init__(self, pid: int, sample_rate: int, channels: int, buffer_ms: int = 100) -> None:
        self.pid: int = pid
        self.sample_rate: int = sample_rate
        self.channels: int = channels
        self._buffer_ms: int = buffer_ms

        self._com_initialized: bool = False
        self._audio_client: ctypes.c_void_p = ctypes.c_void_p()
        self._capture_client: ctypes.c_void_p = ctypes.c_void_p()
        self._event: int | None = None
        self._started: bool = False

    def __enter__(self) -> 'ProcessAudioCapture':
        self.open()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def open(self) -> None:
        """激活进程音频并开始捕获。失败时会清理已申请的资源并抛出 ProcessAudioCaptureError"""
        try:
            self._open()
        except Exception:
            self.close()
            raise

    def _open(self) -> None:
        if not is_process_audio_capture_supported():
            raise ProcessAudioCaptureError(f'系统版本低于 build {_MIN_WINDOWS_BUILD}，不支持按进程捕获音频')

        ole32 = ctypes.windll.ole32
        hr = ole32.CoInitializeEx(None, _COINIT_MULTITHREADED)
        if hr in (_S_OK, _S_FALSE):
            self._com_initialized = True
        elif hr != _RPC_E_CHANGED_MODE:  # 线程已经是其他套间模式时可以直接继续用
            _check_hr(hr, 'CoInitializeEx')

        self._audio_client = self._activate_audio_client()

        block_align = self.channels * 2
        wave_format = _WaveFormatEx(
            wFormatTag=_WAVE_FORMAT_PCM,
            nChannels=self.channels,
            nSamplesPerSec=self.sample_rate,
            nAvgBytesPerSec=self.sample_rate * block_align,
            nBlockAlign=block_align,
            wBitsPerSample=16,
            cbSize=0,
        )
        stream_flags = (
            _AUDCLNT_STREAMFLAGS_LOOPBACK
            | _AUDCLNT_STREAMFLAGS_EVENTCALLBACK
            | _AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM
            | _AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY
        )
        buffer_duration = self._buffer_ms * 10000  # 单位 100 纳秒
        _check_hr(_com_call(
            self._audio_client, _AUDIO_CLIENT_INITIALIZE,
            [ctypes.c_int, wintypes.DWORD, ctypes.c_longlong, ctypes.c_longlong,
             ctypes.POINTER(_WaveFormatEx), ctypes.POINTER(_GUID)],
            _AUDCLNT_SHAREMODE_SHARED, stream_flags, buffer_duration, 0, ctypes.byref(wave_format), None,
        ), 'IAudioClient::Initialize')

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateEventW.restype = wintypes.HANDLE
        kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        self._event = kernel32.CreateEventW(None, False, False, None)
        if not self._event:
            raise ProcessAudioCaptureError('CreateEventW 失败')
        _check_hr(_com_call(
            self._audio_client, _AUDIO_CLIENT_SET_EVENT_HANDLE, [wintypes.HANDLE], self._event,
        ), 'IAudioClient::SetEventHandle')

        _check_hr(_com_call(
            self._audio_client, _AUDIO_CLIENT_GET_SERVICE,
            [ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)],
            ctypes.byref(_IID_IAUDIO_CAPTURE_CLIENT), ctypes.byref(self._capture_client),
        ), 'IAudioClient::GetService')

        _check_hr(_com_call(self._audio_client, _AUDIO_CLIENT_START, []), 'IAudioClient::Start')
        self._started = True

    def _activate_audio_client(self) -> ctypes.c_void_p:
        """通过 ActivateAudioInterfaceAsync 激活目标进程的 IAudioClient"""
        params = _AudioClientActivationParams(
            ActivationType=_AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK,
            ProcessLoopbackParams=_AudioClientProcessLoopbackParams(
                TargetProcessId=self.pid,
                ProcessLoopbackMode=_PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE,
            ),
        )
        prop = _PropVariant()
        prop.vt = _VT_BLOB
        prop.blob.cbSize = ctypes.sizeof(params)
        prop.blob.pBlobData = ctypes.cast(ctypes.pointer(params), ctypes.c_void_p)

        activate = ctypes.WinDLL('Mmdevapi.dll').ActivateAudioInterfaceAsync
        activate.restype = _HRESULT
        activate.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(_GUID), ctypes.POINTER(_PropVariant),
                             ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

        handler = _ActivateCompletionHandler()
        operation = ctypes.c_void_p()
        _check_hr(activate(
            _VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK, ctypes.byref(_IID_IAUDIO_CLIENT), ctypes.byref(prop),
            handler.ptr, ctypes.byref(operation),
        ), 'ActivateAudioInterfaceAsync')

        unknown = ctypes.c_void_p()
        try:
            if not handler.done.wait(timeout=5):
                raise ProcessAudioCaptureError('等待进程音频激活超时')
            activate_hr = _HRESULT()
            _check_hr(_com_call(
                operation, _ASYNC_OP_GET_ACTIVATE_RESULT,
                [ctypes.POINTER(_HRESULT), ctypes.POINTER(ctypes.c_void_p)],
                ctypes.byref(activate_hr), ctypes.byref(unknown),
            ), 'GetActivateResult')
            _check_hr(activate_hr.value, f'激活进程音频 pid={self.pid}')

            audio_client = ctypes.c_void_p()
            _check_hr(_com_call(
                unknown, _UNKNOWN_QUERY_INTERFACE,
                [ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)],
                ctypes.byref(_IID_IAUDIO_CLIENT), ctypes.byref(audio_client),
            ), 'QueryInterface IAudioClient')
            return audio_client
        finally:
            _com_release(unknown)
            _com_release(operation)

    def read(self, timeout_ms: int) -> np.ndarray:
        """
        读取当前已捕获的音频。目标进程没有发声时可能返回空数组。
        :param timeout_ms: 没有数据时最多等待的毫秒数
        :return: shape 为 (帧数, 声道数) 的 float32 数组
        """
        ctypes.windll.kernel32.WaitForSingleObject(wintypes.HANDLE(self._event), timeout_ms)

        chunks: list[np.ndarray] = []
        while True:
            packet_size = ctypes.c_uint32()
            _check_hr(_com_call(
                self._capture_client, _CAPTURE_GET_NEXT_PACKET_SIZE,
                [ctypes.POINTER(ctypes.c_uint32)], ctypes.byref(packet_size),
            ), 'IAudioCaptureClient::GetNextPacketSize')
            if packet_size.value == 0:
                break

            data = ctypes.c_void_p()
            frames = ctypes.c_uint32()
            flags = wintypes.DWORD()
            _check_hr(_com_call(
                self._capture_client, _CAPTURE_GET_BUFFER,
                [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(wintypes.DWORD),
                 ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)],
                ctypes.byref(data), ctypes.byref(frames), ctypes.byref(flags), None, None,
            ), 'IAudioCaptureClient::GetBuffer')

            frame_cnt = frames.value
            try:
                if frame_cnt == 0:
                    continue
                if flags.value & _AUDCLNT_BUFFERFLAGS_SILENT or not data.value:
                    chunk = np.zeros((frame_cnt, self.channels), dtype=np.float32)
                else:
                    raw = np.ctypeslib.as_array(
                        ctypes.cast(data, ctypes.POINTER(ctypes.c_int16)),
                        shape=(frame_cnt * self.channels,),
                    )
                    chunk = raw.astype(np.float32).reshape(frame_cnt, self.channels) / 32768.0
                chunks.append(chunk)
            finally:
                _check_hr(_com_call(
                    self._capture_client, _CAPTURE_RELEASE_BUFFER, [ctypes.c_uint32], frame_cnt,
                ), 'IAudioCaptureClient::ReleaseBuffer')

        if len(chunks) == 0:
            return np.empty((0, self.channels), dtype=np.float32)
        return np.concatenate(chunks, axis=0)

    def close(self) -> None:
        """停止捕获并释放资源"""
        if self._started:
            _com_call(self._audio_client, _AUDIO_CLIENT_STOP, [])
            self._started = False
        _com_release(self._capture_client)
        self._capture_client = ctypes.c_void_p()
        _com_release(self._audio_client)
        self._audio_client = ctypes.c_void_p()
        if self._event:
            ctypes.windll.kernel32.CloseHandle(wintypes.HANDLE(self._event))
            self._event = None
        if self._com_initialized:
            ctypes.windll.ole32.CoUninitialize()
            self._com_initialized = False
