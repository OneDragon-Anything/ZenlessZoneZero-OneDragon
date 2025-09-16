"""
配置验证工具模块
提供配置文件格式验证和数据完整性检查功能
"""
from typing import Dict, Any, List, Tuple, Optional
from one_dragon.utils.log_utils import log


class ConfigValidator:
    """配置验证器"""

    @staticmethod
    def validate_battle_assistant_config(config_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证战斗助手主配置

        Args:
            config_data: 配置数据

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        if not isinstance(config_data, dict):
            errors.append("配置文件必须是字典格式")
            return False, errors

        # 验证GPU设置
        if 'use_gpu' in config_data:
            if not isinstance(config_data['use_gpu'], bool):
                errors.append("use_gpu 必须是布尔值")

        # 验证截图间隔
        if 'screenshot_interval' in config_data:
            interval = config_data['screenshot_interval']
            if not isinstance(interval, (int, float)):
                errors.append("screenshot_interval 必须是数字")
            elif interval <= 0:
                errors.append("screenshot_interval 必须大于0")
            elif interval > 1.0:
                errors.append("screenshot_interval 不应超过1.0秒")

        # 验证手柄类型
        if 'gamepad_type' in config_data:
            gamepad_type = config_data['gamepad_type']
            if not isinstance(gamepad_type, str):
                errors.append("gamepad_type 必须是字符串")
            else:
                valid_types = ["none", "xbox", "ps4", "ps5", "switch"]
                if gamepad_type not in valid_types:
                    errors.append(f"gamepad_type 必须是以下值之一: {', '.join(valid_types)}")

        # 验证配置名称
        for config_key in ['dodge_assistant_config', 'auto_battle_config', 'debug_operation_config']:
            if config_key in config_data:
                if not isinstance(config_data[config_key], str):
                    errors.append(f"{config_key} 必须是字符串")
                elif not config_data[config_key].strip():
                    errors.append(f"{config_key} 不能为空")

        # 验证重复模式设置
        if 'debug_operation_repeat' in config_data:
            if not isinstance(config_data['debug_operation_repeat'], bool):
                errors.append("debug_operation_repeat 必须是布尔值")

        return len(errors) == 0, errors

    @staticmethod
    def validate_auto_battle_config(config_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证自动战斗配置

        Args:
            config_data: 配置数据

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        if not isinstance(config_data, dict):
            errors.append("配置文件必须是字典格式")
            return False, errors

        # 验证基本结构
        required_sections = ['team', 'battle']
        for section in required_sections:
            if section not in config_data:
                errors.append(f"缺少必需的配置节: {section}")

        # 验证队伍配置
        if 'team' in config_data:
            team_config = config_data['team']
            if not isinstance(team_config, dict):
                errors.append("team 配置必须是字典格式")
            else:
                # 验证角色配置
                if 'agents' in team_config:
                    agents = team_config['agents']
                    if not isinstance(agents, list):
                        errors.append("agents 必须是列表格式")
                    elif len(agents) == 0:
                        errors.append("至少需要配置一个角色")
                    else:
                        for i, agent in enumerate(agents):
                            if not isinstance(agent, dict):
                                errors.append(f"角色 {i+1} 配置必须是字典格式")
                            elif 'name' not in agent:
                                errors.append(f"角色 {i+1} 缺少 name 字段")

        # 验证战斗配置
        if 'battle' in config_data:
            battle_config = config_data['battle']
            if not isinstance(battle_config, dict):
                errors.append("battle 配置必须是字典格式")
            else:
                # 验证战斗策略
                if 'strategy' in battle_config:
                    strategy = battle_config['strategy']
                    if not isinstance(strategy, str):
                        errors.append("battle.strategy 必须是字符串")
                    elif strategy not in ['aggressive', 'defensive', 'balanced']:
                        errors.append("battle.strategy 必须是 aggressive, defensive 或 balanced")

                # 验证技能优先级
                if 'skill_priority' in battle_config:
                    priority = battle_config['skill_priority']
                    if not isinstance(priority, list):
                        errors.append("battle.skill_priority 必须是列表格式")

        return len(errors) == 0, errors

    @staticmethod
    def validate_dodge_config(config_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证闪避配置

        Args:
            config_data: 配置数据

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        if not isinstance(config_data, dict):
            errors.append("配置文件必须是字典格式")
            return False, errors

        # 验证闪避设置
        if 'dodge' in config_data:
            dodge_config = config_data['dodge']
            if not isinstance(dodge_config, dict):
                errors.append("dodge 配置必须是字典格式")
            else:
                # 验证敏感度
                if 'sensitivity' in dodge_config:
                    sensitivity = dodge_config['sensitivity']
                    if not isinstance(sensitivity, (int, float)):
                        errors.append("dodge.sensitivity 必须是数字")
                    elif sensitivity < 0 or sensitivity > 1:
                        errors.append("dodge.sensitivity 必须在 0-1 之间")

                # 验证反应时间
                if 'reaction_time' in dodge_config:
                    reaction_time = dodge_config['reaction_time']
                    if not isinstance(reaction_time, (int, float)):
                        errors.append("dodge.reaction_time 必须是数字")
                    elif reaction_time < 0 or reaction_time > 1:
                        errors.append("dodge.reaction_time 必须在 0-1 秒之间")

                # 验证闪避方式
                if 'method' in dodge_config:
                    method = dodge_config['method']
                    if not isinstance(method, str):
                        errors.append("dodge.method 必须是字符串")
                    elif method not in ['闪避', '完美闪避', '高级闪避']:
                        errors.append("dodge.method 必须是 闪避, 完美闪避 或 高级闪避")

        return len(errors) == 0, errors

    @staticmethod
    def validate_operation_config(config_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证操作模板配置

        Args:
            config_data: 配置数据

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        if not isinstance(config_data, dict):
            errors.append("配置文件必须是字典格式")
            return False, errors

        # 验证操作序列
        if 'operations' in config_data:
            operations = config_data['operations']
            if not isinstance(operations, list):
                errors.append("operations 必须是列表格式")
            elif len(operations) == 0:
                errors.append("至少需要配置一个操作")
            else:
                for i, operation in enumerate(operations):
                    if not isinstance(operation, dict):
                        errors.append(f"操作 {i+1} 必须是字典格式")
                        continue

                    # 验证操作类型
                    if 'type' not in operation:
                        errors.append(f"操作 {i+1} 缺少 type 字段")
                    elif operation['type'] not in ['key', 'click', 'wait', 'combo']:
                        errors.append(f"操作 {i+1} 的 type 必须是 key, click, wait 或 combo")

                    # 验证持续时间
                    if 'duration' in operation:
                        duration = operation['duration']
                        if not isinstance(duration, (int, float)):
                            errors.append(f"操作 {i+1} 的 duration 必须是数字")
                        elif duration < 0:
                            errors.append(f"操作 {i+1} 的 duration 不能为负数")

        # 验证模板信息
        if 'template_info' in config_data:
            template_info = config_data['template_info']
            if not isinstance(template_info, dict):
                errors.append("template_info 必须是字典格式")
            else:
                # 验证模板名称
                if 'name' in template_info and not isinstance(template_info['name'], str):
                    errors.append("template_info.name 必须是字符串")

                # 验证描述
                if 'description' in template_info and not isinstance(template_info['description'], str):
                    errors.append("template_info.description 必须是字符串")

        return len(errors) == 0, errors

    @staticmethod
    def validate_config_by_type(config_type: str, config_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        根据配置类型验证配置

        Args:
            config_type: 配置类型
            config_data: 配置数据

        Returns:
            (是否有效, 错误信息列表)
        """
        if config_type == "battle_assistant":
            return ConfigValidator.validate_battle_assistant_config(config_data)
        elif config_type == "auto_battle":
            return ConfigValidator.validate_auto_battle_config(config_data)
        elif config_type == "dodge":
            return ConfigValidator.validate_dodge_config(config_data)
        elif config_type == "auto_battle_operation":
            return ConfigValidator.validate_operation_config(config_data)
        else:
            # 对于未知类型，只进行基本验证
            if not isinstance(config_data, dict):
                return False, ["配置文件必须是字典格式"]
            return True, []


# 全局验证器实例
config_validator = ConfigValidator()