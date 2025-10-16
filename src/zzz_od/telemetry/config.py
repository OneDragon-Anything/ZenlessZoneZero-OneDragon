"""
遥测配置管理
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .models import TelemetryConfig, PrivacySettings


logger = logging.getLogger(__name__)


class TelemetryConfigLoader:
    """遥测配置加载器"""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.config_file = config_dir / "telemetry.yml"

    def load_config(self) -> TelemetryConfig:
        """加载遥测配置"""
        config = TelemetryConfig()

        try:
            # 从环境变量加载敏感配置
            self._load_from_env(config)

            # 从配置文件加载其他设置
            if self.config_file.exists():
                self._load_from_file(config)
            else:
                logger.debug(f"Telemetry config file not found: {self.config_file}")
                self._create_default_config_file()

        except Exception as e:
            logger.debug(f"Failed to load telemetry config: {e}")

        return config

    def _load_from_env(self, config: TelemetryConfig) -> None:
        """从env.yml加载配置"""
        # 从环境变量加载Loki认证信息
        env_yml_path = self.config_dir / "env.yml"
        if env_yml_path.exists():
            try:
                with open(env_yml_path, 'r', encoding='utf-8') as f:
                    env_config = yaml.safe_load(f)
                    if env_config:
                        # 加载Loki认证信息
                        if 'loki_tenant_id' in env_config:
                            config.loki_tenant_id = env_config['loki_tenant_id']
                            logger.debug("Loaded Loki tenant ID from env.yml")
                        if 'loki_auth_token' in env_config:
                            config.loki_auth_token = env_config['loki_auth_token']
                            logger.debug("Loaded Loki auth token from env.yml")
            except Exception as e:
                logger.debug(f"Failed to load config from env.yml: {e}")

        # 如果没有从环境变量加载到认证信息，使用硬编码的fallback
        if not config.loki_tenant_id:
            config.loki_tenant_id = "1109268"
            logger.debug("Using hardcoded Loki tenant ID")

        if not config.loki_auth_token:
            config.loki_auth_token = "glc_eyJvIjoiMTMyOTM0MSIsIm4iOiJ6enotb2Qtenp6LW9kIiwiayI6IjhzYnVvMkNXNkU4czg3Nlk0UjBiMEhJTSIsIm0iOnsiciI6InVzIn19"
            logger.debug("Using hardcoded Loki auth token")

        logger.debug(f"Final Loki tenant ID: {'***' if config.loki_tenant_id else 'None'}")
        logger.debug(f"Final Loki auth token: {'***' if config.loki_auth_token else 'None'}")

    def _load_from_file(self, config: TelemetryConfig) -> None:
        """从配置文件加载配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)

            if yaml_data and 'telemetry' in yaml_data:
                telemetry_config = yaml_data['telemetry']

                # 基本设置
                config.enabled = telemetry_config.get('enabled', config.enabled)

                # 功能开关
                features = telemetry_config.get('features', {})
                config.analytics_enabled = features.get('analytics', config.analytics_enabled)
                config.error_reporting_enabled = features.get('error_reporting', config.error_reporting_enabled)
                config.performance_monitoring_enabled = features.get('performance_monitoring', config.performance_monitoring_enabled)

                # 性能设置
                performance = telemetry_config.get('performance', {})
                config.flush_interval = performance.get('flush_interval', config.flush_interval)
                config.max_queue_size = performance.get('max_queue_size', config.max_queue_size)

                # 调试设置
                debug = telemetry_config.get('debug', {})
                config.debug_mode = debug.get('enabled', config.debug_mode)

                # 后端配置
                config.backend_type = telemetry_config.get('backend_type', config.backend_type)

                # Loki配置
                loki_config = telemetry_config.get('loki', {})
                config.loki_url = loki_config.get('url', config.loki_url)
                config.loki_tenant_id = loki_config.get('tenant_id', config.loki_tenant_id)
                config.loki_auth_token = loki_config.get('auth_token', config.loki_auth_token)
                config.loki_labels = loki_config.get('labels', config.loki_labels)

                # 阿里云 WebTracking 配置
                aliyun_config = telemetry_config.get('aliyun_web_tracking', {})
                config.aliyun_web_tracking_enabled = aliyun_config.get(
                    'enabled', config.aliyun_web_tracking_enabled
                )
                config.aliyun_web_tracking_endpoint = aliyun_config.get(
                    'endpoint', config.aliyun_web_tracking_endpoint
                )

        except Exception as e:
            logger.debug(f"Failed to load config from file: {e}")

    def _create_default_config_file(self) -> None:
        """创建默认配置文件"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)

            default_config = {
                'telemetry': {
                    'enabled': True,
                    'backend_type': 'loki',
                    'features': {
                        'analytics': True,
                        'error_reporting': True,
                        'performance_monitoring': True
                    },
                    'loki': {
                        'url': 'https://logs-prod-012.grafana.net',
                        'tenant_id': '1109268',
                        'auth_token': 'glc_eyJvIjoiMTMyOTM0MSIsIm4iOiJ6enotb2Qtenp6LW9kIiwiayI6IjhzYnVvMkNXNkU4czg3Nlk0UjBiMEhJTSIsIm0iOnsiciI6InVzIn19',
                        'labels': {
                            'job': 'one_dragon',
                            'project': 'zzz_od',
                            'environment': 'production'
                        }
                    },
                    'privacy': {
                        'anonymize_user_data': True,
                        'collect_sensitive_data': False
                    },
                    'performance': {
                        'flush_interval': 5,
                        'max_queue_size': 1000,
                        'batch_size': 100
                    },
                    'debug': {
                        'enabled': False,
                        'log_events': False,
                        'validate_data': True
                    },
                    'aliyun_web_tracking': {
                        'enabled': False,
                        'endpoint': ''
                    }
                }
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)

            logger.debug(f"Created default telemetry config: {self.config_file}")

        except Exception as e:
            logger.debug(f"Failed to create default config file: {e}")

    def save_config(self, config: TelemetryConfig) -> bool:
        """保存配置到文件"""
        try:
            config_data = {
                'telemetry': {
                    'enabled': config.enabled,
                    'backend_type': config.backend_type,
                    'features': {
                        'analytics': config.analytics_enabled,
                        'error_reporting': config.error_reporting_enabled,
                        'performance_monitoring': config.performance_monitoring_enabled
                    },
                    'loki': {
                        'url': config.loki_url,
                        'tenant_id': config.loki_tenant_id,
                        'auth_token': config.loki_auth_token,
                        'labels': config.loki_labels
                    },
                    'aliyun_web_tracking': {
                        'enabled': config.aliyun_web_tracking_enabled,
                        'endpoint': config.aliyun_web_tracking_endpoint
                    },
                    'performance': {
                        'flush_interval': config.flush_interval,
                        'max_queue_size': config.max_queue_size
                    },
                    'debug': {
                        'enabled': config.debug_mode
                    }
                }
            }

            self.config_dir.mkdir(parents=True, exist_ok=True)

            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

            logger.debug("Telemetry config saved successfully")
            return True

        except Exception as e:
            logger.debug(f"Failed to save telemetry config: {e}")
            return False


class PrivacySettingsManager:
    """隐私设置管理器"""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.privacy_file = config_dir / "privacy.yml"

    def load_privacy_settings(self) -> PrivacySettings:
        """加载隐私设置"""
        settings = PrivacySettings()

        try:
            if self.privacy_file.exists():
                with open(self.privacy_file, 'r', encoding='utf-8') as f:
                    yaml_data = yaml.safe_load(f)

                if yaml_data and 'privacy' in yaml_data:
                    privacy_data = yaml_data['privacy']

                    settings.collect_user_behavior = privacy_data.get('collect_user_behavior', settings.collect_user_behavior)
                    settings.collect_error_data = privacy_data.get('collect_error_data', settings.collect_error_data)
                    settings.collect_performance_data = privacy_data.get('collect_performance_data', settings.collect_performance_data)
                    settings.anonymize_user_data = privacy_data.get('anonymize_user_data', settings.anonymize_user_data)

        except Exception as e:
            logger.error(f"Failed to load privacy settings: {e}")

        return settings

    def save_privacy_settings(self, settings: PrivacySettings) -> bool:
        """保存隐私设置"""
        try:
            privacy_data = {
                'privacy': {
                    'collect_user_behavior': settings.collect_user_behavior,
                    'collect_error_data': settings.collect_error_data,
                    'collect_performance_data': settings.collect_performance_data,
                    'anonymize_user_data': settings.anonymize_user_data,
                }
            }

            self.config_dir.mkdir(parents=True, exist_ok=True)

            with open(self.privacy_file, 'w', encoding='utf-8') as f:
                yaml.dump(privacy_data, f, default_flow_style=False, allow_unicode=True)

            logger.debug("Privacy settings saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save privacy settings: {e}")
            return False
