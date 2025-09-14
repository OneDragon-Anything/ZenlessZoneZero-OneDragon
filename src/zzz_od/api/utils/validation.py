"""
配置验证和文件操作工具

提供统一的配置验证和文件操作错误处理
"""
from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from zzz_od.api.battle_assistant_models import (
    ConfigurationError,
    FileOperationError,
    ValidationError,
    ConfigNotFoundError,
    TemplateNotFoundError,
    AccessDeniedError
)


class ConfigValidator:
    """配置验证器"""

    @staticmethod
    def validate_config_name(config_name: str, config_type: str) -> None:
        """验证配置名称"""
        if not config_name or not config_name.strip():
            raise ValidationError("配置名称不能为空")

        if len(config_name) > 100:
            raise ValidationError("配置名称过长，最大长度为100字符")

        # 检查非法字符
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in config_name:
                raise ValidationError(f"配置名称包含非法字符: {char}")

    @staticmethod
    def validate_screenshot_interval(interval: float) -> None:
        """验证截图间隔"""
        if interval < 0.01:
            raise ValidationError("截图间隔不能小于0.01秒")
        if interval > 1.0:
            raise ValidationError("截图间隔不能大于1.0秒")

    @staticmethod
    def validate_sensitivity(sensitivity: float) -> None:
        """验证敏感度"""
        if sensitivity < 0.0:
            raise ValidationError("敏感度不能小于0.0")
        if sensitivity > 1.0:
            raise ValidationError("敏感度不能大于1.0")

    @staticmethod
    def validate_reaction_time(reaction_time: float) -> None:
        """验证反应时间"""
        if reaction_time < 0.0:
            raise ValidationError("反应时间不能小于0.0秒")
        if reaction_time > 1.0:
            raise ValidationError("反应时间不能大于1.0秒")

    @staticmethod
    def validate_gamepad_type(gamepad_type: str, supported_types: List[str]) -> None:
        """验证手柄类型"""
        if gamepad_type not in supported_types:
            raise ValidationError(f"不支持的手柄类型: {gamepad_type}，支持的类型: {', '.join(supported_types)}")


class FileOperationHelper:
    """文件操作助手"""

    @staticmethod
    def ensure_directory_exists(directory_path: str) -> None:
        """确保目录存在"""
        try:
            Path(directory_path).mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise AccessDeniedError(f"没有权限创建目录: {directory_path}")
        except Exception as e:
            raise FileOperationError(f"创建目录失败: {directory_path}, 错误: {str(e)}")

    @staticmethod
    def check_file_exists(file_path: str, file_type: str = "文件") -> None:
        """检查文件是否存在"""
        if not os.path.exists(file_path):
            if file_type == "配置":
                raise ConfigNotFoundError(f"配置文件不存在: {file_path}")
            elif file_type == "模板":
                raise TemplateNotFoundError(f"模板文件不存在: {file_path}")
            else:
                raise FileOperationError(f"{file_type}不存在: {file_path}")

    @staticmethod
    def check_file_permissions(file_path: str, operation: str = "读取") -> None:
        """检查文件权限"""
        if not os.path.exists(file_path):
            return

        if operation == "读取" and not os.access(file_path, os.R_OK):
            raise AccessDeniedError(f"没有权限读取文件: {file_path}")
        elif operation == "写入" and not os.access(file_path, os.W_OK):
            raise AccessDeniedError(f"没有权限写入文件: {file_path}")
        elif operation == "删除":
            parent_dir = os.path.dirname(file_path)
            if not os.access(parent_dir, os.W_OK):
                raise AccessDeniedError(f"没有权限删除文件: {file_path}")

    @staticmethod
    def safe_read_yaml(file_path: str) -> Dict[str, Any]:
        """安全读取YAML文件"""
        try:
            FileOperationHelper.check_file_exists(file_path, "配置")
            FileOperationHelper.check_file_permissions(file_path, "读取")

            with open(file_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
                return content if content is not None else {}
        except (yaml.YAMLError, UnicodeDecodeError) as e:
            raise ConfigurationError(f"配置文件格式错误: {file_path}, 错误: {str(e)}")
        except Exception as e:
            if isinstance(e, (ConfigNotFoundError, AccessDeniedError)):
                raise
            raise FileOperationError(f"读取配置文件失败: {file_path}, 错误: {str(e)}")

    @staticmethod
    def safe_write_yaml(file_path: str, data: Dict[str, Any]) -> None:
        """安全写入YAML文件"""
        try:
            # 确保目录存在
            directory = os.path.dirname(file_path)
            if directory:
                FileOperationHelper.ensure_directory_exists(directory)

            # 检查写入权限
            if os.path.exists(file_path):
                FileOperationHelper.check_file_permissions(file_path, "写入")

            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            if isinstance(e, (AccessDeniedError, FileOperationError)):
                raise
            raise FileOperationError(f"写入配置文件失败: {file_path}, 错误: {str(e)}")

    @staticmethod
    def safe_delete_file(file_path: str, allow_missing: bool = False) -> None:
        """安全删除文件"""
        try:
            if not os.path.exists(file_path):
                if not allow_missing:
                    raise FileOperationError(f"要删除的文件不存在: {file_path}")
                return

            FileOperationHelper.check_file_permissions(file_path, "删除")
            os.remove(file_path)
        except Exception as e:
            if isinstance(e, (AccessDeniedError, FileOperationError)):
                raise
            raise FileOperationError(f"删除文件失败: {file_path}, 错误: {str(e)}")

    @staticmethod
    def get_file_info(file_path: str) -> Dict[str, Any]:
        """获取文件信息"""
        try:
            FileOperationHelper.check_file_exists(file_path)
            stat = os.stat(file_path)
            return {
                "size": stat.st_size,
                "modified_time": stat.st_mtime,
                "is_readable": os.access(file_path, os.R_OK),
                "is_writable": os.access(file_path, os.W_OK)
            }
        except Exception as e:
            if isinstance(e, FileOperationError):
                raise
            raise FileOperationError(f"获取文件信息失败: {file_path}, 错误: {str(e)}")

    @staticmethod
    def list_files_in_directory(directory_path: str, extension: str = None) -> List[str]:
        """列出目录中的文件"""
        try:
            if not os.path.exists(directory_path):
                return []

            if not os.path.isdir(directory_path):
                raise FileOperationError(f"路径不是目录: {directory_path}")

            files = []
            for item in os.listdir(directory_path):
                item_path = os.path.join(directory_path, item)
                if os.path.isfile(item_path):
                    if extension is None or item.endswith(extension):
                        files.append(item)

            return sorted(files)
        except Exception as e:
            if isinstance(e, FileOperationError):
                raise
            raise FileOperationError(f"列出目录文件失败: {directory_path}, 错误: {str(e)}")


def validate_battle_assistant_config(config_data: Dict[str, Any], config_type: str) -> None:
    """验证战斗助手配置数据"""
    validator = ConfigValidator()

    if config_type == "dodge":
        if "sensitivity" in config_data:
            validator.validate_sensitivity(config_data["sensitivity"])
        if "reaction_time" in config_data:
            validator.validate_reaction_time(config_data["reaction_time"])

    elif config_type == "auto_battle":
        if "screenshot_interval" in config_data:
            validator.validate_screenshot_interval(config_data["screenshot_interval"])
        if "config_name" in config_data:
            validator.validate_config_name(config_data["config_name"], config_type)

    elif config_type == "operation_debug":
        if "template_name" in config_data:
            validator.validate_config_name(config_data["template_name"], config_type)

    # 通用验证
    if "gamepad_type" in config_data:
        supported_types = ["none", "xbox", "ps4", "ps5", "generic"]  # 根据实际支持的类型调整
        validator.validate_gamepad_type(config_data["gamepad_type"], supported_types)


def create_error_context(operation: str, resource: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
    """创建错误上下文信息"""
    context = {
        "operation": operation,
        "resource": resource,
        "timestamp": str(os.times()),
    }

    if details:
        context.update(details)

    return context