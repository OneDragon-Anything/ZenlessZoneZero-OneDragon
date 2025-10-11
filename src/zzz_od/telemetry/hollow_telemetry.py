"""
迷失之地遥测装饰器
"""
import time
import logging
from functools import wraps
from typing import Any, Dict, Optional, Callable

logger = logging.getLogger(__name__)


def track_hollow_level_progress(func: Callable) -> Callable:
    """
    跟踪迷失之地层数进度的装饰器
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # 获取遥测管理器
        telemetry = getattr(self, '_get_telemetry', lambda: None)()
        if not telemetry:
            return func(self, *args, **kwargs)

        # 获取层数信息
        level_info = None
        if hasattr(self, 'ctx') and hasattr(self.ctx, 'withered_domain') and hasattr(self.ctx.withered_domain, 'level_info'):
            level_info = self.ctx.withered_domain.level_info

        # 初始化层数跟踪状态
        if not hasattr(self, '_hollow_level_tracking'):
            self._hollow_level_tracking = {
                'current_level': -1,
                'current_phase': -1,
                'level_start_time': 0,
                'level_times': {}
            }

        tracking = self._hollow_level_tracking

        if level_info:
            current_level = level_info.level
            current_phase = level_info.phase

            # 检查是否进入新层
            if current_level != tracking['current_level'] or current_phase != tracking['current_phase']:
                # 记录上一层的耗时
                if tracking['current_level'] > 0 and tracking['level_start_time'] > 0:
                    level_key = f"level_{tracking['current_level']}_phase_{tracking['current_phase']}"
                    duration = time.time() - tracking['level_start_time']
                    tracking['level_times'][level_key] = duration

                    # 特别关注倒数第二层（通常是第2层）
                    if tracking['current_level'] == 2:
                        telemetry.track_custom_event('hollow_second_last_level_completed', {
                            'level': tracking['current_level'],
                            'phase': tracking['current_phase'],
                            'duration_seconds': duration,
                            'event_category': 'hollow_progress'
                        })
                        logger.info(f"迷失之地倒数第二层完成，耗时: {duration:.2f}秒")

                # 开始新层计时
                tracking['current_level'] = current_level
                tracking['current_phase'] = current_phase
                tracking['level_start_time'] = time.time()

                # 记录进入新层
                telemetry.track_custom_event('hollow_level_entered', {
                    'level': current_level,
                    'phase': current_phase,
                    'event_category': 'hollow_progress'
                })

                # 特别记录倒数第二层开始
                if current_level == 2:
                    logger.info(f"迷失之地倒数第二层开始，层数: {current_level}, 阶段: {current_phase}")

        # 执行原方法
        result = func(self, *args, **kwargs)

        return result

    return wrapper


class HollowTelemetryMixin:
    """
    迷失之地遥测混入类
    为迷失之地相关类提供遥测功能
    """

    def _get_telemetry(self):
        """获取遥测管理器"""
        if hasattr(self, 'ctx') and hasattr(self.ctx, 'telemetry'):
            return self.ctx.telemetry
        return None

    def track_hollow_event(self, event_name: str, properties: Dict[str, Any] = None) -> None:
        """跟踪迷失之地事件"""
        telemetry = self._get_telemetry()
        if not telemetry:
            return

        event_properties = {
            'event_category': 'hollow_event',
            **(properties or {})
        }

        telemetry.track_custom_event(event_name, event_properties)
        logger.debug(f"Tracked hollow event: {event_name}")
