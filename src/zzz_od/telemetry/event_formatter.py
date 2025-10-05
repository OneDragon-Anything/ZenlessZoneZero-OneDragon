"""
事件格式转换和标签策略实现
将遥测事件格式转换为Loki JSON日志格式，并生成相应的标签策略
"""
import json
import uuid
import platform
import hashlib
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from .models import TelemetryEvent, ErrorEvent, PerformanceEvent


@dataclass
class LokiLogEntry:
    """Loki日志条目数据结构"""
    message: str
    labels: Dict[str, str]
    metadata: Dict[str, Any]
    timestamp: Optional[str] = None


@dataclass
class EventFormatConfig:
    """事件格式化配置"""
    app_version: str = "unknown"
    environment: str = "production"
    instance_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    platform: str = field(default_factory=platform.system)

    # 标签配置
    max_label_length: int = 63  # Loki标签长度限制
    max_metadata_size: int = 65536  # 64KB限制



    # 性能统计
    events_formatted: int = 0
    format_errors: int = 0


class EventFormatter:
    """事件格式转换器"""

    def __init__(self, config: EventFormatConfig):
        self.config = config
        self._session_id = str(uuid.uuid4())
        self._fallback_user_id = self._generate_fallback_user_id()

    def _generate_fallback_user_id(self) -> str:
        """生成基于机器特征的回退用户ID"""
        try:
            # 使用机器特征生成稳定的匿名ID
            machine_id = f"{platform.node()}-{platform.machine()}"
            fallback_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, machine_id))
            return fallback_id
        except Exception:
            # 如果生成失败，使用会话级别的随机ID
            return f"session_{str(uuid.uuid4())[:8]}"

    def format_telemetry_event(self, event_data: Dict[str, Any]) -> LokiLogEntry:
        """将遥测事件格式转换为Loki日志格式"""
        try:
            event_type = event_data.get('type', 'capture')

            if event_type == 'capture':
                return self._format_capture_event(event_data)
            elif event_type == 'identify':
                return self._format_identify_event(event_data)
            elif event_type == 'alias':
                return self._format_alias_event(event_data)
            else:
                return self._format_generic_event(event_data)

        except Exception as e:
            self.config.format_errors += 1
            return self._create_error_entry(f"Format error: {str(e)}", event_data)
        finally:
            self.config.events_formatted += 1

    def _format_capture_event(self, event_data: Dict[str, Any]) -> LokiLogEntry:
        """格式化capture事件"""
        event_name = event_data.get('event', 'unknown_event')
        distinct_id = event_data.get('distinct_id') or self._fallback_user_id
        properties = event_data.get('properties', {})

        message = f"one_dragon_event:{event_name}"

        labels = self._generate_base_labels()
        labels.update(self._generate_event_labels(event_name, distinct_id))

        metadata = self._generate_standard_metadata(distinct_id, event_name, event_data)
        metadata.update(self._sanitize_properties(properties))

        return LokiLogEntry(
            message=message,
            labels=labels,
            metadata=metadata,
            timestamp=event_data.get('timestamp')
        )

    def _format_identify_event(self, event_data: Dict[str, Any]) -> LokiLogEntry:
        """格式化identify事件"""
        distinct_id = event_data.get('distinct_id') or self._fallback_user_id
        properties = event_data.get('properties', {})

        message = f"user_identify:{distinct_id}"

        labels = self._generate_base_labels()
        labels.update({
            'event_type': 'user_identify',
            'level': 'info',
            'user_uuid': distinct_id
        })

        metadata = self._generate_standard_metadata(distinct_id, 'user_identify', event_data)
        metadata.update(self._sanitize_properties(properties))

        return LokiLogEntry(
            message=message,
            labels=labels,
            metadata=metadata,
            timestamp=event_data.get('timestamp')
        )

    def _format_alias_event(self, event_data: Dict[str, Any]) -> LokiLogEntry:
        """格式化alias事件"""
        previous_id = event_data.get('previous_id', 'unknown')
        distinct_id = event_data.get('distinct_id') or self._fallback_user_id

        message = f"user_alias:{previous_id}->{distinct_id}"

        labels = self._generate_base_labels()
        labels.update({
            'event_type': 'user_alias',
            'level': 'info',
            'user_uuid': distinct_id
        })

        metadata = self._generate_standard_metadata(distinct_id, 'user_alias', event_data)
        metadata.update({
            'previous_id': previous_id,  # 直接使用UUID
            'new_id': distinct_id        # 直接使用UUID
        })

        return LokiLogEntry(
            message=message,
            labels=labels,
            metadata=metadata,
            timestamp=event_data.get('timestamp')
        )

    def _format_generic_event(self, event_data: Dict[str, Any]) -> LokiLogEntry:
        """格式化通用事件"""
        event_type = event_data.get('type', 'unknown')
        distinct_id = event_data.get('distinct_id') or self._fallback_user_id

        message = f"generic_event:{event_type}"

        labels = self._generate_base_labels()
        labels.update({
            'event_type': 'generic',
            'level': 'info',
            'user_uuid': distinct_id
        })

        metadata = self._generate_standard_metadata(distinct_id, event_type, event_data)
        metadata.update(self._sanitize_properties(event_data))

        return LokiLogEntry(
            message=message,
            labels=labels,
            metadata=metadata,
            timestamp=event_data.get('timestamp')
        )

    def format_error_event(self, error_event: ErrorEvent, distinct_id: str) -> LokiLogEntry:
        """格式化错误事件"""
        message = f"error:{error_event.error_type}:{error_event.error_message[:100]}"

        labels = self._generate_base_labels()
        labels.update({
            'event_type': 'error',
            'level': 'error',
            'error_type': self._sanitize_label_value(error_event.error_type),
            'user_uuid': distinct_id
        })

        metadata = self._generate_standard_metadata(distinct_id, 'error')
        metadata.update({
            'error_type': error_event.error_type,
            'error_message': error_event.error_message,
            'stack_trace': error_event.stack_trace,
            'context': error_event.context,
            'user_actions': error_event.user_actions,
            'system_info': error_event.system_info
        })

        return LokiLogEntry(
            message=message,
            labels=labels,
            metadata=metadata,
            timestamp=error_event.timestamp.isoformat()
        )

    def format_performance_event(self, perf_event: PerformanceEvent, distinct_id: str) -> LokiLogEntry:
        """格式化性能事件"""
        message = f"performance_metric:{perf_event.metric_name}={perf_event.value}{perf_event.unit}"

        labels = self._generate_base_labels()
        labels.update({
            'event_type': 'performance',
            'level': 'info',
            'metric_name': self._sanitize_label_value(perf_event.metric_name),
            'user_uuid': distinct_id
        })

        metadata = self._generate_standard_metadata(distinct_id, 'performance')
        metadata.update({
            'metric_name': perf_event.metric_name,
            'value': perf_event.value,
            'unit': perf_event.unit,
            'tags': perf_event.tags
        })

        return LokiLogEntry(
            message=message,
            labels=labels,
            metadata=metadata,
            timestamp=perf_event.timestamp.isoformat()
        )

    def _generate_base_labels(self) -> Dict[str, str]:
        """生成基础标签（所有日志都包含）"""
        return {
            'job': 'one_dragon',
            'project': 'zzz_od',
            'environment': self.config.environment,
            'app_version': self.config.app_version,
            'instance_id': self.config.instance_id,
            'platform': self.config.platform
        }

    def _generate_event_labels(self, event_name: str, distinct_id: str) -> Dict[str, str]:
        """生成事件特定标签"""
        feature = self._classify_event_feature(event_name)
        component = self._classify_event_component(event_name)
        operation = self._classify_event_operation(event_name)

        labels = {
            'event_type': 'telemetry',
            'event_name': self._sanitize_label_value(event_name),
            'level': 'info',
            'user_uuid': distinct_id
        }

        if feature:
            labels['feature'] = feature
        if component:
            labels['component'] = component
        if operation:
            labels['operation'] = operation

        return labels

    def _generate_standard_metadata(self, distinct_id: str, event_name: str, event_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成标准元数据字段"""
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'session_id': self._session_id,
            'user_uuid': distinct_id,    # 用户UUID标识
            'event_name': event_name,
            'app_version': self.config.app_version,
            'platform': self.config.platform,
            'instance_id': self.config.instance_id
        }
        return metadata

    def _classify_event_feature(self, event_name: str) -> Optional[str]:
        """根据事件名称分类功能"""
        event_lower = event_name.lower()

        if any(keyword in event_lower for keyword in ['auto', 'battle', 'fight']):
            return 'automation'
        elif any(keyword in event_lower for keyword in ['ui', 'click', 'button', 'menu']):
            return 'ui_interaction'
        elif any(keyword in event_lower for keyword in ['nav', 'page', 'screen']):
            return 'navigation'
        elif any(keyword in event_lower for keyword in ['config', 'setting']):
            return 'configuration'
        elif any(keyword in event_lower for keyword in ['start', 'launch', 'init']):
            return 'lifecycle'
        else:
            return None

    def _classify_event_component(self, event_name: str) -> Optional[str]:
        """根据事件名称分类组件"""
        event_lower = event_name.lower()

        if 'withered' in event_lower:
            return 'withered_domain'
        elif 'void' in event_lower:
            return 'lost_void'
        elif 'patrol' in event_lower:
            return 'world_patrol'
        elif any(keyword in event_lower for keyword in ['battle', 'fight']):
            return 'battle_system'
        elif any(keyword in event_lower for keyword in ['ui', 'interface']):
            return 'user_interface'
        else:
            return None

    def _classify_event_operation(self, event_name: str) -> Optional[str]:
        """根据事件名称分类操作"""
        event_lower = event_name.lower()

        if any(keyword in event_lower for keyword in ['start', 'begin']):
            return 'start'
        elif any(keyword in event_lower for keyword in ['end', 'finish', 'complete']):
            return 'complete'
        elif any(keyword in event_lower for keyword in ['error', 'fail']):
            return 'error'
        elif any(keyword in event_lower for keyword in ['click', 'press']):
            return 'interact'
        else:
            return None

    def _sanitize_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """清理和验证属性数据"""
        sanitized = {}

        for key, value in properties.items():
            clean_key = self._sanitize_metadata_key(key)
            clean_value = self._sanitize_metadata_value(value)

            if clean_key and clean_value is not None:
                sanitized[clean_key] = clean_value

        # 检查元数据大小
        metadata_str = json.dumps(sanitized, default=str)
        if len(metadata_str.encode('utf-8')) > self.config.max_metadata_size:
            sanitized = self._truncate_metadata(sanitized)

        return sanitized

    def _sanitize_label_value(self, value: str) -> str:
        """清理标签值，确保符合Loki要求"""
        if not value:
            return 'unknown'

        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', str(value))

        if len(sanitized) > self.config.max_label_length:
            sanitized = sanitized[:self.config.max_label_length]

        return sanitized.lower()

    def _sanitize_metadata_key(self, key: str) -> str:
        """清理元数据键名"""
        if not key or not isinstance(key, str):
            return ""

        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', key)

        if sanitized and sanitized[0].isdigit():
            sanitized = f"field_{sanitized}"

        return sanitized

    def _sanitize_metadata_value(self, value: Any) -> Any:
        """清理元数据值"""
        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return value
        elif isinstance(value, (list, tuple)):
            return [self._sanitize_metadata_value(item) for item in value]
        elif isinstance(value, dict):
            return {
                self._sanitize_metadata_key(k): self._sanitize_metadata_value(v)
                for k, v in value.items()
            }
        else:
            return str(value)

    def _truncate_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """截断元数据以符合大小限制"""
        truncated = {}
        current_size = 0

        for key, value in metadata.items():
            item_str = json.dumps({key: value}, default=str)
            item_size = len(item_str.encode('utf-8'))

            if current_size + item_size <= self.config.max_metadata_size:
                truncated[key] = value
                current_size += item_size
            else:
                truncated['_truncated'] = True
                break

        return truncated



    def _create_error_entry(self, error_message: str, original_data: Dict[str, Any]) -> LokiLogEntry:
        """创建格式化错误的日志条目"""
        labels = self._generate_base_labels()
        labels.update({
            'event_type': 'format_error',
            'level': 'error'
        })

        metadata = {
            'error_message': error_message,
            'original_data': str(original_data)[:1000],
            'timestamp': datetime.now().isoformat()
        }

        return LokiLogEntry(
            message=f"format_error:{error_message}",
            labels=labels,
            metadata=metadata
        )

    def get_statistics(self) -> Dict[str, Any]:
        """获取格式化统计信息"""
        return {
            'events_formatted': self.config.events_formatted,
            'format_errors': self.config.format_errors,
            'success_rate': (
                (self.config.events_formatted - self.config.format_errors) /
                max(self.config.events_formatted, 1)
            ) * 100,
            'session_id': self._session_id,
            'instance_id': self.config.instance_id
        }


class LabelStrategy:
    """标签策略管理器"""

    @staticmethod
    def get_recommended_labels() -> Dict[str, List[str]]:
        """获取推荐的标签配置"""
        return {
            'base_labels': [
                'job',
                'environment',
                'app_version',
                'instance_id',
                'platform'
            ],
            'event_labels': [
                'event_type',
                'event_name',
                'level',
                'user_id'
            ],
            'feature_labels': [
                'feature',
                'component',
                'operation'
            ],
            'error_labels': [
                'error_type'
            ],
            'performance_labels': [
                'metric_name'
            ]
        }

    @staticmethod
    def validate_labels(labels: Dict[str, str]) -> Tuple[bool, List[str]]:
        """验证标签是否符合Loki要求"""
        errors = []

        for key, value in labels.items():
            if not key or not isinstance(key, str):
                errors.append(f"Invalid label key: {key}")
                continue

            if not value or not isinstance(value, str):
                errors.append(f"Invalid label value for key '{key}': {value}")
                continue

            if len(value) > 63:
                errors.append(f"Label value too long for key '{key}': {len(value)} > 63")

        return len(errors) == 0, errors