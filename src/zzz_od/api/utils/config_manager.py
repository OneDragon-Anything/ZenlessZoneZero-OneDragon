"""
战斗助手配置管理工具模块
提供统一的配置文件CRUD操作、验证和备份功能
"""
import os
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from one_dragon.utils.log_utils import log


class ConfigFileManager:
    """配置文件管理器"""

    def __init__(self, base_config_dir: str = "config"):
        self.base_config_dir = base_config_dir

    def get_config_list(self, config_type: str) -> List[Dict[str, Any]]:
        """
        获取指定类型的配置文件列表

        Args:
            config_type: 配置类型 (auto_battle, dodge, auto_battle_operation等)

        Returns:
            配置文件信息列表
        """
        config_dir = os.path.join(self.base_config_dir, config_type)

        if not os.path.exists(config_dir):
            return []

        configs = []

        # 遍历配置目录，包括子目录
        for root, dirs, files in os.walk(config_dir):
            for filename in files:
                if filename.endswith('.yml') or filename.endswith('.yaml'):
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, config_dir)

                    # 获取配置名称（去掉扩展名）
                    config_name = filename.rsplit('.', 1)[0]
                    # 移除.sample后缀
                    if config_name.endswith('.sample'):
                        config_name = config_name[:-7]
                        is_sample = True
                    else:
                        is_sample = False

                    # 如果在子目录中，包含子目录路径
                    if root != config_dir:
                        subdir = os.path.relpath(root, config_dir)
                        config_name = f"{subdir}/{config_name}"

                    try:
                        stat = os.stat(file_path)
                        configs.append({
                            "name": config_name,
                            "path": relative_path,
                            "full_path": file_path,
                            "is_sample": is_sample,
                            "description": f"{config_type}配置: {config_name}",
                            "last_modified": datetime.fromtimestamp(stat.st_mtime),
                            "file_size": stat.st_size
                        })
                    except OSError as e:
                        log.warning(f"无法获取文件状态 {file_path}: {e}")
                        continue

        return configs

    def config_exists(self, config_type: str, config_name: str) -> bool:
        """
        检查配置文件是否存在

        Args:
            config_type: 配置类型
            config_name: 配置名称

        Returns:
            是否存在
        """
        config_path = self._get_config_path(config_type, config_name)
        sample_path = self._get_config_path(config_type, config_name, is_sample=True)

        return os.path.exists(config_path) or os.path.exists(sample_path)

    def load_config(self, config_type: str, config_name: str) -> Optional[Dict[str, Any]]:
        """
        加载配置文件内容

        Args:
            config_type: 配置类型
            config_name: 配置名称

        Returns:
            配置内容，如果文件不存在返回None
        """
        config_path = self._get_config_path(config_type, config_name)
        sample_path = self._get_config_path(config_type, config_name, is_sample=True)

        # 优先使用正式配置文件
        target_path = config_path if os.path.exists(config_path) else sample_path

        if not os.path.exists(target_path):
            return None

        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            log.error(f"加载配置文件失败 {target_path}: {e}")
            return None

    def save_config(self, config_type: str, config_name: str, config_data: Dict[str, Any],
                   create_backup: bool = True) -> bool:
        """
        保存配置文件

        Args:
            config_type: 配置类型
            config_name: 配置名称
            config_data: 配置数据
            create_backup: 是否创建备份

        Returns:
            是否保存成功
        """
        config_path = self._get_config_path(config_type, config_name)

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            # 创建备份
            if create_backup and os.path.exists(config_path):
                self._create_backup(config_path)

            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

            log.info(f"配置文件保存成功: {config_path}")
            return True

        except Exception as e:
            log.error(f"保存配置文件失败 {config_path}: {e}")
            return False

    def delete_config(self, config_type: str, config_name: str,
                     allow_sample_delete: bool = False) -> Tuple[bool, str]:
        """
        删除配置文件

        Args:
            config_type: 配置类型
            config_name: 配置名称
            allow_sample_delete: 是否允许删除示例文件

        Returns:
            (是否成功, 错误信息)
        """
        config_path = self._get_config_path(config_type, config_name)
        sample_path = self._get_config_path(config_type, config_name, is_sample=True)

        # 确定要删除的文件路径
        target_path = None
        if os.path.exists(config_path):
            target_path = config_path
        elif os.path.exists(sample_path):
            if not allow_sample_delete:
                return False, "不能删除示例配置文件"
            target_path = sample_path

        if target_path is None:
            return False, f"配置文件 {config_name} 不存在"

        try:
            # 创建备份
            self._create_backup(target_path)

            # 删除文件
            os.remove(target_path)
            log.info(f"配置文件删除成功: {target_path}")
            return True, ""

        except Exception as e:
            log.error(f"删除配置文件失败 {target_path}: {e}")
            return False, f"删除失败: {str(e)}"

    def validate_config(self, config_type: str, config_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证配置文件格式

        Args:
            config_type: 配置类型
            config_data: 配置数据

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        if not isinstance(config_data, dict):
            errors.append("配置文件必须是字典格式")
            return False, errors

        # 根据配置类型进行特定验证
        if config_type == "auto_battle":
            errors.extend(self._validate_auto_battle_config(config_data))
        elif config_type == "dodge":
            errors.extend(self._validate_dodge_config(config_data))
        elif config_type == "auto_battle_operation":
            errors.extend(self._validate_operation_config(config_data))

        return len(errors) == 0, errors

    def copy_config(self, config_type: str, source_name: str, target_name: str) -> bool:
        """
        复制配置文件

        Args:
            config_type: 配置类型
            source_name: 源配置名称
            target_name: 目标配置名称

        Returns:
            是否复制成功
        """
        source_path = self._get_config_path(config_type, source_name)
        target_path = self._get_config_path(config_type, target_name)

        # 如果源文件不存在，尝试sample文件
        if not os.path.exists(source_path):
            source_path = self._get_config_path(config_type, source_name, is_sample=True)

        if not os.path.exists(source_path):
            log.error(f"源配置文件不存在: {source_path}")
            return False

        try:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            # 复制文件
            shutil.copy2(source_path, target_path)
            log.info(f"配置文件复制成功: {source_path} -> {target_path}")
            return True

        except Exception as e:
            log.error(f"复制配置文件失败: {e}")
            return False

    def _get_config_path(self, config_type: str, config_name: str, is_sample: bool = False) -> str:
        """获取配置文件路径"""
        config_dir = os.path.join(self.base_config_dir, config_type)

        # 处理子目录路径
        if '/' in config_name:
            parts = config_name.split('/')
            config_dir = os.path.join(config_dir, *parts[:-1])
            filename = parts[-1]
        else:
            filename = config_name

        # 构建文件名
        if is_sample:
            filename = f"{filename}.sample.yml"
        else:
            filename = f"{filename}.yml"

        return os.path.join(config_dir, filename)

    def _create_backup(self, file_path: str) -> None:
        """创建配置文件备份"""
        try:
            backup_dir = os.path.join(os.path.dirname(file_path), ".backup")
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(file_path)
            backup_filename = f"{timestamp}_{filename}"
            backup_path = os.path.join(backup_dir, backup_filename)

            shutil.copy2(file_path, backup_path)
            log.debug(f"创建配置备份: {backup_path}")

        except Exception as e:
            log.warning(f"创建备份失败: {e}")

    def _validate_auto_battle_config(self, config_data: Dict[str, Any]) -> List[str]:
        """验证自动战斗配置"""
        from .config_validation import config_validator
        is_valid, errors = config_validator.validate_auto_battle_config(config_data)
        return errors

    def _validate_dodge_config(self, config_data: Dict[str, Any]) -> List[str]:
        """验证闪避配置"""
        from .config_validation import config_validator
        is_valid, errors = config_validator.validate_dodge_config(config_data)
        return errors

    def _validate_operation_config(self, config_data: Dict[str, Any]) -> List[str]:
        """验证操作配置"""
        from .config_validation import config_validator
        is_valid, errors = config_validator.validate_operation_config(config_data)
        return errors


class TemplateManager:
    """模板文件管理器"""

    def __init__(self, template_dir: str = "config/auto_battle_operation"):
        self.template_dir = template_dir

    def get_template_list(self) -> List[Dict[str, Any]]:
        """获取所有模板文件列表"""
        if not os.path.exists(self.template_dir):
            return []

        templates = []

        # 遍历模板目录，包括子目录
        for root, dirs, files in os.walk(self.template_dir):
            for filename in files:
                if filename.endswith('.yml') or filename.endswith('.yaml'):
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, self.template_dir)

                    # 获取模板名称（去掉扩展名）
                    template_name = filename.rsplit('.', 1)[0]
                    # 移除.sample后缀
                    if template_name.endswith('.sample'):
                        template_name = template_name[:-7]
                        is_sample = True
                    else:
                        is_sample = False

                    # 如果在子目录中，包含子目录路径
                    if root != self.template_dir:
                        subdir = os.path.relpath(root, self.template_dir)
                        template_name = f"{subdir}/{template_name}"

                    try:
                        stat = os.stat(file_path)
                        templates.append({
                            "name": template_name,
                            "path": relative_path,
                            "full_path": file_path,
                            "is_sample": is_sample,
                            "description": f"操作模板: {template_name}",
                            "last_modified": datetime.fromtimestamp(stat.st_mtime),
                            "file_size": stat.st_size
                        })
                    except OSError as e:
                        log.warning(f"无法获取模板文件状态 {file_path}: {e}")
                        continue

        return templates

    def template_exists(self, template_name: str) -> bool:
        """检查模板是否存在"""
        template_path = self._get_template_path(template_name)
        sample_path = self._get_template_path(template_name, is_sample=True)

        return os.path.exists(template_path) or os.path.exists(sample_path)

    def load_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """加载模板内容"""
        template_path = self._get_template_path(template_name)
        sample_path = self._get_template_path(template_name, is_sample=True)

        # 优先使用正式模板文件
        target_path = template_path if os.path.exists(template_path) else sample_path

        if not os.path.exists(target_path):
            return None

        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            log.error(f"加载模板文件失败 {target_path}: {e}")
            return None

    def delete_template(self, template_name: str, allow_sample_delete: bool = False) -> Tuple[bool, str]:
        """删除模板文件"""
        template_path = self._get_template_path(template_name)
        sample_path = self._get_template_path(template_name, is_sample=True)

        # 确定要删除的文件路径
        target_path = None
        if os.path.exists(template_path):
            target_path = template_path
        elif os.path.exists(sample_path):
            if not allow_sample_delete:
                return False, "不能删除示例模板文件"
            target_path = sample_path

        if target_path is None:
            return False, f"模板文件 {template_name} 不存在"

        try:
            # 创建备份
            self._create_backup(target_path)

            # 删除文件
            os.remove(target_path)
            log.info(f"模板文件删除成功: {target_path}")
            return True, ""

        except Exception as e:
            log.error(f"删除模板文件失败 {target_path}: {e}")
            return False, f"删除失败: {str(e)}"

    def _get_template_path(self, template_name: str, is_sample: bool = False) -> str:
        """获取模板文件路径"""
        # 处理子目录路径
        if '/' in template_name:
            parts = template_name.split('/')
            template_dir = os.path.join(self.template_dir, *parts[:-1])
            filename = parts[-1]
        else:
            template_dir = self.template_dir
            filename = template_name

        # 构建文件名
        if is_sample:
            filename = f"{filename}.sample.yml"
        else:
            filename = f"{filename}.yml"

        return os.path.join(template_dir, filename)

    def _create_backup(self, file_path: str) -> None:
        """创建模板文件备份"""
        try:
            backup_dir = os.path.join(os.path.dirname(file_path), ".backup")
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(file_path)
            backup_filename = f"{timestamp}_{filename}"
            backup_path = os.path.join(backup_dir, backup_filename)

            shutil.copy2(file_path, backup_path)
            log.debug(f"创建模板备份: {backup_path}")

        except Exception as e:
            log.warning(f"创建备份失败: {e}")


# 全局实例
config_manager = ConfigFileManager()
template_manager = TemplateManager()