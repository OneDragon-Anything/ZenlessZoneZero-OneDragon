"""
PostHog客户端包装器
提供与PostHog服务的通信接口，包括本地队列、批量发送和重试机制
"""
import os
import time
import json
import logging
import threading
from queue import Queue, Empty
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

import posthog

from .models import TelemetryConfig


logger = logging.getLogger(__name__)


class PostHogClient:
    """PostHog客户端包装器"""

    def __init__(self, config: TelemetryConfig):
        self.config = config
        self._initialized = False
        self._shutdown = False

        # 本地队列
        self._event_queue = Queue(maxsize=config.max_queue_size)
        self._flush_thread: Optional[threading.Thread] = None
        self._last_flush_time = datetime.now()

        # 统计信息
        self.events_sent = 0
        self.events_failed = 0
        self.queue_size = 0

    def initialize(self) -> bool:
        """初始化PostHog客户端"""
        try:
            if not self.config.api_key:
                logger.warning("PostHog API key not provided, telemetry disabled")
                return False

            logger.debug(f"Initializing PostHog client with host: {self.config.host}")

            # 初始化PostHog SDK
            posthog.project_api_key = self.config.api_key
            posthog.host = self.config.host

            # 发送应用启动事件
            logger.debug("Sending app startup event...")
            try:
                # 生成一个基于机器特征的匿名用户ID
                import platform
                import uuid
                machine_id = f"{platform.node()}-{platform.machine()}"
                anonymous_user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, machine_id))

                logger.debug("App startup event sent successfully")
            except Exception as e:
                logger.warning(f"Failed to send app startup event: {e}")

            # 启动后台刷新线程
            self._start_flush_thread()

            self._initialized = True
            logger.debug(f"PostHog client initialized successfully with host: {self.config.host}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize PostHog client: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _start_flush_thread(self) -> None:
        """启动后台刷新线程"""
        if self._flush_thread is None or not self._flush_thread.is_alive():
            self._flush_thread = threading.Thread(
                target=self._flush_worker,
                daemon=True,
                name="PostHogFlushWorker"
            )
            self._flush_thread.start()

    def _flush_worker(self) -> None:
        """后台刷新工作线程"""
        while not self._shutdown:
            try:
                # 等待刷新间隔或队列满
                time.sleep(1)  # 每秒检查一次

                current_time = datetime.now()
                time_since_last_flush = (current_time - self._last_flush_time).total_seconds()

                # 检查是否需要刷新
                should_flush = (
                    time_since_last_flush >= self.config.flush_interval or
                    self._event_queue.qsize() >= self.config.max_queue_size * 0.8
                )

                if should_flush:
                    self._flush_queue()

            except Exception as e:
                logger.error(f"Error in flush worker: {e}")
                time.sleep(5)  # 错误后等待5秒

    def _flush_queue(self) -> None:
        """刷新事件队列"""
        if self._event_queue.empty():
            return

        events_to_send = []

        # 从队列中取出事件
        while not self._event_queue.empty() and len(events_to_send) < 100:  # 批量大小限制
            try:
                event = self._event_queue.get_nowait()
                events_to_send.append(event)
            except Empty:
                break

        if not events_to_send:
            return

        # 发送事件
        success_count = 0
        for event in events_to_send:
            try:
                self._send_single_event(event)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send event: {e}")
                self.events_failed += 1

        self.events_sent += success_count
        self._last_flush_time = datetime.now()

        logger.debug(f"Flushed {success_count}/{len(events_to_send)} events")

    def _send_single_event(self, event: Dict[str, Any]) -> None:
        """发送单个事件"""
        event_type = event.get('type', 'capture')

        if event_type == 'capture':
            posthog.capture(
                distinct_id=event['distinct_id'],
                event=event['event'],
                properties=event.get('properties', {})
            )
        elif event_type == 'identify':
            posthog.identify(
                distinct_id=event['distinct_id'],
                properties=event.get('properties', {})
            )
        elif event_type == 'alias':
            posthog.alias(
                previous_id=event['previous_id'],
                distinct_id=event['distinct_id']
            )

    def capture(self, distinct_id: str, event: str, properties: Dict[str, Any] = None) -> None:
        """捕获事件"""
        if not self._initialized or self._shutdown:
            return

        event_data = {
            'type': 'capture',
            'distinct_id': distinct_id,
            'event': event,
            'properties': properties or {},
            'timestamp': datetime.now().isoformat()
        }

        self._enqueue_event(event_data)

    def identify(self, distinct_id: str, properties: Dict[str, Any] = None) -> None:
        """识别用户"""
        if not self._initialized or self._shutdown:
            return

        event_data = {
            'type': 'identify',
            'distinct_id': distinct_id,
            'properties': properties or {},
            'timestamp': datetime.now().isoformat()
        }

        self._enqueue_event(event_data)

    def alias(self, previous_id: str, distinct_id: str) -> None:
        """关联用户ID"""
        if not self._initialized or self._shutdown:
            return

        event_data = {
            'type': 'alias',
            'previous_id': previous_id,
            'distinct_id': distinct_id,
            'timestamp': datetime.now().isoformat()
        }

        self._enqueue_event(event_data)

    def set_user_properties(self, distinct_id: str, properties: Dict[str, Any]) -> None:
        """设置用户属性"""
        self.identify(distinct_id, properties)

    def _enqueue_event(self, event_data: Dict[str, Any]) -> None:
        """将事件加入队列"""
        try:
            self._event_queue.put_nowait(event_data)
            self.queue_size = self._event_queue.qsize()
        except Exception as e:
            logger.error(f"Failed to enqueue event: {e}")
            self.events_failed += 1

    def flush(self) -> None:
        """立即刷新队列"""
        if self._initialized:
            self._flush_queue()
            posthog.flush()

    def shutdown(self) -> None:
        """关闭PostHog客户端"""
        logger.debug("Shutting down PostHog client...")

        try:
            self._shutdown = True

            # 停止刷新线程
            if self._flush_thread and self._flush_thread.is_alive():
                self._flush_thread.join(timeout=5)

            # 强制刷新所有剩余事件
            logger.debug("Flushing all remaining events...")
            self._flush_queue()

            # 再次刷新，确保所有事件都被发送
            self.flush()

            # 关闭PostHog
            posthog.shutdown()

            logger.debug(f"PostHog client shutdown complete. Events sent: {self.events_sent}, failed: {self.events_failed}")

        except Exception as e:
            logger.debug(f"Error during PostHog client shutdown: {e}")

    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        status = {
            'initialized': self._initialized,
            'events_sent': self.events_sent,
            'events_failed': self.events_failed,
            'queue_size': self.queue_size,
            'last_flush': self._last_flush_time.isoformat() if self._last_flush_time else None,
            'health': 'healthy' if self.events_failed < 10 else 'degraded'
        }

        # 添加连接状态信息
        if self._initialized:
            status.update({
                'connected': self.events_sent > 0 or self.events_failed == 0,
                'api_key_configured': bool(self.config.api_key),
                'host': self.config.host,
                'last_error': getattr(self, '_last_error', None)
            })
        else:
            status.update({
                'connected': False,
                'api_key_configured': bool(self.config.api_key),
                'host': self.config.host,
                'last_error': 'Client not initialized'
            })

        return status
