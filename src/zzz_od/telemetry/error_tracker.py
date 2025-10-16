"""
错误追踪器
捕获和处理应用程序错误，包括异常处理、错误分组和上下文收集
"""
import sys
import traceback
import threading
import logging
import platform
import os
import shutil
import ctypes
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from collections import defaultdict, deque

from .privacy_controller import PrivacyController
from .data_sanitizer import DataSanitizer


logger = logging.getLogger(__name__)


class ErrorTracker:
    """错误追踪器"""

    def __init__(self, telemetry_client, privacy_controller: PrivacyController):
        self.telemetry_client = telemetry_client
        self.privacy_controller = privacy_controller
        self.data_sanitizer = DataSanitizer()

        # 错误统计
        self.error_counts = defaultdict(int)
        self.error_history = deque(maxlen=100)  # 保留最近100个错误

        # 面包屑跟踪
        self.breadcrumbs = deque(maxlen=50)  # 保留最近50个面包屑

        # 异常处理器
        self.original_excepthook = None
        self.exception_handlers: List[Callable] = []

        # 线程锁
        self._lock = threading.Lock()

    def setup_exception_handler(self) -> None:
        """设置全局异常处理器"""
        try:
            # 保存原始异常处理器
            self.original_excepthook = sys.excepthook

            # 设置新的异常处理器
            sys.excepthook = self._global_exception_handler

            # 设置线程异常处理器
            if hasattr(threading, 'excepthook'):
                threading.excepthook = self._thread_exception_handler

            logger.debug("Global exception handler set up")

        except Exception as e:
            logger.error(f"Failed to setup exception handler: {e}")

    def restore_exception_handler(self) -> None:
        """恢复原始异常处理器"""
        try:
            if self.original_excepthook:
                sys.excepthook = self.original_excepthook
                self.original_excepthook = None

            logger.debug("Original exception handler restored")

        except Exception as e:
            logger.error(f"Failed to restore exception handler: {e}")

    def _global_exception_handler(self, exc_type, exc_value, exc_traceback):
        """全局异常处理器"""
        try:
            # 捕获异常
            self.capture_exception(exc_value, {
                'handler_type': 'global',
                'thread_name': threading.current_thread().name
            })

            # 调用原始处理器
            if self.original_excepthook:
                self.original_excepthook(exc_type, exc_value, exc_traceback)

        except Exception as e:
            logger.error(f"Error in global exception handler: {e}")

    def _thread_exception_handler(self, args):
        """线程异常处理器"""
        try:
            exc_type, exc_value, exc_traceback, thread = args

            self.capture_exception(exc_value, {
                'handler_type': 'thread',
                'thread_name': thread.name if thread else 'unknown',
                'thread_id': thread.ident if thread else None
            })

        except Exception as e:
            logger.error(f"Error in thread exception handler: {e}")

    def capture_exception(self, exception: Exception, extra_context: Dict[str, Any] = None) -> None:
        """捕获异常"""
        try:
            with self._lock:
                # 检查隐私设置
                if not self.privacy_controller.is_error_reporting_enabled():
                    logger.debug("Error reporting disabled by privacy settings")
                    return

                # 生成错误ID
                error_id = self._generate_error_id(exception)

                # 收集错误信息
                error_data = {
                    'error_id': error_id,
                    'error_type': type(exception).__name__,
                    'error_message': str(exception),
                    'stack_trace': traceback.format_exc(),
                    'breadcrumbs': list(self.breadcrumbs),
                    'context': extra_context or {},
                    'system_info': self._collect_system_info(),
                    'timestamp': datetime.now().isoformat(),
                    'occurrence_count': self.error_counts[error_id] + 1
                }

                # 更新错误统计
                self.error_counts[error_id] += 1
                self.error_history.append({
                    'error_id': error_id,
                    'timestamp': datetime.now(),
                    'error_type': type(exception).__name__
                })

                # 数据清理
                error_data = self.data_sanitizer.sanitize_error_data(error_data)

                # 隐私过滤
                error_data = self.privacy_controller.filter_sensitive_info(error_data)

                # 发送错误事件到telemetry client
                if self.telemetry_client:
                    # 生成用户ID（如果没有提供）
                    user_id = extra_context.get('user_id')  # 移除硬编码的默认值

                    self.telemetry_client.capture(
                        distinct_id=user_id,
                        event='error_occurred',
                        properties=error_data
                    )

                logger.debug(f"Exception captured: {type(exception).__name__} (ID: {error_id})")

        except Exception as e:
            logger.error(f"Failed to capture exception: {e}")

    def capture_error(self, error_message: str, error_type: str, context: Dict[str, Any] = None) -> None:
        """捕获错误信息"""
        try:
            with self._lock:
                # 检查隐私设置
                if not self.privacy_controller.is_error_reporting_enabled():
                    return

                # 生成错误ID
                error_id = self._generate_error_id_from_message(error_type, error_message)

                # 收集错误信息
                error_data = {
                    'error_id': error_id,
                    'error_type': error_type,
                    'error_message': error_message,
                    'breadcrumbs': list(self.breadcrumbs),
                    'context': context or {},
                    'timestamp': datetime.now().isoformat(),
                    'occurrence_count': self.error_counts[error_id] + 1,
                    'manual_capture': True
                }

                # 更新错误统计
                self.error_counts[error_id] += 1
                self.error_history.append({
                    'error_id': error_id,
                    'timestamp': datetime.now(),
                    'error_type': error_type
                })

                # 数据处理
                error_data = self.data_sanitizer.sanitize_error_data(error_data)
                error_data = self.privacy_controller.filter_sensitive_info(error_data)

                # 发送错误事件到telemetry client
                if self.telemetry_client:
                    # 生成用户ID（如果没有提供）
                    user_id = context.get('user_id') if context else None

                    self.telemetry_client.capture(
                        distinct_id=user_id,
                        event='error_occurred',
                        properties=error_data
                    )

                logger.debug(f"Error captured: {error_type} (ID: {error_id})")

        except Exception as e:
            logger.error(f"Failed to capture error: {e}")

    def add_breadcrumb(self, message: str, category: str, level: str = "info",
                      data: Dict[str, Any] = None) -> None:
        """添加面包屑"""
        try:
            with self._lock:
                breadcrumb = {
                    'message': message,
                    'category': category,
                    'level': level,
                    'timestamp': datetime.now().isoformat(),
                    'data': data or {}
                }

                # 数据清理
                breadcrumb = self.privacy_controller.filter_sensitive_info(breadcrumb)

                self.breadcrumbs.append(breadcrumb)
                logger.debug(f"Breadcrumb added: {category} - {message}")

        except Exception as e:
            logger.error(f"Failed to add breadcrumb: {e}")

    def track_operation_start(self, operation_name: str, context: Dict[str, Any] = None) -> None:
        """跟踪操作开始"""
        self.add_breadcrumb(
            message=f"Operation started: {operation_name}",
            category="operation",
            level="info",
            data=context
        )

    def track_operation_end(self, operation_name: str, success: bool,
                          duration: float = None, result: Dict[str, Any] = None) -> None:
        """跟踪操作结束"""
        level = "info" if success else "warning"
        message = f"Operation {'completed' if success else 'failed'}: {operation_name}"

        data = {'success': success}
        if duration is not None:
            data['duration_seconds'] = duration
        if result:
            data.update(result)

        self.add_breadcrumb(
            message=message,
            category="operation",
            level=level,
            data=data
        )

    def track_user_action(self, action: str, target: str = None, context: Dict[str, Any] = None) -> None:
        """跟踪用户操作"""
        message = f"User action: {action}"
        if target:
            message += f" on {target}"

        self.add_breadcrumb(
            message=message,
            category="user_action",
            level="info",
            data=context
        )

    def track_system_event(self, event: str, details: Dict[str, Any] = None) -> None:
        """跟踪系统事件"""
        self.add_breadcrumb(
            message=f"System event: {event}",
            category="system",
            level="info",
            data=details
        )

    def _generate_error_id(self, exception: Exception) -> str:
        """生成错误ID"""
        import hashlib

        # 使用异常类型和消息生成ID
        error_signature = f"{type(exception).__name__}:{str(exception)}"

        # 添加堆栈跟踪的关键部分
        tb = traceback.format_exc()
        if tb:
            # 提取关键的堆栈信息（文件名和行号）
            lines = tb.split('\n')
            key_lines = [line for line in lines if 'File "' in line and 'line' in line]
            if key_lines:
                error_signature += ":" + ":".join(key_lines[-3:])  # 最后3个关键行

        # 生成哈希
        return hashlib.md5(error_signature.encode()).hexdigest()[:8]

    def _generate_error_id_from_message(self, error_type: str, error_message: str) -> str:
        """从错误消息生成错误ID"""
        import hashlib

        error_signature = f"{error_type}:{error_message}"
        return hashlib.md5(error_signature.encode()).hexdigest()[:8]

    def _collect_system_info(self) -> Dict[str, Any]:
        try:
            system_info = {'platform': 'Windows', 'platform_version': platform.version(),
                           'python_version': platform.python_version(), 'cpu_count': os.cpu_count()}
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem_status = MEMORYSTATUSEX()
            mem_status.dwLength = ctypes.sizeof(mem_status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))

            system_info['memory_total'] = mem_status.ullTotalPhys
            system_info['memory_available'] = mem_status.ullAvailPhys
            try:
                target_path = os.path.abspath(__file__)
            except NameError:
                target_path = os.path.abspath(sys.executable)
            disk_usage = shutil.disk_usage(target_path)
            system_info['disk_usage_percent'] = (disk_usage.used / disk_usage.total) * 100

            return system_info

        except Exception as e:
            logger.warning(f"Failed to collect system info on Windows: {e}")
            return {'collection_error': str(e)}

    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计"""
        with self._lock:
            total_errors = sum(self.error_counts.values())
            unique_errors = len(self.error_counts)

            # 最常见的错误
            most_common = sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            # 最近的错误
            recent_errors = list(self.error_history)[-10:]

            return {
                'total_errors': total_errors,
                'unique_errors': unique_errors,
                'most_common_errors': [{'error_id': eid, 'count': count} for eid, count in most_common],
                'recent_errors': recent_errors,
                'breadcrumbs_count': len(self.breadcrumbs)
            }

    def clear_error_history(self) -> None:
        """清除错误历史"""
        with self._lock:
            self.error_counts.clear()
            self.error_history.clear()
            self.breadcrumbs.clear()
            logger.debug("Error history cleared")

    def add_exception_handler(self, handler: Callable[[Exception, Dict[str, Any]], None]) -> None:
        """添加自定义异常处理器"""
        self.exception_handlers.append(handler)

    def remove_exception_handler(self, handler: Callable) -> None:
        """移除自定义异常处理器"""
        if handler in self.exception_handlers:
            self.exception_handlers.remove(handler)

    def _call_custom_handlers(self, exception: Exception, context: Dict[str, Any]) -> None:
        """调用自定义异常处理器"""
        for handler in self.exception_handlers:
            try:
                handler(exception, context)
            except Exception as e:
                logger.error(f"Error in custom exception handler: {e}")

    def shutdown(self) -> None:
        """关闭错误追踪器"""
        try:
            # 恢复原始异常处理器
            self.restore_exception_handler()

            # 清理资源
            self.exception_handlers.clear()

            logger.debug("Error tracker shutdown complete")

        except Exception as e:
            logger.error(f"Error during error tracker shutdown: {e}")
