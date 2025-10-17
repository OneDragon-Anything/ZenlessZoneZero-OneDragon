"""
用户界面支持模块
为隐私控制界面提供后端支持
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from .privacy_controller import PrivacyController
from .models import PrivacySettings


logger = logging.getLogger(__name__)


class TelemetryUISupport:
    """遥测UI支持类"""

    def __init__(self, privacy_controller: PrivacyController):
        self.privacy_controller = privacy_controller

    def get_privacy_options(self) -> Dict[str, Any]:
        """获取隐私选项配置"""
        return {
            'data_collection': {
                'title': '数据收集设置',
                'description': '控制应用程序收集哪些类型的数据',
                'options': [
                    {
                        'key': 'collect_user_behavior',
                        'title': '用户行为分析',
                        'description': '收集用户操作、导航和功能使用数据，帮助改善用户体验',
                        'enabled': self.privacy_controller.is_analytics_enabled(),
                        'impact': 'low',
                        'examples': ['按钮点击', '页面导航', '功能使用统计']
                    },
                    {
                        'key': 'collect_error_data',
                        'title': '错误报告',
                        'description': '自动收集应用程序错误和崩溃信息，帮助开发者修复问题',
                        'enabled': self.privacy_controller.is_error_reporting_enabled(),
                        'impact': 'medium',
                        'examples': ['异常信息', '堆栈跟踪', '系统状态']
                    },
                    {
                        'key': 'collect_performance_data',
                        'title': '性能监控',
                        'description': '收集应用程序性能指标，帮助优化运行效率',
                        'enabled': self.privacy_controller.is_performance_monitoring_enabled(),
                        'impact': 'low',
                        'examples': ['启动时间', '操作耗时', '内存使用']
                    }
                ]
            },
            'data_processing': {
                'title': '数据处理设置',
                'description': '控制如何处理收集的数据',
                'options': [
                    {
                        'key': 'anonymize_user_data',
                        'title': '数据匿名化',
                        'description': '对个人身份信息进行匿名化处理，保护用户隐私',
                        'enabled': self.privacy_controller.should_anonymize_data(),
                        'impact': 'high',
                        'recommended': True
                    }
                ]
            }
        }

    def get_privacy_summary(self) -> Dict[str, Any]:
        """获取隐私设置摘要"""
        settings = self.privacy_controller.get_privacy_settings()

        enabled_features = []
        if settings.get('collect_user_behavior', False):
            enabled_features.append('用户行为分析')
        if settings.get('collect_error_data', False):
            enabled_features.append('错误报告')
        if settings.get('collect_performance_data', False):
            enabled_features.append('性能监控')

        privacy_level = self._calculate_privacy_level(settings)

        return {
            'telemetry_enabled': self.privacy_controller.is_telemetry_enabled(),
            'enabled_features': enabled_features,
            'anonymization_enabled': settings.get('anonymize_user_data', False),
            'privacy_level': privacy_level,
            'recommendations': self._get_privacy_recommendations(settings)
        }

    def _calculate_privacy_level(self, settings: Dict[str, Any]) -> str:
        """计算隐私级别"""
        score = 0

        # 数据收集影响隐私
        if settings.get('collect_user_behavior', False):
            score += 1
        if settings.get('collect_error_data', False):
            score += 2  # 错误数据可能包含更多敏感信息
        if settings.get('collect_performance_data', False):
            score += 1

        # 匿名化提高隐私
        if settings.get('anonymize_user_data', False):
            score -= 2

        if score <= 0:
            return 'high'
        elif score <= 2:
            return 'medium'
        else:
            return 'low'

    def _get_privacy_recommendations(self, settings: Dict[str, Any]) -> List[str]:
        """获取隐私建议"""
        recommendations = []

        if not settings.get('anonymize_user_data', False):
            recommendations.append('建议启用数据匿名化以更好地保护隐私')

        if settings.get('data_retention_days', 90) > 180:
            recommendations.append('考虑缩短数据保留时间以减少隐私风险')

        if (settings.get('collect_user_behavior', False) and
            settings.get('collect_error_data', False) and
            settings.get('collect_performance_data', False)):
            recommendations.append('您已启用所有数据收集功能，请确保这符合您的隐私偏好')

        if not any([
            settings.get('collect_user_behavior', False),
            settings.get('collect_error_data', False),
            settings.get('collect_performance_data', False)
        ]):
            recommendations.append('所有遥测功能已禁用，这将限制我们改善产品的能力')

        return recommendations

    def validate_privacy_settings(self, settings: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证隐私设置"""
        errors = []

        # 验证布尔值设置
        boolean_keys = [
            'collect_user_behavior',
            'collect_error_data',
            'collect_performance_data',
            'anonymize_user_data'
        ]

        for key in boolean_keys:
            if key in settings and not isinstance(settings[key], bool):
                errors.append(f'{key} 必须是布尔值')

        # 逻辑验证
        if (not settings.get('collect_user_behavior', True) and
            not settings.get('collect_error_data', True) and
            not settings.get('collect_performance_data', True)):
            # 如果所有功能都禁用，给出警告而不是错误
            pass

        return len(errors) == 0, errors

    def apply_privacy_settings(self, settings: Dict[str, Any]) -> Tuple[bool, str]:
        """应用隐私设置"""
        try:
            # 验证设置
            is_valid, errors = self.validate_privacy_settings(settings)
            if not is_valid:
                return False, f"设置验证失败: {'; '.join(errors)}"

            # 应用设置
            success = self.privacy_controller.update_privacy_settings(settings)

            if success:
                return True, "隐私设置已成功更新"
            else:
                return False, "保存隐私设置失败"

        except Exception as e:
            logger.error(f"Failed to apply privacy settings: {e}")
            return False, f"应用设置时发生错误: {str(e)}"

    def get_data_examples(self) -> Dict[str, Any]:
        """获取数据收集示例"""
        return {
            'user_behavior': {
                'title': '用户行为数据示例',
                'examples': [
                    {
                        'event': 'app_launched',
                        'data': {
                            'launch_time': '2.5秒',
                            'startup_mode': '正常启动',
                            'version': '2.0.0'
                        }
                    },
                    {
                        'event': 'automation_started',
                        'data': {
                            'automation_type': '每日任务',
                            'estimated_duration': '5分钟'
                        }
                    },
                    {
                        'event': 'ui_interaction',
                        'data': {
                            'element': '开始按钮',
                            'action': '点击',
                            'screen': '主界面'
                        }
                    }
                ]
            },
            'error_data': {
                'title': '错误数据示例',
                'examples': [
                    {
                        'event': 'error_occurred',
                        'data': {
                            'error_type': 'ImageRecognitionError',
                            'error_message': '无法识别游戏界面',
                            'operation': '图像识别',
                            'context': '战斗检测'
                        }
                    }
                ]
            },
            'performance_data': {
                'title': '性能数据示例',
                'examples': [
                    {
                        'event': 'performance_metric',
                        'data': {
                            'metric_name': 'image_processing_time',
                            'value': '150.5毫秒',
                            'algorithm': '模板匹配'
                        }
                    },
                    {
                        'event': 'performance_metric',
                        'data': {
                            'metric_name': 'memory_usage',
                            'value': '512MB',
                            'component': '主进程'
                        }
                    }
                ]
            }
        }

    def get_privacy_impact_info(self) -> Dict[str, Any]:
        """获取隐私影响信息"""
        return {
            'data_anonymization': {
                'title': '数据匿名化',
                'description': '我们如何保护您的隐私',
                'methods': [
                    '个人身份信息使用哈希算法处理',
                    '文件路径中的用户名被移除',
                    '敏感配置信息被过滤',
                    'IP地址和邮箱地址被匿名化'
                ]
            },
            'data_transmission': {
                'title': '数据传输',
                'description': '数据如何安全传输',
                'security_measures': [
                    '使用HTTPS加密传输',
                    '本地数据队列加密存储',
                    '网络故障时自动重试',
                    '传输失败时本地缓存'
                ]
            },
            'data_usage': {
                'title': '数据使用',
                'description': '收集的数据如何使用',
                'purposes': [
                    '改善软件功能和用户体验',
                    '识别和修复软件错误',
                    '优化软件性能',
                    '了解功能使用情况'
                ],
                'not_used_for': [
                    '不会出售给第三方',
                    '不会用于广告投放',
                    '不会用于用户画像',
                    '不会与其他服务共享'
                ]
            }
        }

    def export_privacy_report(self) -> Dict[str, Any]:
        """导出隐私报告"""
        try:
            settings = self.privacy_controller.get_privacy_settings()
            summary = self.get_privacy_summary()

            report = {
                'report_info': {
                    'generated_at': datetime.now().isoformat(),
                    'report_version': '1.0',
                    'user_consent': summary['telemetry_enabled']
                },
                'current_settings': settings,
                'privacy_summary': summary,
                'data_examples': self.get_data_examples(),
                'privacy_impact': self.get_privacy_impact_info()
            }

            logger.debug("Privacy report generated")
            return report

        except Exception as e:
            logger.error(f"Failed to export privacy report: {e}")
            return {'error': str(e)}
