import inspect
import logging
import threading
from enum import Enum
from functools import cached_property
from pathlib import Path

from pynput import keyboard

from one_dragon.base.config.basic_model_config import BasicModelConfig
from one_dragon.base.config.custom_config import UILanguageEnum
from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.controller.pc_button.pc_button_listener import PcButtonListener
from one_dragon.base.matcher.ocr.ocr_matcher import OcrMatcher
from one_dragon.base.matcher.ocr.ocr_service import OcrService
from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher, OnnxOcrParam
from one_dragon.base.matcher.template_matcher import TemplateMatcher
from one_dragon.base.operation.application.application_factory_manager import (
    ApplicationFactoryManager,
)
from one_dragon.base.operation.application.application_group_manager import (
    ApplicationGroupManager,
)
from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
)
from one_dragon.base.operation.application.plugin_info import PluginSource
from one_dragon.base.operation.context_event_bus import ContextEventBus
from one_dragon.base.operation.context_lazy_signal import ContextLazySignal
from one_dragon.base.operation.one_dragon_env_context import (
    ONE_DRAGON_CONTEXT_EXECUTOR,
    OneDragonEnvContext,
)
from one_dragon.base.push.push_service import PushService
from one_dragon.base.screen.screen_loader import ScreenContext
from one_dragon.base.screen.template_loader import TemplateLoader
from one_dragon.utils import debug_utils, file_utils, i18_utils, log_utils, thread_utils
from one_dragon.utils.log_utils import log


class ContextKeyboardEventEnum(Enum):

    PRESS = 'context_keyboard_press'


class ContextInstanceEventEnum(Enum):

    instance_active = 'instance_active'


class OneDragonContext(ContextEventBus, OneDragonEnvContext):

    def __init__(self):
        ContextEventBus.__init__(self)
        OneDragonEnvContext.__init__(self)

        self.signal: ContextLazySignal = ContextLazySignal()

        if self.one_dragon_config.current_active_instance is None:
            self.one_dragon_config.create_new_instance(True)
        self.current_instance_idx = self.one_dragon_config.current_active_instance.idx

        self.screen_loader: ScreenContext = ScreenContext()
        self.template_loader: TemplateLoader = TemplateLoader()
        self.tm: TemplateMatcher = TemplateMatcher(self.template_loader)

        self.ocr: OcrMatcher = OnnxOcrMatcher(
            OnnxOcrParam(
                use_gpu=False,  # 目前OCR使用GPU会闪退
                det_limit_side_len=max(self.project_config.screen_standard_width, self.project_config.screen_standard_height),
            )
        )
        self.ocr_service: OcrService = OcrService(ocr_matcher=self.ocr)
        self.controller: ControllerBase | None = None

        self.keyboard_controller = keyboard.Controller()
        self.btn_listener = PcButtonListener(on_button_tap=self._on_key_press, listen_keyboard=True, listen_mouse=True)
        self.btn_listener.start()

        # 注册应用
        self.run_context: ApplicationRunContext = ApplicationRunContext(self)
        self.app_group_manager: ApplicationGroupManager = ApplicationGroupManager(self)

        self.push_service: PushService = PushService(self)

        # 初始化相关
        self._init_lock = threading.Lock()
        self._application_registered: bool = False  # 应用是否注册完毕
        self.ready_for_application: bool = False  # 初始化完成 可以运行应用了

    #------------------- 需要懒加载的都使用 @cached_property -------------------#

    #------------------- 以下是 应用工厂相关 -------------------#

    @cached_property
    def application_plugin_dirs(self) -> list[tuple[Path, PluginSource]]:
        """
        应用插件目录列表

        默认返回：
        1. 子类所在目录的同级 'application' 目录（内置应用）
        2. 项目根目录下的 'plugins' 目录（外部插件，支持相对导入）

        例如：如果子类在 zzz_od/context/zzz_context.py，则返回：
        - (zzz_od/application, BUILTIN)
        - ({project_root}/plugins, THIRD_PARTY)

        Returns:
            list[tuple[Path, PluginSource]]: 应用插件目录列表
        """
        dirs: list[tuple[Path, PluginSource]] = []

        # 获取实际子类的定义文件
        cls_file = inspect.getfile(self.__class__)
        parent_dir = Path(cls_file).parent.parent

        # 计算 application 目录：子类文件所在目录的上级目录下的 application 目录
        # 例如：zzz_od/context/zzz_context.py -> zzz_od/application
        application_dir = parent_dir / 'application'
        if application_dir.is_dir():
            dirs.append((application_dir, PluginSource.BUILTIN))

        # 计算项目根目录下的 plugins 目录（外部插件）
        # 从 src 目录往上一级就是项目根目录
        src_dir = file_utils.find_src_dir(cls_file)
        if src_dir is not None:
            project_root = src_dir.parent
            plugins_dir = project_root / 'plugins'
            if plugins_dir.is_dir():
                dirs.append((plugins_dir, PluginSource.THIRD_PARTY))

        return dirs

    @cached_property
    def factory_manager(self) -> ApplicationFactoryManager:
        """应用工厂管理器"""
        return ApplicationFactoryManager(self, self.application_plugin_dirs)

    #------------------- 以下是 游戏/脚本级别的 -------------------#

    @cached_property
    def one_dragon_config(self):
        from one_dragon.base.config.one_dragon_config import OneDragonConfig
        return OneDragonConfig()

    @cached_property
    def custom_config(self):
        from one_dragon.base.config.custom_config import CustomConfig
        return CustomConfig()

    @cached_property
    def cv_service(self):
        from one_dragon.base.cv_process.cv_service import CvService
        return CvService(self)

    @cached_property
    def model_config(self) -> BasicModelConfig:
        return BasicModelConfig()

    #------------------- 以下是 账号实例级别的 需要在 reload_instance_config 中刷新 -------------------#

    @cached_property
    def game_account_config(self):
        from one_dragon.base.config.game_account_config import GameAccountConfig
        return GameAccountConfig(self.current_instance_idx)

    @cached_property
    def notify_config(self):
        from one_dragon.base.config.notify_config import NotifyConfig
        return NotifyConfig(self.current_instance_idx, self.run_context.notify_app_map)

    #------------------- 以下是 应用注册相关 -------------------#

    def register_application_factory(self) -> None:
        """注册应用

        使用工厂管理器自动扫描和注册应用工厂。
        """
        # 发现并注册应用
        non_default_factories, default_factories = self.factory_manager.discover_factories()

        if non_default_factories:
            self.run_context.registry_application(non_default_factories, default_group=False)

        if default_factories:
            self.run_context.registry_application(default_factories, default_group=True)

    def refresh_application_registration(self) -> None:
        """刷新应用注册

        重新扫描插件目录，刷新所有应用的注册。
        可在运行时调用以加载新的应用或更新已有应用。
        """
        log.info("开始刷新应用注册...")

        # 清空现有注册
        self.run_context.clear_applications()

        # 重新发现并注册
        non_default_factories, default_factories = self.factory_manager.discover_factories(reload_modules=True)

        if non_default_factories:
            self.run_context.registry_application(non_default_factories, default_group=False)

        if default_factories:
            self.run_context.registry_application(default_factories, default_group=True)

        # 更新默认应用组
        self.app_group_manager.set_default_apps(self.run_context.default_group_apps)

        # 清除应用组配置缓存，使其重新加载
        self.app_group_manager.clear_config_cache()

        # 刷新通知配置中的应用映射
        if 'notify_config' in self.__dict__:
            del self.__dict__['notify_config']

        log.info("应用注册刷新完成")

    #------------------- 以下是 初始化相关 -------------------#

    def init(self) -> None:
        if not self._init_lock.acquire(blocking=False):
            return

        try:
            self.ready_for_application = False

            if self.custom_config.ui_language == UILanguageEnum.AUTO.value.value:
                i18_utils.detect_and_set_default_language()
            else:
                i18_utils.update_default_lang(self.custom_config.ui_language)

            log_utils.set_log_level(logging.DEBUG if self.env_config.is_debug else logging.INFO)

            if not self._application_registered:  # 只需要注册一次
                self.register_application_factory()
                self.app_group_manager.set_default_apps(self.run_context.default_group_apps)
                self._application_registered = True

            self.init_ocr()

            self.screen_loader.reload()

            # 账号实例层级的配置 不是应用特有的配置
            self.reload_instance_config()

            # 初始化控制器
            self.init_controller()

            self.init_for_application()

            self.ready_for_application = True

            self.run_context.check_and_update_all_run_record(self.current_instance_idx)

            self.push_service.init_push_channels()

            self.gh_proxy_service.update_proxy_url()

            self.init_others()
        except Exception:
            log.error('识别连携技出错', exc_info=True)
        finally:
            self._init_lock.release()

    def init_controller(self) -> None:
        """
        初始化控制器
        由子类自行实现
        """
        pass

    def init_for_application(self) -> None:
        """
        执行应用前 还需要做的初始化
        应该加载游戏级别
        由子类自行实现
        """
        pass

    def init_others(self) -> None:
        """
        其他非必要的初始化
        由子类自行实现
        """
        pass

    def init_async(self) -> None:
        """
        异步初始化
        """
        f = ONE_DRAGON_CONTEXT_EXECUTOR.submit(self.init)
        f.add_done_callback(thread_utils.handle_future_result)

    def _on_key_press(self, key: str):
        """
        按键时触发 抛出事件，事件体为按键
        :param key: 按键
        :return:
        """
        # log.info('按键 %s' % key)
        if key == self.key_start_running:
            self.run_context.switch_context_pause_and_run()
        elif key == self.key_stop_running:
            self.run_context.stop_running()
        elif key == self.key_screenshot:
            self.screenshot_and_save_debug(self.env_config.copy_screenshot)

        self.dispatch_event(ContextKeyboardEventEnum.PRESS.value, key)

    @property
    def is_game_window_ready(self) -> bool:
        """
        游戏窗口是否已经出现
        :return:
        """
        return self.controller is not None and self.controller.is_game_window_ready

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
        self.reload_instance_config()
        self.on_switch_instance()
        self.dispatch_event(ContextInstanceEventEnum.instance_active.value, instance_idx)

    def on_switch_instance(self) -> None:
        """
        切换实例后的回调，用于更新 controller 配置
        由子类实现具体逻辑
        """
        pass

    def reload_instance_config(self):
        """
        重新加载账号实例相关的配置，不是单个应用特有的配置
        注意如果有缓存需要清理缓存
        子类需要继承加载更多的配置
        """
        log.info('开始加载实例配置 %d' % self.current_instance_idx)

        to_clear_props = [
            'game_account_config',
            'notify_config',
        ]
        for prop in to_clear_props:
            if prop in self.__dict__:
                del self.__dict__[prop]

    def init_ocr(self) -> None:
        """
        初始化OCR
        :return:
        """
        self.ocr.update_use_gpu(self.model_config.ocr_gpu)
        self.ocr.init_model(
            ghproxy_url=self.env_config.gh_proxy_url if self.env_config.is_gh_proxy else None,
            proxy_url=self.env_config.personal_proxy if self.env_config.is_personal_proxy else None,
        )

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        @return:
        """
        self.btn_listener.stop()
        if self.controller is not None:
            self.controller.cleanup_after_app_shutdown()
        self.one_dragon_config.clear_temp_instance_indices()
        ContextEventBus.after_app_shutdown(self)
        OneDragonEnvContext.after_app_shutdown(self)
        from one_dragon.base.conditional_operation.operator import ConditionalOperator
        ConditionalOperator.after_app_shutdown()
        from one_dragon.base.conditional_operation.operation_executor import OperationExecutor
        OperationExecutor.after_app_shutdown()
        from one_dragon.base.conditional_operation.state_record_service import StateRecordService
        StateRecordService.after_app_shutdown()
        from one_dragon.utils import gpu_executor
        gpu_executor.shutdown(wait=False)
