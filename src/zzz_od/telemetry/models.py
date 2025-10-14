"""
遥测数据模型定义
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid


@dataclass
class TelemetryEvent:
    """遥测事件数据结构"""
    event_name: str
    user_uuid: str
    properties: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    app_version: str = ""


@dataclass
class ErrorEvent:
    """错误事件数据结构"""
    error_type: str
    error_message: str
    stack_trace: str
    context: Dict[str, Any]
    user_actions: List[str] = field(default_factory=list)
    system_info: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceEvent:
    """性能事件数据结构"""
    metric_name: str
    value: float
    unit: str
    tags: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TelemetryConfig:
    """遥测配置"""
    enabled: bool = True
    analytics_enabled: bool = True
    error_reporting_enabled: bool = True
    performance_monitoring_enabled: bool = True

    flush_interval: int = 5  # 秒
    max_queue_size: int = 1000
    debug_mode: bool = False

    # 后端配置（现在只支持Loki）
    backend_type: str = "loki"

    # Loki相关配置
    loki_url: str = ""
    loki_tenant_id: str = ""
    loki_auth_token: str = ""
    loki_labels: Dict[str, str] = field(default_factory=dict)

    # 阿里云 WebTracking 配置
    aliyun_web_tracking_enabled: bool = True
    aliyun_web_tracking_endpoint: str = ""

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典更新配置"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


@dataclass
class PrivacySettings:
    """隐私设置"""
    collect_user_behavior: bool = True
    collect_error_data: bool = True
    collect_performance_data: bool = True
    anonymize_user_data: bool = True
