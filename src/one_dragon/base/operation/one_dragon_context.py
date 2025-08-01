import logging
from enum import Enum
from pynput import keyboard, mouse
from typing import Optional

from one_dragon.base.config.custom_config import CustomConfig, UILanguageEnum
from one_dragon.base.config.game_account_config import GameAccountConfig
from one_dragon.base.config.one_dragon_app_config import OneDragonAppConfig
from one_dragon.base.config.one_dragon_config import OneDragonConfig
from one_dragon.base.config.push_config import PushConfig
from one_dragon.base.operation.context_lazy_signal import ContextLazySignal
from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.controller.pc_button.pc_button_listener import PcButtonListener
from one_dragon.base.matcher.ocr.ocr_matcher import OcrMatcher
from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher, OnnxOcrParam
from one_dragon.base.matcher.ocr.ocr_service import OcrService
from one_dragon.base.matcher.template_matcher import TemplateMatcher
from one_dragon.base.operation.context_event_bus import ContextEventBus
from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext, ONE_DRAGON_CONTEXT_EXECUTOR
from one_dragon.base.screen.screen_loader import ScreenContext
from one_dragon.base.screen.template_loader import TemplateLoader
from one_dragon.utils import debug_utils, i18_utils, log_utils
from one_dragon.utils import thread_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class ContextRunStateEnum(Enum):

    STOP: int = 0  # 停止
    RUN: int = 1  # 正在运行
    PAUSE: int = 2  # 暂停


class ContextRunningStateEventEnum(Enum):
    """
    运行状态相关的事件 事件体为 ContextRunStateEnum
    """

    START_RUNNING: str = 'context_start_running'
    PAUSE_RUNNING: str = 'context_pause_running'
    RESUME_RUNNING: str = 'context_resume_running'
    STOP_RUNNING: str = 'context_stop_running'


class ContextKeyboardEventEnum(Enum):

    PRESS: str = 'context_keyboard_press'


class ContextInstanceEventEnum(Enum):

    instance_active: str = 'instance_active'


class OneDragonContext(ContextEventBus, OneDragonEnvContext):

    def __init__(self, controller: Optional[ControllerBase] = None):
        ContextEventBus.__init__(self)
        OneDragonEnvContext.__init__(self)

        self.one_dragon_config: OneDragonConfig = OneDragonConfig()
        self.custom_config: CustomConfig = CustomConfig()
        self.signal: ContextLazySignal = ContextLazySignal()

        if self.one_dragon_config.current_active_instance is None:
            self.one_dragon_config.create_new_instance(True)
        self.current_instance_idx = self.one_dragon_config.current_active_instance.idx

        self.context_running_state: ContextRunStateEnum = ContextRunStateEnum.STOP

        self.screen_loader: ScreenContext = ScreenContext()
        self.template_loader: TemplateLoader = TemplateLoader()
        self.tm: TemplateMatcher = TemplateMatcher(self.template_loader)
        self.ocr: OcrMatcher = OnnxOcrMatcher(
            OnnxOcrParam(
                det_limit_side_len=max(self.project_config.screen_standard_width, self.project_config.screen_standard_height),
            )
        )
        self.ocr_service: OcrService | None = None  # 延迟初始化
        self.controller: ControllerBase = controller

        self.keyboard_controller = keyboard.Controller()
        self.mouse_controller = mouse.Controller()
        self.btn_listener = PcButtonListener(on_button_tap=self._on_key_press, listen_keyboard=True, listen_mouse=True)
        self.btn_listener.start()

    def init_by_config(self) -> None:
        """
        根据配置进行初始化
        不能在 __init__ 中调用，因为子类可能还没有完成初始化
        :return:
        """
        if self.custom_config.ui_language == UILanguageEnum.AUTO.value.value:
            i18_utils.detect_and_set_default_language()
        else:
            i18_utils.update_default_lang(self.custom_config.ui_language)
        log_utils.set_log_level(logging.DEBUG if self.env_config.is_debug else logging.INFO)

    def start_running(self) -> bool:
        """
        开始运行
        :return:
        """
        if self.context_running_state != ContextRunStateEnum.STOP:
            log.error('请先结束其他运行中的功能 再启动')
            return False

        self.context_running_state = ContextRunStateEnum.RUN
        self.controller.init_before_context_run()
        self.dispatch_event(ContextRunningStateEventEnum.START_RUNNING.value, self.context_running_state)
        return True

    def stop_running(self):
        if self.is_context_running:  # 先触发暂停 让执行中的指令停止
            self.switch_context_pause_and_run()
        self.context_running_state = ContextRunStateEnum.STOP
        log.info('停止运行')
        self.dispatch_event(ContextRunningStateEventEnum.STOP_RUNNING.value, self.context_running_state)

    @property
    def is_context_stop(self) -> bool:
        return self.context_running_state == ContextRunStateEnum.STOP

    @property
    def is_context_running(self) -> bool:
        return self.context_running_state == ContextRunStateEnum.RUN

    @property
    def is_context_pause(self) -> bool:
        return self.context_running_state == ContextRunStateEnum.PAUSE

    @property
    def context_running_status_text(self) -> str:
        if self.context_running_state == ContextRunStateEnum.STOP:
            return gt('空闲')
        elif self.context_running_state == ContextRunStateEnum.RUN:
            return gt('运行中')
        elif self.context_running_state == ContextRunStateEnum.PAUSE:
            return gt('暂停中')
        else:
            return gt('未知')

    def switch_context_pause_and_run(self):
        if self.context_running_state == ContextRunStateEnum.RUN:
            log.info('暂停运行')
            self.context_running_state = ContextRunStateEnum.PAUSE
            self.dispatch_event(ContextRunningStateEventEnum.PAUSE_RUNNING.value, self.context_running_state)
        elif self.context_running_state == ContextRunStateEnum.PAUSE:
            log.info('恢复运行')
            self.context_running_state = ContextRunStateEnum.RUN
            self.dispatch_event(ContextRunningStateEventEnum.RESUME_RUNNING.value, self.context_running_state)

    def _on_key_press(self, key: str):
        """
        按键时触发 抛出事件，事件体为按键
        :param key: 按键
        :return:
        """
        # log.info('按键 %s' % key)
        if key == self.key_start_running:
            self.switch_context_pause_and_run()
        elif key == self.key_stop_running:
            self.stop_running()
        elif key == self.key_screenshot:
            self.screenshot_and_save_debug(self.env_config.copy_screenshot)

        self.dispatch_event(ContextKeyboardEventEnum.PRESS.value, key)

    @property
    def is_game_window_ready(self) -> bool:
        """
        游戏窗口是否已经出现
        :return:
        """
        return self.controller.is_game_window_ready

    @property
    def key_start_running(self) -> str:
        return self.env_config.key_start_running

    @property
    def key_stop_running(self) -> str:
        return self.env_config.key_stop_running

    @property
    def key_screenshot(self) -> str:
        return self.env_config.key_screenshot

    @property
    def key_debug(self) -> str:
        return self.env_config.key_debug

    def screenshot_and_save_debug(self, copy_screenshot: bool) -> None:
        """
        截图 保存到debug
        """
        if self.controller is None or not self.controller.is_game_window_ready:
            return
        if self.controller.game_win is not None:
            self.controller.game_win.active()
        _, img = self.controller.screenshot(independent=True)
        debug_utils.save_debug_image(img, copy_screenshot=copy_screenshot)

    def switch_instance(self, instance_idx: int) -> None:
        """
        切换实例
        :param instance_idx:
        :return:
        """
        self.one_dragon_config.active_instance(instance_idx)
        self.current_instance_idx = self.one_dragon_config.current_active_instance.idx
        self.load_instance_config()
        self.dispatch_event(ContextInstanceEventEnum.instance_active.value, instance_idx)

    def load_instance_config(self):
        log.info('开始加载实例配置 %d' % self.current_instance_idx)
        self.one_dragon_app_config: OneDragonAppConfig = OneDragonAppConfig(self.current_instance_idx)
        self.game_account_config: GameAccountConfig = GameAccountConfig(self.current_instance_idx)
        self.push_config: PushConfig = PushConfig(self.current_instance_idx)

    def async_init_ocr(self) -> None:
        """
        异步初始化OCR
        :return:
        """
        f = ONE_DRAGON_CONTEXT_EXECUTOR.submit(self.init_ocr)
        f.add_done_callback(thread_utils.handle_future_result)

    def init_ocr(self) -> None:
        """
        初始化OCR
        :return:
        """
        self.ocr.init_model(
            ghproxy_url=self.env_config.gh_proxy_url if self.env_config.is_gh_proxy else None,
            proxy_url=self.env_config.personal_proxy if self.env_config.is_personal_proxy else None,
        )

        # 初始化OCR缓存服务
        if self.ocr_service is None:
            self.ocr_service = OcrService(ocr_matcher=self.ocr)
        else:
            self.ocr_service.ocr_matcher = self.ocr

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        @return:
        """
        self.btn_listener.stop()
        self.controller.cleanup_after_app_shutdown()
        self.one_dragon_config.clear_temp_instance_indices()
        self.one_dragon_app_config.clear_temp_app_run_list()
        ContextEventBus.after_app_shutdown(self)
        OneDragonEnvContext.after_app_shutdown(self)
