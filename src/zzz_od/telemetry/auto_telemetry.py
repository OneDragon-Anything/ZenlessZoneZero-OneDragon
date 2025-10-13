"""
自动遥测装饰器和混入类
为父类提供自动遥测功能，子类无需手动添加遥测代码
"""
import time
import logging
from functools import wraps
from typing import Any, Dict, Optional, Callable


logger = logging.getLogger(__name__)


def auto_telemetry_method(event_name: str = None, track_performance: bool = True):
    """
    自动遥测方法装饰器

     event_name: 自定义事件名称，如果不提供则使用方法名
        track_performance: 是否跟踪性能指标
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # 获取遥测管理器
            telemetry = getattr(self, '_get_telemetry', lambda: None)()
            if not telemetry:
                return func(self, *args, **kwargs)

            # 确定事件名称
            actual_event_name = event_name or f"{self.__class__.__name__}.{func.__name__}"

            # 记录开始时间
            start_time = time.time() if track_performance else None

            try:
                # 执行原方法
                result = func(self, *args, **kwargs)

                # 计算执行时间
                duration = time.time() - start_time if start_time else None

                # 记录成功事件
                event_properties = {
                    'class': self.__class__.__name__,
                    'method': func.__name__,
                    'success': True
                }

                if duration is not None:
                    event_properties['duration'] = duration

                telemetry.capture_event(actual_event_name, event_properties)

                return result

            except Exception as e:
                # 计算执行时间
                duration = time.time() - start_time if start_time else None

                # 记录错误
                telemetry.capture_error(e, {
                    'class': self.__class__.__name__,
                    'method': func.__name__,
                    'event_name': actual_event_name,
                    'duration': duration
                })

                raise

        return wrapper
    return decorator


class AutoTelemetryMixin:
    """
    自动遥测混入类
    为任何类提供自动遥测功能
    """

    def _get_telemetry(self):
        """获取遥测管理器"""
        # 尝试从不同的属性获取遥测管理器
        if hasattr(self, 'ctx') and hasattr(self.ctx, 'telemetry'):
            return self.ctx.telemetry
        elif hasattr(self, 'telemetry'):
            return self.telemetry
        else:
            return None


class TelemetryApplicationMixin(AutoTelemetryMixin):
    """
    应用类专用的遥测混入
    """

    def _get_telemetry_properties(self) -> Optional[Dict[str, Any]]:
        """应用类特定的遥测属性"""
        properties = {}

        # 添加应用特定属性
        if hasattr(self, 'app_id'):
            properties['app_id'] = self.app_id
        if hasattr(self, 'need_check_game_win'):
            properties['need_check_game_win'] = self.need_check_game_win

        return properties if properties else None

    @auto_telemetry_method("application_execute", track_performance=True)
    def execute(self):
        """自动跟踪应用执行"""
        # 这个装饰器会自动处理遥测
        pass

    @auto_telemetry_method("application_stop", track_performance=False)
    def stop(self):
        """自动跟踪应用停止"""
        pass


class TelemetryInterfaceMixin(AutoTelemetryMixin):
    """
    界面类专用的遥测混入
    """

    def _get_telemetry_properties(self) -> Optional[Dict[str, Any]]:
        """界面类特定的遥测属性"""
        properties = {}

        # 添加界面特定属性
        if hasattr(self, 'object_name'):
            properties['interface_name'] = self.object_name
        if hasattr(self, 'nav_text'):
            properties['nav_text'] = self.nav_text

        return properties if properties else None

    def track_interface_shown(self):
        """跟踪界面显示"""
        telemetry = self._get_telemetry()
        if not telemetry:
            return

        properties = {
            'interface_name': getattr(self, 'object_name', 'unknown'),
            'action': 'shown'
        }

        custom_props = self._get_telemetry_properties()
        if custom_props:
            properties.update(custom_props)

        telemetry.track_custom_event('interface_shown', properties)

    def track_interface_hidden(self):
        """跟踪界面隐藏"""
        telemetry = self._get_telemetry()
        if not telemetry:
            return

        properties = {
            'interface_name': getattr(self, 'object_name', 'unknown'),
            'action': 'hidden'
        }

        custom_props = self._get_telemetry_properties()
        if custom_props:
            properties.update(custom_props)

        telemetry.track_custom_event('interface_hidden', properties)


class TelemetryOperationMixin(AutoTelemetryMixin):
    """
    操作类专用的遥测混入
    """

    def _get_telemetry_properties(self) -> Optional[Dict[str, Any]]:
        """操作类特定的遥测属性"""
        properties = {}

        # 添加操作特定属性
        if hasattr(self, 'op_name'):
            properties['operation_name'] = self.op_name
        if hasattr(self, 'timeout_seconds'):
            properties['timeout_seconds'] = self.timeout_seconds
        if hasattr(self, 'need_check_game_win'):
            properties['need_check_game_win'] = self.need_check_game_win

        return properties if properties else None
