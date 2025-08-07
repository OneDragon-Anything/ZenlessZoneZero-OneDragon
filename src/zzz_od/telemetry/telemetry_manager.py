"""
遥测管理器
统一管理所有遥测组件，提供简单的API接口
"""
import logging
import platform
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from .models import TelemetryConfig, PrivacySettings
from .config import TelemetryConfigLoader, PrivacySettingsManager
from .posthog_client import PostHogClient
from .privacy_controller import PrivacyController
from .data_sanitizer import DataSanitizer
from .ui_support import TelemetryUISupport
from .event_collector import EventCollector
from .error_tracker import ErrorTracker
from .performance_monitor import PerformanceMonitor


logger = logging.getLogger(__name__)


class TelemetryManager:
    """遥测管理器"""

    def __init__(self, context):
        """
        初始化遥测管理器

        Args:
            context: OneDragon上下文对象
        """
        self.ctx = context
        self._initialized = False
        self._user_id: Optional[str] = None
        self._session_id = str(uuid.uuid4())

        # 配置管理
        from one_dragon.utils import os_utils
        config_dir = Path(os_utils.get_work_dir()) / "config"
        self.config_loader = TelemetryConfigLoader(config_dir)
        self.privacy_manager = PrivacySettingsManager(config_dir)

        # 组件
        self.config: Optional[TelemetryConfig] = None
        self.privacy_settings: Optional[PrivacySettings] = None
        self.posthog_client: Optional[PostHogClient] = None
        self.privacy_controller: Optional[PrivacyController] = None
        self.data_sanitizer: Optional[DataSanitizer] = None
        self.ui_support: Optional[TelemetryUISupport] = None
        self.event_collector: Optional[EventCollector] = None
        self.error_tracker: Optional[ErrorTracker] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None

    def initialize(self) -> bool:
        """初始化遥测系统"""
        try:
            logger.debug("Initializing telemetry system...")

            # 加载配置
            self.config = self.config_loader.load_config()
            self.privacy_settings = self.privacy_manager.load_privacy_settings()

            # 检查是否启用遥测
            if not self.config.enabled:
                logger.debug("Telemetry is disabled by configuration")
                return True

            logger.debug("Telemetry is enabled, initializing components...")

            # 初始化隐私控制器和数据清理器
            from one_dragon.utils import os_utils
            config_dir = Path(os_utils.get_work_dir()) / "config"
            self.privacy_controller = PrivacyController(config_dir)
            self.data_sanitizer = DataSanitizer()
            self.ui_support = TelemetryUISupport(self.privacy_controller)

            # 初始化PostHog客户端
            logger.debug("Initializing PostHog client...")
            self.posthog_client = PostHogClient(self.config)
            if not self.posthog_client.initialize():
                logger.warning("Failed to initialize PostHog client")
                return False

            logger.debug("PostHog client initialized successfully")

            # 生成用户ID（在创建 EventCollector 之前）
            self._user_id = self._generate_user_id()

            # 初始化核心遥测组件
            logger.debug("Initializing telemetry components...")
            self.event_collector = EventCollector(self.posthog_client, self.privacy_controller, self._user_id)
            self.error_tracker = ErrorTracker(self.posthog_client, self.privacy_controller)
            self.performance_monitor = PerformanceMonitor(self.posthog_client, self.privacy_controller)

            # 设置全局异常处理器
            self.error_tracker.setup_exception_handler()

            # 开始系统监控（降低频率，避免过多日志）
            self.performance_monitor.start_system_monitoring(interval=30.0)

            self._initialized = True
            logger.debug("Telemetry system initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize telemetry system: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _generate_user_id(self) -> str:
        """生成匿名用户ID"""
        try:
            # 使用机器特征生成稳定的匿名ID
            machine_id = f"{platform.node()}-{platform.machine()}"
            # 这里可以添加更多的机器特征，但要注意隐私
            user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, machine_id))
            logger.debug(f"Generated anonymous user ID: {user_id[:8]}...")
            return user_id
        except Exception as e:
            # 如果生成失败，使用随机ID
            logger.warning(f"Failed to generate user ID from machine features: {e}")
            user_id = str(uuid.uuid4())
            logger.debug(f"Using random user ID: {user_id[:8]}...")
            return user_id

    def is_enabled(self) -> bool:
        """检查遥测是否启用"""
        return (
            self._initialized and
            self.config and
            self.config.enabled and
            self.posthog_client and
            self.posthog_client._initialized
        )

    def capture_event(self, event_name: str, properties: Dict[str, Any] = None) -> None:
        """捕获事件"""
        if not self.is_enabled() or not self._user_id:
            return

        try:
            # 添加通用属性
            event_properties = {
                'session_id': self._session_id,
                'app_version': getattr(self.ctx.project_config, 'version', '2.0.0'),
                **(properties or {})
            }

            # 隐私控制和数据处理
            if self.privacy_controller:
                processed_properties = self.privacy_controller.process_event_data(event_name, event_properties)
                if processed_properties is None:
                    logger.debug(f"Event {event_name} blocked by privacy settings")
                    return
                event_properties = processed_properties

            # 数据清理
            if self.data_sanitizer:
                event_properties = self.data_sanitizer.sanitize_event_properties(event_properties)

            self.posthog_client.capture(
                distinct_id=self._user_id,
                event=event_name,
                properties=event_properties
            )

            logger.debug(f"Captured event: {event_name}")

        except Exception as e:
            logger.error(f"Failed to capture event {event_name}: {e}")

    def capture_error(self, error: Exception, context: Dict[str, Any] = None) -> None:
        """捕获错误"""
        if not self.is_enabled():
            return

        try:
            import traceback

            error_data = {
                'error_type': type(error).__name__,
                'error_message': str(error),
                'stack_trace': traceback.format_exc(),
                'context': context or {},
                'session_id': self._session_id,
                'app_version': getattr(self.ctx.project_config, 'version', '2.0.0'),
            }

            # 隐私控制检查
            if self.privacy_controller and not self.privacy_controller.is_error_reporting_enabled():
                logger.debug("Error reporting disabled by privacy settings")
                return

            # 数据清理
            if self.data_sanitizer:
                error_data = self.data_sanitizer.sanitize_error_data(error_data)

            # 隐私过滤
            if self.privacy_controller:
                error_data = self.privacy_controller.filter_sensitive_info(error_data)

            self.posthog_client.capture(
                distinct_id=self._user_id,
                event='error_occurred',
                properties=error_data
            )

            logger.debug(f"Captured error: {type(error).__name__}")

        except Exception as e:
            logger.error(f"Failed to capture error: {e}")

    def capture_performance(self, metric_name: str, value: float, tags: Dict[str, Any] = None) -> None:
        """捕获性能指标"""
        if not self.is_enabled():
            return

        try:
            performance_properties = {
                'metric_name': metric_name,
                'metric_value': value,
                'session_id': self._session_id,
                'app_version': getattr(self.ctx.project_config, 'version', '2.0.0'),
                **(tags or {})
            }

            self.posthog_client.capture(
                distinct_id=self._user_id,
                event='performance_metric',
                properties=performance_properties
            )

            logger.debug(f"Captured performance metric: {metric_name} = {value}")

        except Exception as e:
            logger.error(f"Failed to capture performance metric: {e}")

    def identify_user(self, user_id: str, properties: Dict[str, Any] = None) -> None:
        """识别用户"""
        if not self.is_enabled():
            return

        try:
            self.posthog_client.identify(
                distinct_id=user_id,
                properties=properties or {}
            )

            # 关联旧的匿名ID
            if self._user_id and self._user_id != user_id:
                self.posthog_client.alias(self._user_id, user_id)

            self._user_id = user_id
            logger.debug(f"Identified user: {user_id}")

        except Exception as e:
            logger.error(f"Failed to identify user: {e}")

    def set_user_properties(self, properties: Dict[str, Any]) -> None:
        """设置用户属性"""
        if not self.is_enabled() or not self._user_id:
            return

        try:
            self.posthog_client.set_user_properties(self._user_id, properties)
            logger.debug("Set user properties")

        except Exception as e:
            logger.error(f"Failed to set user properties: {e}")

    def flush(self) -> None:
        """立即刷新所有待发送的数据"""
        if self.posthog_client:
            self.posthog_client.flush()

    def shutdown(self) -> None:
        """关闭遥测系统"""
        logger.debug("Shutting down telemetry system...")

        try:
            # 强制刷新所有待发送的事件
            if self.is_enabled():
                logger.debug("Flushing all pending events before shutdown...")
                self.flush()

                # 记录应用关闭事件
                if self.event_collector:
                    session_duration = self._get_session_duration()
                    self.event_collector.track_app_shutdown(session_duration, clean_shutdown=True)

                # 再次强制刷新，确保关闭事件也被发送
                self.flush()

            # 关闭核心组件
            if self.performance_monitor:
                self.performance_monitor.shutdown()

            if self.error_tracker:
                self.error_tracker.shutdown()

            # 关闭PostHog客户端（这会再次刷新队列）
            if self.posthog_client:
                self.posthog_client.shutdown()

            self._initialized = False
            logger.debug("Telemetry system shutdown complete")

        except Exception as e:
            logger.error(f"Error during telemetry shutdown: {e}")

    def _get_session_duration(self) -> float:
        """获取会话持续时间（秒）"""
        # 这里需要记录会话开始时间，暂时返回0
        return 0.0

    def update_privacy_settings(self, settings: Dict[str, Any]) -> bool:
        """更新隐私设置"""
        if self.privacy_controller:
            return self.privacy_controller.update_privacy_settings(settings)
        return False

    def get_privacy_settings(self) -> Dict[str, Any]:
        """获取隐私设置"""
        if self.privacy_controller:
            return self.privacy_controller.get_privacy_settings()
        return {}

    def clear_local_data(self) -> bool:
        """清除本地遥测数据"""
        if self.privacy_controller:
            return self.privacy_controller.clear_local_data()
        return False

    def export_user_data(self) -> Dict[str, Any]:
        """导出用户数据"""
        if self.privacy_controller:
            return self.privacy_controller.export_user_data()
        return {}

    def get_privacy_options(self) -> Dict[str, Any]:
        """获取隐私选项配置"""
        if self.ui_support:
            return self.ui_support.get_privacy_options()
        return {}

    def get_privacy_summary(self) -> Dict[str, Any]:
        """获取隐私设置摘要"""
        if self.ui_support:
            return self.ui_support.get_privacy_summary()
        return {}

    def apply_privacy_settings(self, settings: Dict[str, Any]) -> tuple[bool, str]:
        """应用隐私设置"""
        if self.ui_support:
            return self.ui_support.apply_privacy_settings(settings)
        return False, "UI support not available"

    def get_data_examples(self) -> Dict[str, Any]:
        """获取数据收集示例"""
        if self.ui_support:
            return self.ui_support.get_data_examples()
        return {}

    def export_privacy_report(self) -> Dict[str, Any]:
        """导出隐私报告"""
        if self.ui_support:
            return self.ui_support.export_privacy_report()
        return {}

    # 事件收集器方法
    def track_app_launch(self, launch_time: float, version: str = None) -> None:
        """跟踪应用启动"""
        if self.event_collector:
            app_version = version or getattr(self.ctx.project_config, 'version', '2.0.0')
            self.event_collector.track_app_launch(launch_time, app_version)

    def track_navigation(self, from_screen: str, to_screen: str, duration: float = None) -> None:
        """跟踪页面导航"""
        if self.event_collector:
            self.event_collector.track_navigation(from_screen, to_screen, duration)

    def track_ui_interaction(self, element: str, action: str, context: Dict[str, Any] = None) -> None:
        """跟踪UI交互"""
        if self.event_collector:
            self.event_collector.track_ui_interaction(element, action, context)

    def track_feature_usage(self, feature: str, usage_data: Dict[str, Any] = None) -> None:
        """跟踪功能使用"""
        if self.event_collector:
            self.event_collector.track_feature_usage(feature, usage_data)

    def track_automation_start(self, automation_type: str, config: Dict[str, Any] = None) -> None:
        """跟踪自动化开始"""
        if self.event_collector:
            self.event_collector.track_automation_start(automation_type, config)

    def track_automation_end(self, automation_type: str, duration: float, success: bool,
                           result_data: Dict[str, Any] = None) -> None:
        """跟踪自动化结束"""
        if self.event_collector:
            self.event_collector.track_automation_end(automation_type, duration, success, result_data)

    # 错误追踪器方法
    def add_breadcrumb(self, message: str, category: str, level: str = "info",
                      data: Dict[str, Any] = None) -> None:
        """添加面包屑"""
        if self.error_tracker:
            self.error_tracker.add_breadcrumb(message, category, level, data)

    def track_operation_start(self, operation_name: str, context: Dict[str, Any] = None) -> None:
        """跟踪操作开始"""
        if self.error_tracker:
            self.error_tracker.track_operation_start(operation_name, context)

    def track_operation_end(self, operation_name: str, success: bool,
                          duration: float = None, result: Dict[str, Any] = None) -> None:
        """跟踪操作结束"""
        if self.error_tracker:
            self.error_tracker.track_operation_end(operation_name, success, duration, result)

    # 性能监控器方法
    def track_startup_time(self, startup_duration: float, components: Dict[str, float] = None) -> None:
        """跟踪应用启动时间"""
        if self.performance_monitor:
            self.performance_monitor.track_startup_time(startup_duration, components)

    def track_operation_time(self, operation: str, duration: float, success: bool,
                           metadata: Dict[str, Any] = None) -> None:
        """跟踪操作执行时间"""
        if self.performance_monitor:
            self.performance_monitor.track_operation_time(operation, duration, success, metadata)

    def track_memory_usage(self, usage_mb: float, peak_mb: float = None, component: str = None) -> None:
        """跟踪内存使用"""
        if self.performance_monitor:
            self.performance_monitor.track_memory_usage(usage_mb, peak_mb, component)

    def track_image_recognition_performance(self, processing_time: float, accuracy: float = None,
                                          algorithm: str = None, image_size: str = None) -> None:
        """跟踪图像识别性能"""
        if self.performance_monitor:
            self.performance_monitor.track_image_recognition_performance(
                processing_time, accuracy, algorithm, image_size)

    def start_timer(self, timer_name: str, metadata: Dict[str, Any] = None) -> None:
        """开始计时器"""
        if self.performance_monitor:
            self.performance_monitor.start_timer(timer_name, metadata)

    def stop_timer(self, timer_name: str, success: bool = True,
                  additional_metadata: Dict[str, Any] = None) -> Optional[float]:
        """停止计时器"""
        if self.performance_monitor:
            return self.performance_monitor.stop_timer(timer_name, success, additional_metadata)
        return None

    def measure_time(self, operation_name: str, metadata: Dict[str, Any] = None):
        """上下文管理器形式的计时器"""
        if self.performance_monitor:
            return self.performance_monitor.measure_time(operation_name, metadata)
        else:
            # 返回一个空的上下文管理器
            from contextlib import nullcontext
            return nullcontext()

    def get_health_status(self) -> Dict[str, Any]:
        """获取遥测系统健康状态"""
        status = {
            'initialized': self._initialized,
            'enabled': self.is_enabled(),
            'user_id': self._user_id,
            'session_id': self._session_id
        }

        if self.posthog_client:
            status.update(self.posthog_client.get_health_status())

        if self.privacy_controller:
            status['privacy_settings'] = self.privacy_controller.get_privacy_settings()

        if self.data_sanitizer:
            status['sanitization_stats'] = self.data_sanitizer.get_sanitization_stats()

        if self.event_collector:
            status['session_summary'] = self.event_collector.get_session_summary()

        if self.error_tracker:
            status['error_statistics'] = self.error_tracker.get_error_statistics()

        if self.performance_monitor:
            status['performance_summary'] = self.performance_monitor.get_performance_summary()

        return status

    def get_status(self) -> Dict[str, Any]:
        """获取遥测系统状态（get_health_status的别名）"""
        return self.get_health_status()
