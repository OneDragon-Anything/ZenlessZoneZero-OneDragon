"""
遥测管理器
统一管理所有遥测组件，提供简单的API接口
"""
import platform
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from one_dragon.utils.log_utils import log

from .config import PrivacySettingsManager, TelemetryConfigLoader
from .data_sanitizer import DataSanitizer
from .error_tracker import ErrorTracker
from .event_collector import EventCollector
from .loki_client import LokiClient
from .models import PrivacySettings, TelemetryConfig
from .performance_monitor import PerformanceMonitor
from .privacy_controller import PrivacyController
from .ui_support import TelemetryUISupport


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
        self._app_version = self._get_app_version()

        # 配置管理
        from one_dragon.utils import os_utils
        config_dir = Path(os_utils.get_work_dir()) / "config"
        self.config_loader = TelemetryConfigLoader(config_dir)
        self.privacy_manager = PrivacySettingsManager(config_dir)

        # 组件
        self.config: Optional[TelemetryConfig] = None
        self.privacy_settings: Optional[PrivacySettings] = None
        self.loki_client: Optional[LokiClient] = None
        self.privacy_controller: Optional[PrivacyController] = None
        self.data_sanitizer: Optional[DataSanitizer] = None
        self.ui_support: Optional[TelemetryUISupport] = None
        self.event_collector: Optional[EventCollector] = None
        self.error_tracker: Optional[ErrorTracker] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None

    def initialize(self) -> bool:
        """初始化遥测系统"""
        try:
            log.debug("Initializing telemetry system...")

            # 加载配置
            self.config = self.config_loader.load_config()
            self.privacy_settings = self.privacy_manager.load_privacy_settings()

            # 检查是否启用遥测
            if not self.config.enabled:
                log.debug("Telemetry is disabled by configuration")
                return True

            log.debug("Telemetry is enabled, initializing components...")

            # 初始化隐私控制器和数据清理器
            from one_dragon.utils import os_utils
            config_dir = Path(os_utils.get_work_dir()) / "config"
            self.privacy_controller = PrivacyController(config_dir)
            self.data_sanitizer = DataSanitizer()
            self.ui_support = TelemetryUISupport(self.privacy_controller)

            # 初始化Loki客户端
            log.debug("Initializing Loki client...")
            self.loki_client = LokiClient(self.config)
            if not self.loki_client.initialize():
                log.warning("Failed to initialize Loki client")
                return False

            log.debug("Loki client initialized successfully")

            # 生成用户ID（在创建 EventCollector 之前）
            self._user_id = self._generate_user_id()

            # 初始化核心遥测组件
            log.debug("Initializing telemetry components...")
            self.event_collector = EventCollector(self.loki_client, self.privacy_controller, self._user_id)
            self.error_tracker = ErrorTracker(self.loki_client, self.privacy_controller)
            self.performance_monitor = PerformanceMonitor(self.loki_client, self.privacy_controller)

            # 设置全局异常处理器
            self.error_tracker.setup_exception_handler()

            # 开始系统监控（降低频率，避免过多日志）
            self.performance_monitor.start_system_monitoring(interval=30.0)

            self._initialized = True
            log.debug("Telemetry system initialized successfully")
            return True

        except Exception as e:
            log.error(f"Failed to initialize telemetry system: {e}")
            import traceback
            log.error(traceback.format_exc())
            return False



    def _generate_user_id(self) -> str:
        """生成用户ID"""
        try:
            # 使用机器特征生成稳定的ID
            machine_id = f"{platform.node()}-{platform.machine()}"
            # 生成基于机器特征的稳定UUID
            user_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, machine_id))
            log.debug(f"Generated user UUID: {user_uuid}")
            return user_uuid
        except Exception as e:
            # 如果生成失败，使用随机ID
            log.warning(f"Failed to generate user ID from machine features: {e}")
            user_uuid = str(uuid.uuid4())
            log.debug(f"Using random user UUID: {user_uuid}")
            return user_uuid

    def _get_app_version(self) -> str:
        """获取应用版本号"""
        try:
            # 首先尝试获取启动器版本
            from one_dragon.utils import app_utils
            launcher_version = app_utils.get_launcher_version()
            if launcher_version:
                return launcher_version
        except Exception:
            pass

        # 回退到project_config的version属性
        app_version = getattr(self.ctx.project_config, 'version', None)
        if app_version:
            return app_version

        # 最后回退到默认值
        return '2.0.0'

    def is_enabled(self) -> bool:
        """检查遥测是否启用"""
        return (
            self._initialized and
            self.config and
            self.config.enabled and
            self.loki_client and
            self.loki_client._initialized
        )

    def capture_event(self, event_name: str, properties: Dict[str, Any] = None) -> None:
        """捕获事件"""
        if not self.is_enabled() or not self._user_id:
            return

        try:
            # 添加通用属性
            event_properties = {
                'session_id': self._session_id,
                'app_version': self._app_version,
                **(properties or {})
            }

            # 隐私控制和数据处理
            if self.privacy_controller:
                processed_properties = self.privacy_controller.process_event_data(event_name, event_properties)
                if processed_properties is None:
                    log.debug(f"Event {event_name} blocked by privacy settings")
                    return
                event_properties = processed_properties

            # 数据清理
            if self.data_sanitizer:
                event_properties = self.data_sanitizer.sanitize_event_properties(event_properties)

            # 发送事件到Loki
            self.loki_client.capture(
                distinct_id=self._user_id,
                event=event_name,
                properties=event_properties
            )

            log.debug(f"Captured event: {event_name}")

        except Exception as e:
            log.error(f"Failed to capture event {event_name}: {e}")

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
                'app_version': self._app_version,
            }

            # 隐私控制检查
            if self.privacy_controller and not self.privacy_controller.is_error_reporting_enabled():
                log.debug("Error reporting disabled by privacy settings")
                return

            # 数据清理
            if self.data_sanitizer:
                error_data = self.data_sanitizer.sanitize_error_data(error_data)

            # 隐私过滤
            if self.privacy_controller:
                error_data = self.privacy_controller.filter_sensitive_info(error_data)

            # 发送错误事件到Loki
            self.loki_client.capture(
                distinct_id=self._user_id,
                event='error_occurred',
                properties=error_data
            )

            log.debug(f"Captured error: {type(error).__name__}")

        except Exception as e:
            log.error(f"Failed to capture error: {e}")

    def capture_performance(self, metric_name: str, value: float, tags: Dict[str, Any] = None) -> None:
        """捕获性能指标"""
        if not self.is_enabled():
            return

        try:
            performance_properties = {
                'metric_name': metric_name,
                'metric_value': value,
                'session_id': self._session_id,
                'app_version': self._app_version,
                **(tags or {})
            }

            # 发送性能指标到Loki
            self.loki_client.capture(
                distinct_id=self._user_id,
                event='performance_metric',
                properties=performance_properties
            )

            log.debug(f"Captured performance metric: {metric_name} = {value}")

        except Exception as e:
            log.error(f"Failed to capture performance metric: {e}")

    def track_custom_event(self, event_name: str, properties: Dict[str, Any] = None) -> None:
        """跟踪自定义事件"""
        if not self.is_enabled():
            return

        try:
            # 添加通用属性
            event_properties = {
                'session_id': self._session_id,
                'app_version': self._app_version,
                **(properties or {})
            }

            # 隐私控制和数据处理
            if self.privacy_controller:
                processed_properties = self.privacy_controller.process_event_data(event_name, event_properties)
                if processed_properties is None:
                    log.debug(f"Custom event {event_name} blocked by privacy settings")
                    return
                event_properties = processed_properties

            # 数据清理
            if self.data_sanitizer:
                event_properties = self.data_sanitizer.sanitize_event_properties(event_properties)

            # 发送事件到Loki
            self.loki_client.capture(
                distinct_id=self._user_id,
                event=event_name,
                properties=event_properties
            )

            log.debug(f"Tracked custom event: {event_name}")

        except Exception as e:
            log.error(f"Failed to track custom event {event_name}: {e}")

    def identify_user(self, user_id: str, properties: Dict[str, Any] = None) -> None:
        """识别用户"""
        if not self.is_enabled():
            return

        try:
            # 发送用户识别到Loki
            self.loki_client.identify(
                distinct_id=user_id,
                properties=properties or {}
            )

            # 关联旧的匿名ID
            if self._user_id and self._user_id != user_id:
                self.loki_client.alias(self._user_id, user_id)

            self._user_id = user_id
            log.debug(f"Identified user: {user_id}")

        except Exception as e:
            log.error(f"Failed to identify user: {e}")

    def set_user_properties(self, properties: Dict[str, Any]) -> None:
        """设置用户属性"""
        if not self.is_enabled() or not self._user_id:
            return

        try:
            # 设置用户属性到Loki
            self.loki_client.set_user_properties(self._user_id, properties)
            log.debug("Set user properties")

        except Exception as e:
            log.error(f"Failed to set user properties: {e}")

    def flush(self) -> None:
        """立即刷新所有待发送的数据"""
        if self.loki_client:
            self.loki_client.flush()

    def shutdown(self) -> None:
        """关闭遥测系统"""
        log.debug("Shutting down telemetry system...")

        try:
            # 强制刷新所有待发送的事件
            if self.is_enabled():
                log.debug("Flushing all pending events before shutdown...")
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

            # 关闭Loki客户端（这会再次刷新队列）
            if self.loki_client:
                self.loki_client.shutdown()

            self._initialized = False
            log.debug("Telemetry system shutdown complete")

        except Exception as e:
            log.error(f"Error during telemetry shutdown: {e}")

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
            app_version = version or self._app_version
            self.event_collector.track_app_launch(launch_time, app_version)

    def track_ui_interaction(self, element: str, action: str, properties: Dict[str, Any] = None) -> None:
        """跟踪UI交互（用于DAU统计）"""
        if not self.is_enabled():
            return

        try:
            # 添加通用属性
            event_properties = {
                'element': element,
                'action': action,
                'session_id': self._session_id,
                'app_version': self._app_version,
                'event_category': 'ui_interaction',
                **(properties or {})
            }

            # 隐私控制和数据处理
            if self.privacy_controller:
                processed_properties = self.privacy_controller.process_event_data('ui_interaction', event_properties)
                if processed_properties is None:
                    log.debug(f"UI interaction {element}.{action} blocked by privacy settings")
                    return
                event_properties = processed_properties

            # 数据清理
            if self.data_sanitizer:
                event_properties = self.data_sanitizer.sanitize_event_properties(event_properties)

            # 发送事件到Loki
            self.loki_client.capture(
                distinct_id=self._user_id,
                event='ui_interaction',
                properties=event_properties
            )

            log.debug(f"Tracked UI interaction: {element} - {action}")

        except Exception as e:
            log.error(f"Failed to track UI interaction {element}.{action}: {e}")

    def add_breadcrumb(self, message: str, category: str = "operation", level: str = "info",
                      properties: Dict[str, Any] = None) -> None:
        """添加面包屑（用于错误追踪）"""
        if self.error_tracker:
            self.error_tracker.add_breadcrumb(message, category, level, properties)

    def track_operation_start(self, operation_name: str, context: Dict[str, Any] = None) -> None:
        """跟踪操作开始（用于错误追踪）"""
        if self.error_tracker:
            self.error_tracker.track_operation_start(operation_name, context)

    def track_operation_end(self, operation_name: str, success: bool, duration: float,
                          context: Dict[str, Any] = None) -> None:
        """跟踪操作结束（用于错误追踪）"""
        if self.error_tracker:
            self.error_tracker.track_operation_end(operation_name, success, duration, context)

    def track_operation_time(self, operation: str, duration: float, success: bool,
                           metadata: Dict[str, Any] = None) -> None:
        """跟踪操作时间（用于性能监控）"""
        if self.performance_monitor:
            self.performance_monitor.track_operation_time(operation, duration, success, metadata)

    def track_navigation(self, from_page: str, to_page: str) -> None:
        """跟踪导航（用于DAU统计）"""
        if not self.is_enabled():
            return

        try:
            # 添加通用属性
            event_properties = {
                'from_page': from_page,
                'to_page': to_page,
                'session_id': self._session_id,
                'app_version': self._app_version,
                'event_category': 'navigation'
            }

            # 隐私控制和数据处理
            if self.privacy_controller:
                processed_properties = self.privacy_controller.process_event_data('navigation', event_properties)
                if processed_properties is None:
                    log.debug(f"Navigation {from_page} -> {to_page} blocked by privacy settings")
                    return
                event_properties = processed_properties

            # 数据清理
            if self.data_sanitizer:
                event_properties = self.data_sanitizer.sanitize_event_properties(event_properties)

            # 发送事件到Loki
            self.loki_client.capture(
                distinct_id=self._user_id,
                event='navigation',
                properties=event_properties
            )

            log.debug(f"Tracked navigation: {from_page} -> {to_page}")

        except Exception as e:
            log.error(f"Failed to track navigation {from_page} -> {to_page}: {e}")

    def track_feature_usage(self, feature_name: str, properties: Dict[str, Any] = None) -> None:
        """跟踪功能使用（用于DAU统计）"""
        if not self.is_enabled():
            return

        try:
            # 添加通用属性
            event_properties = {
                'feature_name': feature_name,
                'session_id': self._session_id,
                'app_version': self._app_version,
                'event_category': 'feature_usage',
                **(properties or {})
            }

            # 隐私控制和数据处理
            if self.privacy_controller:
                processed_properties = self.privacy_controller.process_event_data('feature_usage', event_properties)
                if processed_properties is None:
                    log.debug(f"Feature usage {feature_name} blocked by privacy settings")
                    return
                event_properties = processed_properties

            # 数据清理
            if self.data_sanitizer:
                event_properties = self.data_sanitizer.sanitize_event_properties(event_properties)

            # 发送事件到Loki
            self.loki_client.capture(
                distinct_id=self._user_id,
                event='feature_usage',
                properties=event_properties
            )

            log.debug(f"Tracked feature usage: {feature_name}")

        except Exception as e:
            log.error(f"Failed to track feature usage {feature_name}: {e}")



    # 性能监控器方法
    def track_startup_time(self, startup_duration: float, components: Dict[str, float] = None) -> None:
        """跟踪应用启动时间"""
        if self.performance_monitor:
            self.performance_monitor.track_startup_time(startup_duration, components)

    def get_health_status(self) -> Dict[str, Any]:
        """获取遥测系统健康状态"""
        status = {
            'initialized': self._initialized,
            'enabled': self.is_enabled(),
            'user_id': self._user_id,
            'session_id': self._session_id
        }

        # 添加Loki客户端状态信息
        if self.loki_client:
            status.update({
                'backend_type': 'loki',
                'loki_status': self.loki_client.get_health_status()
            })
        else:
            status['backend_type'] = 'loki'

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
