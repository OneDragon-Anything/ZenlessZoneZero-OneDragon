"""
性能监控器
监控应用程序性能指标，包括启动时间、操作耗时、资源使用等
"""
import time
import threading
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from contextlib import contextmanager

from .posthog_client import PostHogClient
from .privacy_controller import PrivacyController


logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, posthog_client: PostHogClient, privacy_controller: PrivacyController):
        self.posthog_client = posthog_client
        self.privacy_controller = privacy_controller

        # 性能指标存储
        self.metrics_history = defaultdict(lambda: deque(maxlen=100))
        self.active_timers = {}

        # 系统监控
        self.system_monitor_active = False
        self.system_monitor_thread = None
        self.system_metrics = deque(maxlen=60)  # 保留1分钟的系统指标

        # 性能阈值
        self.performance_thresholds = {
            'startup_time': 10.0,  # 秒
            'operation_time': 5.0,  # 秒
            'memory_usage': 32768,  # MB (32GB) - 调整为更高的阈值，适应大型应用
            'cpu_usage': 80.0,     # 百分比
            'image_processing': 1.0  # 秒
        }

        # 线程锁
        self._lock = threading.Lock()

        # 应用启动时间
        self.app_start_time = time.time()

    def track_startup_time(self, startup_duration: float, components: Dict[str, float] = None) -> None:
        """跟踪应用启动时间"""
        properties = {
            'startup_duration_seconds': startup_duration,
            'is_slow_startup': startup_duration > self.performance_thresholds['startup_time'],
            'metric_category': 'startup',
            'timestamp': datetime.now().isoformat()
        }

        # 添加组件启动时间
        if components:
            properties['components'] = components
            properties['slowest_component'] = max(components.items(), key=lambda x: x[1])[0]

        self._record_metric('startup_time', startup_duration, properties)

        logger.debug(f"Tracked startup time: {startup_duration:.2f}s")

    def track_operation_time(self, operation: str, duration: float, success: bool,
                           metadata: Dict[str, Any] = None) -> None:
        """跟踪操作执行时间"""
        properties = {
            'operation_name': operation,
            'duration_seconds': duration,
            'success': success,
            'is_slow_operation': duration > self.performance_thresholds['operation_time'],
            'metric_category': 'operation_time',
            'timestamp': datetime.now().isoformat(),
            **(metadata or {})
        }

        metric_name = f"operation_time_{operation}"
        self._record_metric(metric_name, duration, properties)

        logger.debug(f"Tracked operation time: {operation} - {duration:.2f}s ({'success' if success else 'failed'})")

    def track_memory_usage(self, usage_mb: float, peak_mb: float = None, component: str = None) -> None:
        """跟踪内存使用"""
        properties = {
            'memory_usage_mb': usage_mb,
            'peak_memory_mb': peak_mb,
            'component': component,
            'is_high_memory': usage_mb > self.performance_thresholds['memory_usage'],
            'metric_category': 'memory',
            'timestamp': datetime.now().isoformat()
        }

        self._record_metric('memory_usage', usage_mb, properties)

        # 如果内存使用过高，记录警告（限制频率）
        if usage_mb > self.performance_thresholds['memory_usage']:
            # 限制警告频率，避免刷屏
            current_time = time.time()
            if not hasattr(self, '_last_memory_warning') or current_time - self._last_memory_warning > 60:
                logger.warning(f"内存使用过高: {usage_mb:.1f}MB，建议检查内存泄漏")
                self._last_memory_warning = current_time

    def track_cpu_usage(self, usage_percent: float, duration: float, component: str = None) -> None:
        """跟踪CPU使用率"""
        properties = {
            'cpu_usage_percent': usage_percent,
            'duration_seconds': duration,
            'component': component,
            'is_high_cpu': usage_percent > self.performance_thresholds['cpu_usage'],
            'metric_category': 'cpu',
            'timestamp': datetime.now().isoformat()
        }

        self._record_metric('cpu_usage', usage_percent, properties)

        # 如果CPU使用过高，记录警告（限制频率）
        if usage_percent > self.performance_thresholds['cpu_usage']:
            # 限制警告频率，避免刷屏
            current_time = time.time()
            if not hasattr(self, '_last_cpu_warning') or current_time - self._last_cpu_warning > 60:
                logger.warning(f"CPU使用率过高: {usage_percent:.1f}%，建议检查性能问题")
                self._last_cpu_warning = current_time

    def track_image_recognition_performance(self, processing_time: float, accuracy: float = None,
                                          algorithm: str = None, image_size: str = None) -> None:
        """跟踪图像识别性能"""
        properties = {
            'processing_time_seconds': processing_time,
            'accuracy_score': accuracy,
            'algorithm': algorithm,
            'image_size': image_size,
            'is_slow_processing': processing_time > self.performance_thresholds['image_processing'],
            'metric_category': 'image_recognition',
            'timestamp': datetime.now().isoformat()
        }

        self._record_metric('image_recognition_performance', processing_time, properties)

        logger.debug(f"Tracked image recognition performance: {processing_time:.3f}s")

    def start_timer(self, timer_name: str, metadata: Dict[str, Any] = None) -> None:
        """开始计时器"""
        with self._lock:
            self.active_timers[timer_name] = {
                'start_time': time.time(),
                'metadata': metadata or {}
            }

        logger.debug(f"Timer started: {timer_name}")

    def stop_timer(self, timer_name: str, success: bool = True,
                  additional_metadata: Dict[str, Any] = None) -> Optional[float]:
        """停止计时器并返回持续时间"""
        with self._lock:
            if timer_name not in self.active_timers:
                logger.warning(f"Timer not found: {timer_name}")
                return None

            timer_info = self.active_timers.pop(timer_name)
            duration = time.time() - timer_info['start_time']

            # 合并元数据
            metadata = timer_info['metadata'].copy()
            if additional_metadata:
                metadata.update(additional_metadata)

            # 记录性能
            self.track_operation_time(timer_name, duration, success, metadata)

            logger.debug(f"Timer stopped: {timer_name} - {duration:.3f}s")
            return duration

    @contextmanager
    def measure_time(self, operation_name: str, metadata: Dict[str, Any] = None):
        """上下文管理器形式的计时器"""
        start_time = time.time()
        success = True

        try:
            yield
        except Exception as e:
            success = False
            raise
        finally:
            duration = time.time() - start_time
            self.track_operation_time(operation_name, duration, success, metadata)

    def start_system_monitoring(self, interval: float = 5.0) -> None:
        """开始系统监控"""
        if self.system_monitor_active:
            logger.warning("System monitoring already active")
            return

        self.system_monitor_active = True
        self.system_monitor_thread = threading.Thread(
            target=self._system_monitor_worker,
            args=(interval,),
            daemon=True,
            name="SystemMonitor"
        )
        self.system_monitor_thread.start()

        logger.debug(f"System monitoring started with {interval}s interval")

    def stop_system_monitoring(self) -> None:
        """停止系统监控"""
        self.system_monitor_active = False

        if self.system_monitor_thread and self.system_monitor_thread.is_alive():
            self.system_monitor_thread.join(timeout=5)

        logger.debug("System monitoring stopped")

    def _system_monitor_worker(self, interval: float) -> None:
        """系统监控工作线程"""
        try:
            import psutil

            while self.system_monitor_active:
                try:
                    # 收集系统指标
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()

                    system_metrics = {
                        'timestamp': datetime.now(),
                        'cpu_percent': cpu_percent,
                        'memory_percent': memory.percent,
                        'memory_used_mb': memory.used / (1024 * 1024),
                        'memory_available_mb': memory.available / (1024 * 1024)
                    }

                    # 存储指标
                    with self._lock:
                        self.system_metrics.append(system_metrics)

                    # 检查阈值并记录
                    if cpu_percent > self.performance_thresholds['cpu_usage']:
                        self.track_cpu_usage(cpu_percent, interval, 'system_monitor')

                    if memory.used / (1024 * 1024) > self.performance_thresholds['memory_usage']:
                        self.track_memory_usage(memory.used / (1024 * 1024), component='system_monitor')

                    time.sleep(interval)

                except Exception as e:
                    logger.error(f"Error in system monitoring: {e}")
                    time.sleep(interval)

        except ImportError:
            logger.warning("psutil not available, system monitoring disabled")
        except Exception as e:
            logger.error(f"System monitoring worker error: {e}")

    def _record_metric(self, metric_name: str, value: float, properties: Dict[str, Any]) -> None:
        """记录性能指标"""
        try:
            # 检查隐私设置
            if not self.privacy_controller.is_performance_monitoring_enabled():
                logger.debug(f"Performance monitoring disabled for metric: {metric_name}")
                return

            # 存储指标历史
            with self._lock:
                metric_record = {
                    'value': value,
                    'timestamp': datetime.now(),
                    'properties': properties
                }
                self.metrics_history[metric_name].append(metric_record)

            # 发送事件（实际发送在TelemetryManager中处理）
            logger.debug(f"Performance metric recorded: {metric_name} = {value}")

        except Exception as e:
            logger.error(f"Failed to record metric: {e}")

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        try:
            with self._lock:
                summary = {
                    'app_uptime_seconds': time.time() - self.app_start_time,
                    'active_timers': len(self.active_timers),
                    'metrics_collected': sum(len(history) for history in self.metrics_history.values()),
                    'system_monitoring_active': self.system_monitor_active
                }

                # 添加各类指标的统计
                for metric_name, history in self.metrics_history.items():
                    if history:
                        values = [record['value'] for record in history]
                        summary[f"{metric_name}_avg"] = sum(values) / len(values)
                        summary[f"{metric_name}_max"] = max(values)
                        summary[f"{metric_name}_min"] = min(values)
                        summary[f"{metric_name}_count"] = len(values)

                # 最近的系统指标
                if self.system_metrics:
                    latest_system = self.system_metrics[-1]
                    summary['current_cpu_percent'] = latest_system['cpu_percent']
                    summary['current_memory_percent'] = latest_system['memory_percent']
                    summary['current_memory_used_mb'] = latest_system['memory_used_mb']

                return summary

        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {}

    def get_slow_operations(self, threshold_multiplier: float = 2.0) -> List[Dict[str, Any]]:
        """获取慢操作列表"""
        try:
            slow_operations = []

            with self._lock:
                for metric_name, history in self.metrics_history.items():
                    if not metric_name.startswith('operation_time_'):
                        continue

                    operation_name = metric_name.replace('operation_time_', '')

                    # 计算平均时间
                    values = [record['value'] for record in history]
                    if not values:
                        continue

                    avg_time = sum(values) / len(values)
                    max_time = max(values)

                    # 检查是否为慢操作
                    threshold = self.performance_thresholds.get('operation_time', 5.0) * threshold_multiplier
                    if max_time > threshold:
                        slow_operations.append({
                            'operation': operation_name,
                            'avg_time': avg_time,
                            'max_time': max_time,
                            'occurrences': len(values),
                            'threshold': threshold
                        })

            # 按最大时间排序
            slow_operations.sort(key=lambda x: x['max_time'], reverse=True)
            return slow_operations

        except Exception as e:
            logger.error(f"Failed to get slow operations: {e}")
            return []

    def clear_metrics_history(self) -> None:
        """清除指标历史"""
        try:
            with self._lock:
                self.metrics_history.clear()
                self.system_metrics.clear()
                self.active_timers.clear()

            logger.info("Performance metrics history cleared")

        except Exception as e:
            logger.error(f"Failed to clear metrics history: {e}")

    def set_performance_threshold(self, metric_name: str, threshold: float) -> None:
        """设置性能阈值"""
        try:
            self.performance_thresholds[metric_name] = threshold
            logger.info(f"Performance threshold set: {metric_name} = {threshold}")

        except Exception as e:
            logger.error(f"Failed to set performance threshold: {e}")

    def shutdown(self) -> None:
        """关闭性能监控器"""
        try:
            # 停止系统监控
            self.stop_system_monitoring()

            # 停止所有活动计时器
            with self._lock:
                for timer_name in list(self.active_timers.keys()):
                    self.stop_timer(timer_name, success=False)

            logger.info("Performance monitor shutdown complete")

        except Exception as e:
            logger.error(f"Error during performance monitor shutdown: {e}")