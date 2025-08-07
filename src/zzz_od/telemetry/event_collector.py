"""
事件收集器
收集用户行为事件，包括应用启动、导航、UI交互等
"""
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .posthog_client import PostHogClient
from .privacy_controller import PrivacyController


logger = logging.getLogger(__name__)


class EventCollector:
    """事件收集器"""

    def __init__(self, posthog_client: PostHogClient, privacy_controller: PrivacyController, user_id: str):
        self.posthog_client = posthog_client
        self.privacy_controller = privacy_controller
        self.user_id = user_id

        # 会话跟踪
        self.session_start_time = time.time()
        self.last_activity_time = time.time()
        self.navigation_history: List[Dict[str, Any]] = []
        self.interaction_count = 0

        # 功能使用统计
        self.feature_usage = {}

    def track_app_launch(self, launch_time: float, version: str, launch_mode: str = "normal") -> None:
        """跟踪应用启动"""
        import platform
        import socket

        # 获取机器信息（原来在app_startup中的信息）
        machine_id = f"{socket.gethostname()}-{platform.machine()}"

        properties = {
            'launch_time_seconds': launch_time,
            'app_version': version,
            'launch_mode': launch_mode,
            'platform': platform.system(),
            'machine_id': machine_id,
            'startup_type': 'user_launch',  # 区分用户启动
            'session_start': datetime.now().isoformat(),
            'event_category': 'app_lifecycle'
        }

        self._capture_event('app_launched', properties)
        logger.debug(f"Tracked app launch: {launch_time:.2f}s")

    def track_app_shutdown(self, session_duration: float, clean_shutdown: bool = True) -> None:
        """跟踪应用关闭"""
        properties = {
            'session_duration_seconds': session_duration,
            'clean_shutdown': clean_shutdown,
            'total_interactions': self.interaction_count,
            'screens_visited': len(self.navigation_history),
            'features_used': len(self.feature_usage),
            'telemetry_status': 'active',
            'shutdown_type': 'normal',
            'event_category': 'app_lifecycle'
        }

        self._capture_event('app_shutdown', properties)
        logger.debug(f"Tracked app shutdown: {session_duration:.2f}s session")

    def track_navigation(self, from_screen: str, to_screen: str, duration: float = None) -> None:
        """跟踪页面导航"""
        current_time = time.time()

        # 计算停留时间
        if duration is None and self.navigation_history:
            last_nav = self.navigation_history[-1]
            duration = current_time - last_nav.get('timestamp', current_time)

        properties = {
            'from_screen': from_screen,
            'to_screen': to_screen,
            'duration_seconds': duration,
            'navigation_sequence': len(self.navigation_history) + 1,
            'event_category': 'navigation'
        }

        # 记录导航历史
        nav_record = {
            'from_screen': from_screen,
            'to_screen': to_screen,
            'timestamp': current_time,
            'duration': duration
        }
        self.navigation_history.append(nav_record)

        # 限制历史记录长度
        if len(self.navigation_history) > 50:
            self.navigation_history = self.navigation_history[-50:]

        self._capture_event('navigation', properties)
        self._update_activity_time()

        logger.debug(f"Tracked navigation: {from_screen} -> {to_screen}")

    def track_ui_interaction(self, element: str, action: str, context: Dict[str, Any] = None) -> None:
        """跟踪UI交互"""
        self.interaction_count += 1

        properties = {
            'element': element,
            'action': action,
            'interaction_sequence': self.interaction_count,
            'time_since_last_activity': time.time() - self.last_activity_time,
            'event_category': 'ui_interaction',
            **(context or {})
        }

        self._capture_event('ui_interaction', properties)
        self._update_activity_time()

        logger.debug(f"Tracked UI interaction: {action} on {element}")

    def track_feature_usage(self, feature: str, usage_data: Dict[str, Any] = None) -> None:
        """跟踪功能使用"""
        # 更新功能使用统计
        if feature not in self.feature_usage:
            self.feature_usage[feature] = {
                'first_used': time.time(),
                'usage_count': 0,
                'last_used': time.time()
            }

        self.feature_usage[feature]['usage_count'] += 1
        self.feature_usage[feature]['last_used'] = time.time()

        properties = {
            'feature_name': feature,
            'usage_count': self.feature_usage[feature]['usage_count'],
            'time_since_first_use': time.time() - self.feature_usage[feature]['first_used'],
            'event_category': 'feature_usage',
            **(usage_data or {})
        }

        self._capture_event('feature_used', properties)
        self._update_activity_time()

        logger.debug(f"Tracked feature usage: {feature}")

    def track_automation_start(self, automation_type: str, config: Dict[str, Any] = None) -> None:
        """跟踪自动化开始"""
        properties = {
            'automation_type': automation_type,
            'start_time': datetime.now().isoformat(),
            'event_category': 'automation',
            **(config or {})
        }

        self._capture_event('automation_started', properties)
        self.track_feature_usage('automation', {'type': automation_type})

        logger.debug(f"Tracked automation start: {automation_type}")

    def track_automation_end(self, automation_type: str, duration: float, success: bool,
                           result_data: Dict[str, Any] = None) -> None:
        """跟踪自动化结束"""
        properties = {
            'automation_type': automation_type,
            'duration_seconds': duration,
            'success': success,
            'end_time': datetime.now().isoformat(),
            'event_category': 'automation',
            **(result_data or {})
        }

        self._capture_event('automation_ended', properties)
        self._update_activity_time()

        logger.debug(f"Tracked automation end: {automation_type} ({'success' if success else 'failed'})")

    def track_settings_change(self, setting_category: str, setting_name: str,
                           old_value: Any, new_value: Any) -> None:
        """跟踪设置变更"""
        properties = {
            'setting_category': setting_category,
            'setting_name': setting_name,
            'old_value': str(old_value),
            'new_value': str(new_value),
            'event_category': 'settings'
        }

        self._capture_event('settings_changed', properties)
        self._update_activity_time()

        logger.debug(f"Tracked settings change: {setting_category}.{setting_name}")

    def track_game_detection(self, game_detected: bool, detection_time: float,
                           detection_method: str = None) -> None:
        """跟踪游戏检测"""
        properties = {
            'game_detected': game_detected,
            'detection_time_seconds': detection_time,
            'detection_method': detection_method,
            'event_category': 'game_detection'
        }

        event_name = 'game_detected' if game_detected else 'game_detection_failed'
        self._capture_event(event_name, properties)

        logger.debug(f"Tracked game detection: {'success' if game_detected else 'failed'}")

    def track_image_recognition(self, operation_type: str, success: bool,
                              processing_time: float, confidence: float = None) -> None:
        """跟踪图像识别操作"""
        properties = {
            'operation_type': operation_type,
            'success': success,
            'processing_time_seconds': processing_time,
            'confidence_score': confidence,
            'event_category': 'image_recognition'
        }

        event_name = 'image_recognition_success' if success else 'image_recognition_failed'
        self._capture_event(event_name, properties)

        logger.debug(f"Tracked image recognition: {operation_type} ({'success' if success else 'failed'})")

    def track_custom_event(self, event_name: str, properties: Dict[str, Any] = None) -> None:
        """跟踪自定义事件"""
        event_properties = {
            'event_category': 'custom',
            **(properties or {})
        }

        self._capture_event(event_name, event_properties)
        self._update_activity_time()

        logger.debug(f"Tracked custom event: {event_name}")

    def _capture_event(self, event_name: str, properties: Dict[str, Any]) -> None:
        """内部事件捕获方法"""
        # 检查隐私设置
        if not self.privacy_controller.is_analytics_enabled():
            logger.debug(f"Event {event_name} blocked by privacy settings")
            return

        # 添加通用属性
        enhanced_properties = {
            'session_duration': time.time() - self.session_start_time,
            'total_interactions': self.interaction_count,
            'timestamp': datetime.now().isoformat(),
            **properties
        }

        # 通过隐私控制器处理数据
        processed_properties = self.privacy_controller.process_event_data(event_name, enhanced_properties)
        if processed_properties is None:
            return

        # 实际发送事件到 PostHog
        if not self.user_id:
            logger.debug(f"Cannot send event {event_name}: user_id is None")
            return

        self.posthog_client.capture(
            distinct_id=self.user_id,
            event=event_name,
            properties=processed_properties
        )

        logger.debug(f"Event sent to PostHog: {event_name}")

    def _update_activity_time(self) -> None:
        """更新最后活动时间"""
        self.last_activity_time = time.time()

    def get_session_summary(self) -> Dict[str, Any]:
        """获取会话摘要"""
        current_time = time.time()
        session_duration = current_time - self.session_start_time

        return {
            'session_duration_seconds': session_duration,
            'total_interactions': self.interaction_count,
            'screens_visited': len(self.navigation_history),
            'features_used': list(self.feature_usage.keys()),
            'most_used_feature': max(self.feature_usage.items(),
                                   key=lambda x: x[1]['usage_count'])[0] if self.feature_usage else None,
            'last_activity_time': self.last_activity_time,
            'navigation_path': [nav['to_screen'] for nav in self.navigation_history[-10:]]  # 最近10个页面
        }

    def reset_session(self) -> None:
        """重置会话数据"""
        self.session_start_time = time.time()
        self.last_activity_time = time.time()
        self.navigation_history.clear()
        self.interaction_count = 0
        self.feature_usage.clear()

        logger.debug("Session data reset")
