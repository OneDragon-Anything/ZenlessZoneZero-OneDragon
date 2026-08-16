from __future__ import annotations

import threading
import warnings
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from enum import Enum, IntEnum
from math import gcd
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
from cv2.typing import MatLike
from scipy.fft import irfft, next_fast_len, rfft
from scipy.io import wavfile
from scipy.io.wavfile import WavFileWarning
from scipy.signal import butter, filtfilt, resample_poly

from one_dragon.base.conditional_operation.state_recorder import StateRecord
from one_dragon.base.operation.context_notify_event import ContextNotifyEvent
from one_dragon.utils import cal_utils, os_utils, thread_utils, yolo_config_utils
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.yolo.flash_classifier import FlashClassifier

if TYPE_CHECKING:
    from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator


# 创建一个线程池执行器，用于异步执行任务
_dodge_check_executor = ThreadPoolExecutor(thread_name_prefix='od_dodge_check', max_workers=16)

class AudioRecorder:
    """
    音频录制类，用于录制和处理音频数据。
    """

    def __init__(self, error_callback: Callable[[RuntimeError], None] | None = None) -> None:
        self.running: bool = False  # 标记录制是否正在运行
        self._run_lock = threading.Lock()  # 用于线程安全的锁
        self._error_callback: Callable[[RuntimeError], None] | None = error_callback

        self._sample_rate: int = 32000  # 采样率
        self._used_channel: int = 2  # 使用的音频通道数
        self._sample_len: float = 0.01  # 每次采样的长度（秒）
        self._chunk_size: int = int(self._sample_rate * self._sample_len)  # 每个音频块的大小

        self.trigger_threshold: float = 0.1  # 触发阈值

        self._filter_degree: int = 4  # 四阶 Butterworth 滤波器，阶数越大阻带衰减越强
        self._cut_off: int = 1000  # 截止频率，滤除该频率以下的声音

        # Butterworth高通滤波
        filter_b, filter_a = butter(
            self._filter_degree,
            self._cut_off,
            btype='highpass',
            output='ba',
            fs=self._sample_rate
        )
        self.filter_b: np.ndarray = filter_b
        self.filter_a: np.ndarray = filter_a

        self.latest_audio: np.ndarray = np.empty(shape=(0,), dtype=np.float64)  # 存储最新的音频数据
        self._update_audio_lock = threading.Lock()

    def start_running_async(self) -> None:
        """
        异步启动音频录制。
        """
        with self._run_lock:
            if self.running:
                return

            self.running = True

        self.latest_audio = np.zeros(self._sample_rate // 2)  # 初始化音频数据缓冲区，长度为0.5秒
        future = _dodge_check_executor.submit(self._record_loop)
        future.add_done_callback(thread_utils.handle_future_result)

    def _record_loop(self) -> None:
        """
        音频录制循环，持续录制音频数据。
        """
        # 这个在全局导入的话 会导致QT的选择文件无法使用
        import soundcard as sc
        from soundcard.mediafoundation import SoundcardRuntimeWarning

        warnings.filterwarnings('ignore', category=SoundcardRuntimeWarning)

        try:
            _mic = sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True)
            _recorder = _mic.recorder(samplerate=self._sample_rate, channels=self._used_channel)
            with _recorder as audio_recorder:
                while self.running:
                    stream_data = audio_recorder.record(numframes=self._chunk_size)
                    # 双声道逐帧取平均值，得到与模板一致的单声道波形。
                    stream_data = np.mean(stream_data, axis=1)

                    with self._update_audio_lock:
                        # 更新 latest_audio
                        self.latest_audio[:-len(stream_data)] = self.latest_audio[len(stream_data):]
                        self.latest_audio[-len(stream_data):] = stream_data
        except RuntimeError as e:
            log.warning('音频录制异常，已停止声音闪避识别', exc_info=True)
            if self._error_callback is not None:
                self._error_callback(e)
        finally:
            self.running = False

    def stop_running(self) -> None:
        """
        停止音频录制。
        """
        self.running = False

    def clear_audio(self) -> None:
        """
        清空当前录音。
        """
        with self._update_audio_lock:
            self.latest_audio = np.zeros(self._sample_rate // 2)

    def get_latest_audio(self) -> np.ndarray:
        """获取不会被录音线程同时修改的音频副本。"""
        with self._update_audio_lock:
            return self.latest_audio.copy()


class AudioTemplateEnum(IntEnum):
    """声音模板编号。"""

    NORMAL_DODGE = 1
    PURPLE_DODGE = 2
    X_DODGE = 3


class YoloStateEventEnum(Enum):
    """
    YOLO状态事件枚举类，定义不同的闪避识别事件。
    """
    DODGE_YELLOW = '闪避识别-黄光'
    DODGE_RED = '闪避识别-红光'
    DODGE_AUDIO = '闪避识别-声音'


class AutoBattleDodgeContext:
    """
    战斗闪避上下文类，用于管理和处理闪避识别相关的逻辑。
    """

    def __init__(self, ctx: ZContext) -> None:
        self.ctx: ZContext = ctx  # 上下文对象

        self._flash_model: FlashClassifier | None = None  # 闪避分类器
        self._audio_recorder: AudioRecorder = AudioRecorder(self._on_audio_record_error)  # 音频录制器
        self._audio_template_fft: np.ndarray | None = None  # 补零后模板的频域数据
        self._audio_corr_mask: np.ndarray | None = None  # 各模板相关结果的有效区间
        self._audio_corr_denominator: np.ndarray | None = None  # 各模板相关系数分母
        self._audio_fft_size: int = 0

        # 识别锁，保证每种类型只有一个实例在进行识别
        self._check_dodge_flash_lock = threading.Lock()
        self._check_audio_lock = threading.Lock()

        # 识别间隔
        self._check_dodge_interval: float | list[float] = 0
        self._check_audio_interval: float = 0.02

        # 上一次识别的时间
        self._last_check_dodge_time: float = 0
        self._last_check_audio_time: float = 0

        # 最近一次命中音频模板的时间，保留给后续事件判断使用
        self._last_audio_event_time: float = 0

    def _on_audio_record_error(self, error: RuntimeError) -> None:
        """音频录制异常时通知当前运行界面。"""
        self.ctx.dispatch_event(
            ContextNotifyEvent.EVENT_ID,
            ContextNotifyEvent.warning(
                title='声音闪避已停用',
                content=f'音频录制异常，请检查音频设备/独占模式/默认输出设备：{error}',
            ),
        )

    def init_auto_op(
            self,
            auto_op: AutoBattleOperator,
    ) -> None:
        """
        加载自动战斗操作器时的动作
        """
        self._check_dodge_interval = auto_op.check_dodge_interval
        self._check_audio_interval = 0.02

        use_gpu = self.ctx.model_config.flash_classifier_gpu
        if self._flash_model is None or self._flash_model.gpu != use_gpu:
            self._flash_model = FlashClassifier(
                model_name=self.ctx.model_config.flash_classifier,
                backup_model_name=self.ctx.model_config.flash_classifier_backup,
                model_parent_dir_path=yolo_config_utils.get_model_category_dir('flash_classifier'),
                gh_proxy=self.ctx.env_config.is_gh_proxy,
                gh_proxy_url=self.ctx.env_config.gh_proxy_url if self.ctx.env_config.is_gh_proxy else None,
                personal_proxy=self.ctx.env_config.personal_proxy if self.ctx.env_config.is_personal_proxy else None,
                gpu=use_gpu
            )

    def init_battle_dodge_context(
            self,
    ) -> None:
        """
        初始化上下文，在运行前调用。
        """
        # 上一次识别的时间
        self._last_check_dodge_time = 0
        self._last_check_audio_time = 0

        # 异步加载音频模板
        _dodge_check_executor.submit(self.init_audio_template)

    def init_audio_template(self) -> None:
        """
        加载音频模板。
        """
        if self._audio_template_fft is not None:
            return
        log.info('加载声音模板中')

        template_dir = Path(os_utils.get_path_under_work_dir('assets', 'template', 'dodge_audio'))
        template_files: tuple[str, ...] = (
            'template_1.wav',
            'template_2.wav',
            'template_3.wav',
        )
        # 模板只在初始化时完成重采样、滤波和标准化，实时识别时直接复用。
        templates = [
            self._standardize_wave(
                self._get_filter_wave(self._load_audio_template(template_dir / filename))
            )
            for filename in template_files
        ]
        template_lengths = np.asarray([template.size for template in templates], dtype=np.int64)
        max_template_length = int(np.max(template_lengths))
        # 补零只用于组成二维矩阵并批量计算 FFT，相关系数仍按真实长度处理。
        template_matrix = np.zeros((len(templates), max_template_length), dtype=np.float64)
        for template_idx, template in enumerate(templates):
            template_matrix[template_idx, :template.size] = template

        audio_window_size = self._audio_recorder._sample_rate // 2
        fft_size = next_fast_len(max_template_length + audio_window_size - 1)
        corr_mask = np.zeros((len(templates), fft_size), dtype=np.bool_)
        for template_idx, template_length_value in enumerate(template_lengths):
            template_length = int(template_length_value)
            full_length = template_length + audio_window_size - 1
            if template_length > audio_window_size:
                start = (audio_window_size - 1) // 2
                stop = start + template_length
            else:
                swapped_start = (template_length - 1) // 2
                start = full_length - (swapped_start + audio_window_size)
                stop = full_length - swapped_start
            # 只保留各模板真实长度对应的 same 区间，排除矩阵补零产生的无效位置。
            corr_mask[template_idx, start:stop] = True

        self._audio_fft_size = fft_size
        self._audio_corr_mask = corr_mask
        # 分母使用模板和录音的真实较长长度，保持与旧相关系数算法一致。
        self._audio_corr_denominator = np.maximum(
            template_lengths,
            audio_window_size,
        ).astype(np.float64)
        # 缓存三个模板的频域数据，实时识别时不再重复计算模板 FFT。
        self._audio_template_fft = rfft(template_matrix, n=fft_size, axis=1)

        log.info('加载声音模板完成')

    def _load_audio_template(self, template_path: Path) -> np.ndarray:
        """读取模板并转换为录音使用的采样率和单声道。"""
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', WavFileWarning)
            sample_rate, audio = wavfile.read(template_path)

        # 将不同 WAV 数据类型统一换算为浮点波形。
        if np.issubdtype(audio.dtype, np.unsignedinteger):
            audio_type_info = np.iinfo(audio.dtype)
            midpoint = float(audio_type_info.max + 1) / 2
            audio = (audio.astype(np.float64) - midpoint) / midpoint
        elif np.issubdtype(audio.dtype, np.signedinteger):
            max_value = float(max(abs(np.iinfo(audio.dtype).min), np.iinfo(audio.dtype).max))
            audio = audio.astype(np.float64) / max_value
        else:
            audio = audio.astype(np.float64)

        # 模板与实时录音都使用单声道，双声道模板逐帧取平均值。
        if audio.ndim == 2:
            audio = np.mean(audio, axis=1)
        elif audio.ndim != 1:
            raise ValueError(f'不支持的音频维度: {audio.ndim}')

        target_sample_rate = self._audio_recorder._sample_rate
        if sample_rate != target_sample_rate:
            # 使用整数倍率的多相滤波重采样，避免引入 librosa 依赖。
            common_divisor = gcd(sample_rate, target_sample_rate)
            audio = resample_poly(
                audio,
                target_sample_rate // common_divisor,
                sample_rate // common_divisor,
            )
        return audio

    def check_dodge_flash(
        self,
        screen: MatLike,
        screenshot_time: float,
        audio_future: Future[AudioTemplateEnum | Literal[False]] | None = None,
    ) -> bool:
        """
        识别画面是否有闪光。
        :param screen: 屏幕截图
        :param screenshot_time: 截图时间
        :param audio_future: 音频识别结果的Future对象
        :return: 是否应该闪避 （识别到闪光或者声音）
        """
        if not self._check_dodge_flash_lock.acquire(blocking=False):
            return False

        try:
            if screenshot_time - self._last_check_dodge_time < cal_utils.random_in_range(self._check_dodge_interval):
                # 还没有达到识别间隔
                return False

            self._last_check_dodge_time = screenshot_time

            result = self._flash_model.run(screen)
            state_name: str | None = None
            if result.class_idx == 1:
                state_name = YoloStateEventEnum.DODGE_RED.value
            elif result.class_idx == 2:
                state_name = YoloStateEventEnum.DODGE_YELLOW.value
            elif audio_future is not None:
                audio_result = audio_future.result()
                # 普通闪避和 X 黄光需要触发闪避状态，紫光只分类、不触发操作。
                if audio_result in (AudioTemplateEnum.NORMAL_DODGE, AudioTemplateEnum.X_DODGE):
                    state_name = YoloStateEventEnum.DODGE_AUDIO.value

            should_dodge = state_name is not None
            if should_dodge:
                self.ctx.auto_battle_context.state_record_service.update_state(StateRecord(state_name, screenshot_time))

            return should_dodge
        except Exception:
            log.error('识别画面闪光失败', exc_info=True)
            return False
        finally:
            self._check_dodge_flash_lock.release()

    def check_dodge_audio(self, screenshot_time: float) -> AudioTemplateEnum | Literal[False]:
        """
        识别音频是否有闪避提示。
        :param screenshot_time: 截图时间
        :return: 命中的模板编号，未命中时返回 False
        """
        if not self._check_audio_lock.acquire(blocking=False):
            return False

        try:
            if screenshot_time - self._last_check_audio_time < cal_utils.random_in_range(self._check_audio_interval):
                # 还没有达到识别间隔
                return False
            if self._audio_template_fft is None:
                return False
            self._last_check_audio_time = screenshot_time

            latest_audio = self._audio_recorder.get_latest_audio()
            if latest_audio.size == 0:
                return False

            corr = self.get_max_corr(latest_audio)
            # 多个模板同时过阈值时，只采用相关系数最高的分类结果。
            matched_idx = int(np.argmax(corr))
            max_corr = float(corr[matched_idx])

            # 记录命中时间并清空当前录音缓冲区
            if max_corr > self._audio_recorder.trigger_threshold:
                self._last_audio_event_time = screenshot_time
                self._audio_recorder.clear_audio()
                return AudioTemplateEnum(matched_idx + 1)

            return False
        except Exception:
            log.error('识别闪避声音失败', exc_info=True)
            return False
        finally:
            self._check_audio_lock.release()

    def get_max_corr(self, y: np.ndarray) -> np.ndarray:
        """
        计算三个模板与录音的最大相关系数。
        :param y: 待识别的录音
        :return: 三个模板各自的最大相关系数
        """
        if (
            self._audio_template_fft is None
            or self._audio_corr_mask is None
            or self._audio_corr_denominator is None
        ):
            raise RuntimeError('声音模板尚未加载')
        audio_window_size = self._audio_recorder._sample_rate // 2
        if y.ndim != 1 or y.size != audio_window_size:
            raise ValueError(f'录音长度必须为 {audio_window_size}')

        wy = self._standardize_wave(self._get_filter_wave(y))
        # 录音只计算一次 FFT，再与三个模板频域数据广播相乘并批量逆变换。
        audio_fft = rfft(wy[::-1], n=self._audio_fft_size)
        correlation = irfft(
            self._audio_template_fft * audio_fft[np.newaxis, :],
            n=self._audio_fft_size,
            axis=1,
        )
        max_correlation = np.max(
            correlation,
            axis=1,
            where=self._audio_corr_mask,
            initial=-np.inf,
        )
        # 掩码已排除补零区域，这里按三个模板的真实分母分别归一化。
        return max_correlation / self._audio_corr_denominator

    @staticmethod
    def _standardize_wave(x: np.ndarray) -> np.ndarray:
        """按标准差缩放波形，保持与旧算法一致。"""
        standard_deviation = float(np.std(x))
        if standard_deviation < np.finfo(np.float64).eps * 10:
            return np.zeros_like(x, dtype=np.float64)
        return x / standard_deviation

    def _get_filter_wave(self, x: np.ndarray) -> np.ndarray:
        """
        音频滤波。
        :param x: 音频信号x
        :return: 滤波后波形
        """
        wx = filtfilt(self._audio_recorder.filter_b,
                      self._audio_recorder.filter_a,
                      x)
        return wx

    def start_context_async(self) -> None:
        """
        启动上下文，启动音频录制。
        """
        self._audio_recorder.start_running_async()

    def stop_context(self) -> None:
        """
        停止上下文，停止音频录制。
        """
        self._audio_recorder.stop_running()

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        """
        _dodge_check_executor.shutdown(wait=False, cancel_futures=True)
