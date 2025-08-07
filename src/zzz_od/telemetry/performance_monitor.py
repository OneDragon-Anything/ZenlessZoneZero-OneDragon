"""
性能监控统计模块
提供遥测系统的性能监控和统计功能
"""
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque


@dataclass
class PerformanceMetrics:
    """性能指标数据结构"""
    # 事件处理性能
    events_processed: int = 0
    events_per_second: float = 0.0
    avg_processing_time_ms: float = 0.0
    max_processing_time_ms: float = 0.0

    # 队列性能
    queue_size: int = 0
    max_queue_size: int = 0
    queue_full_count: int = 0

    # 网络性能
    network_requests: int = 0
    network_failures: int = 0
    avg_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0

    # 内存使用
    memory_usage_mb: float = 0.0
    max_memory_usage_mb: float = 0.0

    # 错误统计
    format_errors: int = 0
    send_errors: int = 0
    total_errors: int = 0

    # 时间戳
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.events_processed + self.total_errors
        if total == 0:
            return 100.0
        return (self.events_processed / total) * 100

    @property
    def network_success_rate(self) -> float:
        """网络成功率"""
        if self.network_requests == 0:
            return 100.0
        return ((self.network_requests - self.network_failures) / self.network_requests) * 100


@dataclass
class TimingRecord:
    """时间记录"""
    timestamp: datetime
    duration_ms: float
    operation: str
    success: bool


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, telemetry_client=None, privacy_controller=None, window_size_minutes: int = 5):
        self.telemetry_client = telemetry_client
        self.privacy_controller = privacy_controller
        self.window_size = timedelta(minutes=window_size_minutes)
        self.metrics = PerformanceMetrics()

        # 时间窗口数据
        self._timing_records: deque = deque()
        self._event_timestamps: deque = deque()
        self._network_records: deque = deque()

        # 线程安全锁
        self._lock = threading.RLock()

        # 内存监控
        self._memory_samples: deque = deque(maxlen=100)

        # 启动时间
        self._start_time = datetime.now()

    def record_event_processing(self, duration_ms: float, success: bool = True) -> None:
        """记录事件处理性能"""
        with self._lock:
            current_time = datetime.now()

            # 记录时间数据
            record = TimingRecord(
                timestamp=current_time,
                duration_ms=duration_ms,
                operation='event_processing',
                success=success
            )
            self._timing_records.append(record)

            if success:
                self.metrics.events_processed += 1
                self._event_timestamps.append(current_time)
            else:
                self.metrics.total_errors += 1

            # 更新最大处理时间
            if duration_ms > self.metrics.max_processing_time_ms:
                self.metrics.max_processing_time_ms = duration_ms

            # 清理过期数据
            self._cleanup_old_records()

            # 更新统计
            self._update_processing_stats()

    def record_network_request(self, duration_ms: float, success: bool = True) -> None:
        """记录网络请求性能"""
        with self._lock:
            current_time = datetime.now()

            record = TimingRecord(
                timestamp=current_time,
                duration_ms=duration_ms,
                operation='network_request',
                success=success
            )
            self._network_records.append(record)

            self.metrics.network_requests += 1
            if not success:
                self.metrics.network_failures += 1
                self.metrics.send_errors += 1
                self.metrics.total_errors += 1

            # 更新最大响应时间
            if duration_ms > self.metrics.max_response_time_ms:
                self.metrics.max_response_time_ms = duration_ms

            # 清理过期数据
            self._cleanup_old_records()

            # 更新网络统计
            self._update_network_stats()

    def record_queue_status(self, current_size: int, is_full: bool = False) -> None:
        """记录队列状态"""
        with self._lock:
            self.metrics.queue_size = current_size

            if current_size > self.metrics.max_queue_size:
                self.metrics.max_queue_size = current_size

            if is_full:
                self.metrics.queue_full_count += 1

    def record_format_error(self) -> None:
        """记录格式化错误"""
        with self._lock:
            self.metrics.format_errors += 1
            self.metrics.total_errors += 1

    def record_memory_usage(self, memory_mb: float) -> None:
        """记录内存使用"""
        with self._lock:
            self.metrics.memory_usage_mb = memory_mb
            self._memory_samples.append(memory_mb)

            if memory_mb > self.metrics.max_memory_usage_mb:
                self.metrics.max_memory_usage_mb = memory_mb

    def send_performance_event(self, metric_name: str, metric_value: float,
                              metadata: Dict[str, Any] = None, user_id: str = None) -> None:
        """发送性能指标事件到telemetry client"""
        if not self.telemetry_client:
            return

        # 检查隐私设置
        if self.privacy_controller and not self.privacy_controller.is_analytics_enabled():
            return

        properties = {
            'metric_name': metric_name,
            'metric_value': metric_value,
            'timestamp': datetime.now().isoformat(),
            **(metadata or {})
        }

        # 隐私过滤
        if self.privacy_controller:
            properties = self.privacy_controller.filter_sensitive_info(properties)

        # 调用telemetry_client，如果没有user_id则让LokiClient生成默认ID
        self.telemetry_client.capture(
            distinct_id=user_id,  # 可以为None，LokiClient会处理
            event='performance_metric',
            properties=properties
        )

    def get_current_metrics(self) -> PerformanceMetrics:
        """获取当前性能指标"""
        with self._lock:
            # 更新时间戳
            self.metrics.last_updated = datetime.now()
            return self.metrics

    def get_detailed_stats(self) -> Dict[str, Any]:
        """获取详细统计信息"""
        with self._lock:
            current_time = datetime.now()
            uptime = current_time - self._start_time

            # 计算时间窗口内的统计
            recent_processing_times = [
                r.duration_ms for r in self._timing_records
                if r.operation == 'event_processing' and r.success
            ]

            recent_network_times = [
                r.duration_ms for r in self._network_records
                if r.success
            ]

            return {
                'uptime_seconds': uptime.total_seconds(),
                'current_metrics': self.metrics,
                'processing_stats': {
                    'recent_count': len(recent_processing_times),
                    'recent_avg_ms': sum(recent_processing_times) / len(recent_processing_times) if recent_processing_times else 0,
                    'recent_min_ms': min(recent_processing_times) if recent_processing_times else 0,
                    'recent_max_ms': max(recent_processing_times) if recent_processing_times else 0,
                    'percentile_95_ms': self._calculate_percentile(recent_processing_times, 95),
                    'percentile_99_ms': self._calculate_percentile(recent_processing_times, 99)
                },
                'network_stats': {
                    'recent_count': len(recent_network_times),
                    'recent_avg_ms': sum(recent_network_times) / len(recent_network_times) if recent_network_times else 0,
                    'recent_min_ms': min(recent_network_times) if recent_network_times else 0,
                    'recent_max_ms': max(recent_network_times) if recent_network_times else 0,
                    'percentile_95_ms': self._calculate_percentile(recent_network_times, 95),
                    'percentile_99_ms': self._calculate_percentile(recent_network_times, 99)
                },
                'memory_stats': {
                    'current_mb': self.metrics.memory_usage_mb,
                    'max_mb': self.metrics.max_memory_usage_mb,
                    'avg_mb': sum(self._memory_samples) / len(self._memory_samples) if self._memory_samples else 0,
                    'samples_count': len(self._memory_samples)
                },
                'error_breakdown': {
                    'format_errors': self.metrics.format_errors,
                    'send_errors': self.metrics.send_errors,
                    'total_errors': self.metrics.total_errors,
                    'error_rate': (self.metrics.total_errors / max(self.metrics.events_processed + self.metrics.total_errors, 1)) * 100
                }
            }

    def get_health_assessment(self) -> Dict[str, Any]:
        """获取健康评估"""
        with self._lock:
            metrics = self.get_current_metrics()

            # 健康评分 (0-100)
            health_score = 100
            issues = []

            # 检查成功率
            if metrics.success_rate < 95:
                health_score -= 20
                issues.append(f"Low success rate: {metrics.success_rate:.1f}%")

            # 检查网络成功率
            if metrics.network_success_rate < 90:
                health_score -= 15
                issues.append(f"Low network success rate: {metrics.network_success_rate:.1f}%")

            # 检查处理时间
            if metrics.avg_processing_time_ms > 100:
                health_score -= 10
                issues.append(f"High processing time: {metrics.avg_processing_time_ms:.1f}ms")

            # 检查队列积压
            if metrics.queue_size > 500:
                health_score -= 15
                issues.append(f"High queue size: {metrics.queue_size}")

            # 检查内存使用
            if metrics.memory_usage_mb > 500:
                health_score -= 10
                issues.append(f"High memory usage: {metrics.memory_usage_mb:.1f}MB")

            # 检查错误率
            error_rate = (metrics.total_errors / max(metrics.events_processed + metrics.total_errors, 1)) * 100
            if error_rate > 5:
                health_score -= 20
                issues.append(f"High error rate: {error_rate:.1f}%")

            # 确定健康状态
            if health_score >= 90:
                status = 'healthy'
            elif health_score >= 70:
                status = 'degraded'
            else:
                status = 'unhealthy'

            return {
                'status': status,
                'score': max(0, health_score),
                'issues': issues,
                'metrics_summary': {
                    'events_processed': metrics.events_processed,
                    'success_rate': metrics.success_rate,
                    'avg_processing_time_ms': metrics.avg_processing_time_ms,
                    'queue_size': metrics.queue_size,
                    'memory_usage_mb': metrics.memory_usage_mb,
                    'total_errors': metrics.total_errors
                }
            }

    def reset_metrics(self) -> None:
        """重置所有指标"""
        with self._lock:
            self.metrics = PerformanceMetrics()
            self._timing_records.clear()
            self._event_timestamps.clear()
            self._network_records.clear()
            self._memory_samples.clear()
            self._start_time = datetime.now()

    def _cleanup_old_records(self) -> None:
        """清理过期记录"""
        cutoff_time = datetime.now() - self.window_size

        # 清理时间记录
        while self._timing_records and self._timing_records[0].timestamp < cutoff_time:
            self._timing_records.popleft()

        # 清理事件时间戳
        while self._event_timestamps and self._event_timestamps[0] < cutoff_time:
            self._event_timestamps.popleft()

        # 清理网络记录
        while self._network_records and self._network_records[0].timestamp < cutoff_time:
            self._network_records.popleft()

    def _update_processing_stats(self) -> None:
        """更新处理统计"""
        # 计算事件处理速率
        if len(self._event_timestamps) >= 2:
            time_span = (self._event_timestamps[-1] - self._event_timestamps[0]).total_seconds()
            if time_span > 0:
                self.metrics.events_per_second = len(self._event_timestamps) / time_span

        # 计算平均处理时间
        processing_times = [
            r.duration_ms for r in self._timing_records
            if r.operation == 'event_processing' and r.success
        ]

        if processing_times:
            self.metrics.avg_processing_time_ms = sum(processing_times) / len(processing_times)

    def _update_network_stats(self) -> None:
        """更新网络统计"""
        # 计算平均响应时间
        response_times = [
            r.duration_ms for r in self._network_records
            if r.success
        ]

        if response_times:
            self.metrics.avg_response_time_ms = sum(response_times) / len(response_times)

    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """计算百分位数"""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)

        return sorted_values[index]

    def start_system_monitoring(self, interval: float = 30.0) -> None:
        """开始系统监控（占位方法）"""
        # 这个方法在当前实现中不需要做任何事情
        # 因为我们使用的是被动监控而不是主动监控
        pass

    def track_operation_time(self, operation: str, duration: float, success: bool, metadata: Dict[str, Any] = None) -> None:
        """跟踪操作执行时间"""
        duration_ms = duration * 1000  # 转换为毫秒
        self.record_event_processing(duration_ms, success)

        # 发送性能事件
        self.send_performance_event(
            f"operation_time_{operation}",
            duration,
            {
                'operation': operation,
                'success': success,
                'duration_ms': duration_ms,
                **(metadata or {})
            }
        )

    def track_startup_time(self, startup_duration: float, components: Dict[str, float] = None) -> None:
        """跟踪应用启动时间"""
        self.send_performance_event(
            "app_startup_time",
            startup_duration,
            {
                'startup_duration': startup_duration,
                'components': components or {},
                'event_type': 'startup_performance'
            }
        )

    def track_memory_usage(self, usage_mb: float, peak_mb: float = None, component: str = None) -> None:
        """跟踪内存使用"""
        self.record_memory_usage(usage_mb)

        self.send_performance_event(
            "memory_usage",
            usage_mb,
            {
                'usage_mb': usage_mb,
                'peak_mb': peak_mb,
                'component': component,
                'event_type': 'memory_performance'
            }
        )

    def track_image_recognition_performance(self, processing_time: float, accuracy: float = None,
                                          algorithm: str = None, image_size: str = None) -> None:
        """跟踪图像识别性能"""
        self.send_performance_event(
            "image_recognition_performance",
            processing_time,
            {
                'processing_time': processing_time,
                'accuracy': accuracy,
                'algorithm': algorithm,
                'image_size': image_size,
                'event_type': 'image_recognition_performance'
            }
        )

    def start_timer(self, timer_name: str, metadata: Dict[str, Any] = None) -> None:
        """开始计时器"""
        if not hasattr(self, '_timers'):
            self._timers = {}

        self._timers[timer_name] = {
            'start_time': time.time(),
            'metadata': metadata or {}
        }

    def stop_timer(self, timer_name: str, success: bool = True, additional_metadata: Dict[str, Any] = None) -> Optional[float]:
        """停止计时器"""
        if not hasattr(self, '_timers') or timer_name not in self._timers:
            return None

        timer_info = self._timers.pop(timer_name)
        duration = time.time() - timer_info['start_time']

        # 合并元数据
        metadata = timer_info['metadata'].copy()
        if additional_metadata:
            metadata.update(additional_metadata)

        # 跟踪操作时间
        self.track_operation_time(timer_name, duration, success, metadata)

        return duration

    def measure_time(self, operation_name: str, metadata: Dict[str, Any] = None):
        """上下文管理器形式的计时器"""
        return PerformanceContext(self, operation_name)

    def shutdown(self) -> None:
        """关闭性能监控器"""
        # 清理资源
        if hasattr(self, '_timers'):
            self._timers.clear()

        # 重置指标
        self.reset_metrics()

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要（兼容方法）"""
        return self.get_detailed_stats()


class PerformanceContext:
    """性能监控上下文管理器"""

    def __init__(self, monitor: PerformanceMonitor, operation: str = 'event_processing'):
        self.monitor = monitor
        self.operation = operation
        self.start_time = None
        self.success = True

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            # 只有在没有手动标记错误的情况下才根据异常状态设置success
            if self.success:
                self.success = exc_type is None

            if self.operation == 'network_request':
                self.monitor.record_network_request(duration_ms, self.success)
            else:
                self.monitor.record_event_processing(duration_ms, self.success)

    def mark_error(self):
        """标记操作失败"""
        self.success = False


# 全局性能监控实例
_global_monitor: Optional[PerformanceMonitor] = None


def get_global_monitor() -> PerformanceMonitor:
    """获取全局性能监控实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


def monitor_performance(operation: str = 'event_processing'):
    """性能监控装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_global_monitor()
            with PerformanceContext(monitor, operation):
                return func(*args, **kwargs)
        return wrapper
    return decorator