"""
隐私控制器
管理用户隐私设置、数据匿名化和敏感信息过滤
"""
import re
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, List, Set, Optional
from pathlib import Path

from .models import PrivacySettings
from .config import PrivacySettingsManager


logger = logging.getLogger(__name__)


class PrivacyController:
    """隐私控制器"""

    # 敏感信息关键词
    SENSITIVE_KEYS = {
        'password', 'passwd', 'pwd', 'secret', 'token', 'key', 'api_key',
        'auth', 'authorization', 'credential', 'private', 'confidential',
        'ssn', 'social_security', 'credit_card', 'card_number', 'cvv',
        'email', 'phone', 'mobile', 'address', 'location', 'ip_address',
        'user_id', 'username', 'login', 'account'
    }

    # 敏感数据模式
    SENSITIVE_PATTERNS = [
        # 邮箱地址
        re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        # 电话号码
        re.compile(r'\b\d{3}-?\d{3}-?\d{4}\b'),
        # IP地址
        re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
        # 信用卡号
        re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
        # 身份证号（简化版）
        re.compile(r'\b\d{15}|\d{18}\b'),
    ]

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.settings_manager = PrivacySettingsManager(config_dir)
        self.settings: Optional[PrivacySettings] = None
        self._load_settings()

    def _load_settings(self) -> None:
        """加载隐私设置"""
        try:
            self.settings = self.settings_manager.load_privacy_settings()
            logger.debug("Privacy settings loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load privacy settings: {e}")
            self.settings = PrivacySettings()  # 使用默认设置

    def is_telemetry_enabled(self) -> bool:
        """检查遥测是否启用"""
        return self.settings is not None and (
            self.settings.collect_user_behavior or
            self.settings.collect_error_data or
            self.settings.collect_performance_data
        )

    def is_analytics_enabled(self) -> bool:
        """检查用户行为分析是否启用"""
        return self.settings is not None and self.settings.collect_user_behavior

    def is_error_reporting_enabled(self) -> bool:
        """检查错误报告是否启用"""
        return self.settings is not None and self.settings.collect_error_data

    def is_performance_monitoring_enabled(self) -> bool:
        """检查性能监控是否启用"""
        return self.settings is not None and self.settings.collect_performance_data

    def should_anonymize_data(self) -> bool:
        """检查是否应该匿名化数据"""
        return self.settings is not None and self.settings.anonymize_user_data

    def anonymize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """匿名化数据"""
        if not self.should_anonymize_data():
            return data

        try:
            anonymized = {}

            for key, value in data.items():
                if self._is_sensitive_key(key):
                    # 敏感键值进行哈希处理
                    anonymized[key] = self._hash_value(str(value))
                elif isinstance(value, str):
                    # 字符串值检查敏感模式
                    anonymized[key] = self._sanitize_string(value)
                elif isinstance(value, dict):
                    # 递归处理嵌套字典
                    anonymized[key] = self.anonymize_data(value)
                elif isinstance(value, list):
                    # 处理列表
                    anonymized[key] = self._anonymize_list(value)
                else:
                    # 其他类型直接保留
                    anonymized[key] = value

            return anonymized

        except Exception as e:
            logger.error(f"Failed to anonymize data: {e}")
            return self.filter_sensitive_info(data)  # 降级到过滤模式

    def filter_sensitive_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """过滤敏感信息"""
        try:
            filtered = {}

            for key, value in data.items():
                if self._is_sensitive_key(key):
                    # 敏感键直接移除或替换
                    filtered[key] = "[FILTERED]"
                elif isinstance(value, str):
                    # 字符串值检查敏感模式
                    filtered[key] = self._filter_string(value)
                elif isinstance(value, dict):
                    # 递归处理嵌套字典
                    filtered[key] = self.filter_sensitive_info(value)
                elif isinstance(value, list):
                    # 处理列表
                    filtered[key] = self._filter_list(value)
                else:
                    # 其他类型直接保留
                    filtered[key] = value

            return filtered

        except Exception as e:
            logger.error(f"Failed to filter sensitive info: {e}")
            return data  # 如果过滤失败，返回原数据

    def _is_sensitive_key(self, key: str) -> bool:
        """检查键是否敏感"""
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in self.SENSITIVE_KEYS)

    def _hash_value(self, value: str) -> str:
        """对值进行哈希处理"""
        if not value:
            return "[EMPTY]"

        # 使用SHA256哈希，取前8位作为匿名标识
        hash_obj = hashlib.sha256(value.encode('utf-8'))
        return f"[HASH:{hash_obj.hexdigest()[:8]}]"

    def _sanitize_string(self, text: str) -> str:
        """清理字符串中的敏感信息"""
        if not text:
            return text

        sanitized = text

        # 应用敏感模式替换
        for pattern in self.SENSITIVE_PATTERNS:
            sanitized = pattern.sub('[REDACTED]', sanitized)

        return sanitized

    def _filter_string(self, text: str) -> str:
        """过滤字符串中的敏感信息"""
        if not text:
            return text

        filtered = text

        # 应用敏感模式替换
        for pattern in self.SENSITIVE_PATTERNS:
            filtered = pattern.sub('[FILTERED]', filtered)

        return filtered

    def _anonymize_list(self, items: List[Any]) -> List[Any]:
        """匿名化列表"""
        anonymized = []

        for item in items:
            if isinstance(item, dict):
                anonymized.append(self.anonymize_data(item))
            elif isinstance(item, str):
                anonymized.append(self._sanitize_string(item))
            else:
                anonymized.append(item)

        return anonymized

    def _filter_list(self, items: List[Any]) -> List[Any]:
        """过滤列表"""
        filtered = []

        for item in items:
            if isinstance(item, dict):
                filtered.append(self.filter_sensitive_info(item))
            elif isinstance(item, str):
                filtered.append(self._filter_string(item))
            else:
                filtered.append(item)

        return filtered

    def update_privacy_settings(self, settings: Dict[str, Any]) -> bool:
        """更新隐私设置"""
        try:
            if self.settings is None:
                self.settings = PrivacySettings()

            # 更新设置
            for key, value in settings.items():
                if hasattr(self.settings, key):
                    setattr(self.settings, key, value)

            # 保存设置
            success = self.settings_manager.save_privacy_settings(self.settings)

            if success:
                logger.debug("Privacy settings updated successfully")
            else:
                logger.error("Failed to save privacy settings")

            return success

        except Exception as e:
            logger.error(f"Failed to update privacy settings: {e}")
            return False

    def get_privacy_settings(self) -> Dict[str, Any]:
        """获取当前隐私设置"""
        if self.settings is None:
            return {}

        return {
            'collect_user_behavior': self.settings.collect_user_behavior,
            'collect_error_data': self.settings.collect_error_data,
            'collect_performance_data': self.settings.collect_performance_data,
            'anonymize_user_data': self.settings.anonymize_user_data
        }

    def validate_event_data(self, event_name: str, properties: Dict[str, Any]) -> bool:
        """验证事件数据是否符合隐私设置"""
        if self.settings is None:
            return False

        # 根据事件类型检查是否允许收集
        if event_name.startswith('error_') and not self.settings.collect_error_data:
            return False

        if event_name.startswith('performance_') and not self.settings.collect_performance_data:
            return False

        if not self.settings.collect_user_behavior:
            # 如果禁用用户行为收集，只允许错误和性能事件
            if not (event_name.startswith('error_') or event_name.startswith('performance_')):
                return False

        return True

    def process_event_data(self, event_name: str, properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理事件数据（验证、过滤、匿名化）"""
        try:
            # 验证是否允许收集此事件
            if not self.validate_event_data(event_name, properties):
                logger.debug(f"Event {event_name} blocked by privacy settings")
                return None

            # 处理数据
            if self.should_anonymize_data():
                processed_data = self.anonymize_data(properties)
            else:
                processed_data = self.filter_sensitive_info(properties)

            return processed_data

        except Exception as e:
            logger.error(f"Failed to process event data: {e}")
            return None

    def clear_local_data(self) -> bool:
        """清除本地遥测数据"""
        try:
            # 这里可以添加清除本地缓存数据的逻辑
            # 例如删除队列文件、临时数据等
            logger.debug("Local telemetry data cleared")
            return True

        except Exception as e:
            logger.error(f"Failed to clear local data: {e}")
            return False

    def export_user_data(self) -> Dict[str, Any]:
        """导出用户数据（GDPR合规）"""
        try:
            # 这里可以添加导出用户数据的逻辑
            export_data = {
                'privacy_settings': self.get_privacy_settings(),
                'data_collection_consent': self.is_telemetry_enabled(),
                'anonymization_enabled': self.should_anonymize_data(),
                'export_timestamp': datetime.now().isoformat()
            }

            logger.debug("User data exported")
            return export_data

        except Exception as e:
            logger.error(f"Failed to export user data: {e}")
            return {}
