"""
Loki客户端包装器
提供与Loki服务的通信接口，包括本地队列、批量发送和重试机制
"""
import json
import platform
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime
from queue import Empty, Queue
from typing import Any, Dict, Optional

import requests

from one_dragon.utils.log_utils import log

from .models import TelemetryConfig


class LokiClient:
    """Loki客户端包装器"""

    def __init__(self, config: TelemetryConfig):
        self.config = config
        self._initialized = False
        self._shutdown = False

        # Loki连接配置
        self.loki_url = f"{config.loki_url.rstrip('/')}/loki/api/v1/push" if config.loki_url else ""
        self.headers = {'Content-Type': 'application/json'}

        # 设置认证头
        if config.loki_tenant_id:
            self.headers['X-Scope-OrgID'] = config.loki_tenant_id
        if config.loki_auth_token and config.loki_tenant_id:
            # 使用Grafana Cloud的认证格式: Bearer {USER_ID}:{API_KEY}
            self.headers['Authorization'] = f'Bearer {config.loki_tenant_id}:{config.loki_auth_token}'

        # 本地队列
        self._event_queue = Queue(maxsize=config.max_queue_size)
        self._flush_thread: Optional[threading.Thread] = None
        self._last_flush_time = datetime.now()

        # 统计信息
        self.events_sent = 0
        self.events_failed = 0
        self.queue_size = 0

        # 基础标签
        self.base_labels = {
            "job": "one_dragon",
            "project": "zzz_od",
            "environment": "production",
            **config.loki_labels
        }

    def initialize(self) -> bool:
        """初始化Loki客户端"""
        try:
            if not self.config.loki_url:
                log.warning("Loki URL not provided, telemetry disabled")
                return False

            log.debug(f"Initializing Loki client with URL: {self.config.loki_url}")

            # 发送应用启动事件
            log.debug("Sending app startup event...")
            try:
                # 生成一个基于机器特征的匿名用户ID
                machine_id = f"{platform.node()}-{platform.machine()}"
                anonymous_user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, machine_id))

                # 发送启动事件
                self.capture(
                    distinct_id=anonymous_user_id,
                    event="app_launched",
                    properties={
                        "platform": platform.system(),
                        "machine": platform.machine(),
                        "python_version": platform.python_version()
                    }
                )
                log.debug("App startup event sent successfully")
            except Exception as e:
                log.warning(f"Failed to send app startup event: {e}")

            # 启动后台刷新线程
            self._start_flush_thread()

            self._initialized = True
            log.debug(f"Loki client initialized successfully with URL: {self.config.loki_url}")
            return True

        except Exception as e:
            log.error(f"Failed to initialize Loent: {e}")
            import traceback
            log.error(traceback.format_exc())
            return False

    def _start_flush_thread(self) -> None:
        """启动后台刷新线程"""
        if self._flush_thread is None or not self._flush_thread.is_alive():
            self._flush_thread = threading.Thread(
                target=self._flush_worker,
                daemon=True,
                name="LokiFlushWorker"
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
                log.error(f"Error in flush worker: {e}")
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

        # 批量发送到Loki
        try:
            success = self._send_batch_to_loki(events_to_send)
            if success:
                self.events_sent += len(events_to_send)
                log.debug(f"Successfully sent {len(events_to_send)} events to Loki")
            else:
                self.events_failed += len(events_to_send)
                log.debug(f"Failed to send {len(events_to_send)} events to Loki")
        except Exception as e:
            # 静默失败，不影响应用运行
            log.debug(f"Error sending batch to Loki: {e}")
            self.events_failed += len(events_to_send)

        self._last_flush_time = datetime.now()

    def _send_batch_to_loki(self, events: list) -> bool:
        """批量发送事件到Loki（集成pushtoloki.py逻辑）"""
        try:
            # 按标签分组事件（优化Loki存储）
            streams = defaultdict(list)

            for event in events:
                # 生成时间戳
                ts = self._get_timestamp_ns()

                # 格式化日志行
                line = self._format_log_line_from_event(event)

                # 生成标签
                labels = self._generate_labels(event)
                labels_tuple = tuple(sorted(labels.items()))

                streams[labels_tuple].append([ts, line])

            # 构建Loki payload
            payload = {
                "streams": [
                    {"stream": dict(labels), "values": values}
                    for labels, values in streams.items()
                ]
            }

            # 使用重试机制发送到Loki
            return self._send_with_retry(payload)

        except Exception as e:
            # 静默失败，不影响应用运行
            log.debug(f"Error in _send_batch_to_loki: {e}")
            return False

    def _send_with_retry(self, payload: Dict[str, Any], max_retries: int = 3) -> bool:
        """带重试机制的发送方法"""
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.loki_url,
                    json=payload,
                    headers=self.headers,
                    timeout=10
                )

                if response.status_code == 204:
                    return True
                else:
                    log.debug(f"Loki returned status {response.status_code}, attempt {attempt + 1}/{max_retries}")

            except requests.exceptions.RequestException as e:
                log.debug(f"Network error sending to Loki, attempt {attempt + 1}/{max_retries}: {e}")

            except Exception as e:
                log.debug(f"Unexpected error sending to Loki, attempt {attempt + 1}/{max_retries}: {e}")

            # 指数退避
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                time.sleep(wait_time)

        # 所有重试都失败，静默失败
        log.debug(f"Failed to send to Loki after {max_retries} attempts, silently failing")
        return False

    def _get_timestamp_ns(self) -> str:
        """获取纳秒时间戳"""
        return str(int(datetime.now().timestamp() * 1e9))

    def _format_log_line(self, message: str, metadata: Optional[Dict[str, str]] = None) -> str:
        """将消息和元数据格式化为单个日志行字符串"""
        if not metadata:
            return message
        # 将元数据转换为 key="value" 的格式，并附加到消息后
        meta_str = " ".join([f'{k}="{v}"' for k, v in metadata.items()])
        return f"{message} {meta_str}"

    def _format_log_line_from_event(self, event: Dict[str, Any]) -> str:
        """从事件格式化日志行"""
        event_type = event.get('type', 'capture')

        if event_type == 'capture':
            message = f"one_dragon_event:{event['event']}"
        elif event_type == 'identify':
            message = f"one_dragon_identify:{event['distinct_id']}"
        elif event_type == 'alias':
            message = f"one_dragon_alias:{event['previous_id']}->{event['distinct_id']}"
        else:
            message = f"one_dragon_unknown:{event_type}"

        # 构建完整的JSON日志
        log_data = {
            "message": message,
            "level": "info",
            "properties": {
                "event_name": event.get('event', ''),
                "user_uuid": event.get('distinct_id', ''),  # 统一使用user_uuid
                "timestamp": event.get('timestamp', datetime.now().isoformat()),
                **event.get('properties', {})
            }
        }

        return json.dumps(log_data, ensure_ascii=False)

    def _generate_labels(self, event: Dict[str, Any]) -> Dict[str, str]:
        """生成Loki标签"""
        event_type = event.get('type', 'capture')

        labels = {
            **self.base_labels,
            "event_type": "telemetry" if event_type == 'capture' else event_type,
            "level": "info"
        }

        # 添加事件特定标签
        if event_type == 'capture' and 'event' in event:
            labels["event_name"] = event['event']

        if 'distinct_id' in event:
            labels["user_uuid"] = event['distinct_id']

        return labels

    def capture(self, distinct_id: str = None, event: str = None, properties: Dict[str, Any] = None) -> None:
        """捕获事件"""
        if not self._initialized or self._shutdown:
            return

        # 如果没有提供distinct_id，生成一个基于机器特征的ID
        if not distinct_id:
            import platform
            import uuid
            machine_id = f"{platform.node()}-{platform.machine()}"
            distinct_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, machine_id))

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
            log.error(f"Failed to enqueue event: {e}")
            self.events_failed += 1

    def flush(self) -> None:
        """立即刷新队列"""
        if self._initialized:
            self._flush_queue()

    def shutdown(self) -> None:
        """关闭Loki客户端"""
        log.debug("Shutting down Loki client...")

        try:
            self._shutdown = True

            # 停止刷新线程
            if self._flush_thread and self._flush_thread.is_alive():
                self._flush_thread.join(timeout=5)

            # 强制刷新所有剩余事件
            log.debug("Flushing all remaining events...")
            self._flush_queue()

            log.debug(f"Loki client shutdown complete. Events sent: {self.events_sent}, failed: {self.events_failed}")

        except Exception as e:
            log.debug(f"Error during Loki client shutdown: {e}")

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
                'loki_url_configured': bool(self.config.loki_url),
                'loki_url': self.config.loki_url,
                'last_error': getattr(self, '_last_error', None)
            })
        else:
            status.update({
                'connected': False,
                'loki_url_configured': bool(self.config.loki_url),
                'loki_url': self.config.loki_url,
                'last_error': 'Client not initialized'
            })

        return status
