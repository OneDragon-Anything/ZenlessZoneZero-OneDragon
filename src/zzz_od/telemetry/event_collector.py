"""
事件收集器
收集用户行为事件，包括应用启动、关闭、自定义事件等
"""
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .privacy_controller import PrivacyController


logger = logging.getLogger(__name__)


class EventCollector:
    """事件收集器"""

    ALLOWED_EVENTS = {"app_launched", "app_shutdown"}

    def __init__(self, telemetry_client, privacy_controller: Optional[PrivacyController], user_id: str):
        self.telemetry_client = telemetry_client
        self.privacy_controller = privacy_controller
        self.user_id = user_id

        # 会话跟踪
        self.session_start_time = time.time()
        self.last_activity_time = time.time()
        self.interaction_count = 0

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
            'telemetry_status': 'active',
            'shutdown_type': 'normal',
            'event_category': 'app_lifecycle'
        }

        self._capture_event('app_shutdown', properties)
        logger.debug(f"Tracked app shutdown: {session_duration:.2f}s session")



    def track_custom_event(self, event_name: str, properties: Dict[str, Any] = None) -> None:
        """跟踪自定义事件"""
        return

    def _capture_event(self, event_name: str, properties: Dict[str, Any]) -> None:
        """内部事件捕获方法"""
        if event_name not in self.ALLOWED_EVENTS:
            return

        # 添加通用属性
        enhanced_properties = {
            'session_duration': time.time() - self.session_start_time,
            'total_interactions': self.interaction_count,
            'timestamp': datetime.now().isoformat(),
            **properties
        }

        # 通过隐私控制器处理数据
        processed_properties = enhanced_properties
        if self.privacy_controller:
            if not self.privacy_controller.is_analytics_enabled():
                logger.debug(f"Event {event_name} blocked by privacy settings")
                return
            filtered = self.privacy_controller.process_event_data(event_name, enhanced_properties)
            if filtered is not None:
                processed_properties = filtered

        if not self.user_id:
            logger.debug(f"Cannot send event {event_name}: user_id is None")
            return

        self.telemetry_client.capture(
            distinct_id=self.user_id,
            event=event_name,
            properties=processed_properties
        )

        logger.debug(f"Event sent to Loki: {event_name}")

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
            'last_activity_time': self.last_activity_time
        }

    def reset_session(self) -> None:
        """重置会话数据"""
        self.session_start_time = time.time()
        self.last_activity_time = time.time()
        self.interaction_count = 0

        logger.debug("Session data reset")
