import os
from typing import Any

import yaml

from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.conditional_operation.scene import Scene
from one_dragon.base.conditional_operation.state_handler import StateHandler
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log


class MergedConfigDumper(yaml.SafeDumper):
    
    def represent_str(self, data):
        return self.represent_scalar('tag:yaml.org,2002:str', data, style='"')

MergedConfigDumper.add_representer(str, lambda dumper, data: dumper.represent_str(data))


class ConditionalOperatorLoader:

    def __init__(
        self,
        sub_dir: list[str],
        template_name: str,
        operation_template_sub_dir: list[str],
        state_handler_template_sub_dir: list[str],
        read_from_merged: bool = True,
    ):
        self._read_from_merged: bool = read_from_merged  # 是否从合并的配置文件中读取
        self._sub_dir: list[str] = sub_dir  # 配置入口文件所在目录
        self._operation_template_sub_dir: list[str] = operation_template_sub_dir  # 操作模板所在目录
        self._state_handler_template_sub_dir: list[str] = state_handler_template_sub_dir  # 状态处理器模板所在目录

        self._template_name: str = template_name  # 配置入口文件名
        
        # 配置数据
        self.scenes: list[Scene] = []

    def load(self) -> None:
        """
        加载配置
        """
        data = ConditionalOperatorLoader.load_yaml_config(self._sub_dir, self._template_name, self._read_from_merged)

        scenes = data.get('scenes', [])

        for scene_data in scenes:
            self.scenes.append(Scene(scene_data))

        self.validate()
            
        self.load_other_info(data)
        self.load_templates()

    def validate(self) -> None:
        """
        校验配置 有问题时抛出异常
        """
        usage_states = []  # 已经监听的状态变更
        normal_scene: bool = False  # 是否已经出现过无触发器的场景
        for scene in self.scenes:
            if len(scene.triggers) > 0:
                for trigger in scene.triggers:
                    if trigger in usage_states:
                        raise ValueError(f'状态 {trigger} 在多个场景中重复使用')
                    usage_states.append(trigger)
            else:
                if normal_scene:
                    raise ValueError('多个场景都没有触发器')
                normal_scene = True

    def load_other_info(self, data: dict[str, Any]) -> None:
        """
        加载其他所需的信息 由子类自行实现

        Args:
            data: yml文件内容
        """
        pass

    def load_templates(self) -> None:
        """
        加载配置中 模板相关部分
        """
        for scene in self.scenes:
            self.load_template_for_scene(scene)

    def load_template_for_scene(self, scene: Scene) -> None:
        """
        给场景加载模板

        Args:
            scene: 场景
        """
        all_new_handlers: list[StateHandler] = []
        for handler in scene.handlers:
            new_handlers: list[StateHandler] = self.load_template_for_state_handler(handler, set())
            all_new_handlers.extend(new_handlers)

        scene.set_handlers(all_new_handlers)

    def load_template_for_state_handler(
        self,
        handler: StateHandler,
        usage_states_handler_templates: set[str]
    ) -> list[StateHandler]:
        """
        给状态处理器加载内部的模板 会递归处理

        Args:
            handler: 状态处理器
            usage_states_handler_templates: 已使用的模板名称列表 用于判断循环引用

        Returns:
            list[StateHandler]: 加载模板后的状态处理器列表
        """
        if handler.state_template is not None:  # 当前是一个模板
            if handler.state_template in usage_states_handler_templates:
                raise ValueError('状态处理器模板循环引用 ' + handler.state_template)
            usage_states_handler_templates.add(handler.state_template)

            all_new_handlers: list[StateHandler] = []
            data = ConditionalOperatorLoader.load_yaml_config(self._state_handler_template_sub_dir, handler.state_template)
            handlers = data.get("handlers", [])
            for handler_data in handlers:
                # 递归加载
                new_handler = StateHandler(handler_data)
                new_handlers = self.load_template_for_state_handler(
                    new_handler,
                    usage_states_handler_templates,
                )
                all_new_handlers.extend(new_handlers)
            usage_states_handler_templates.remove(handler.state_template)

            for i in all_new_handlers:
                if i.state_template is not None:
                    pass

            return all_new_handlers

        if len(handler.sub_handlers) > 0:  # 存在子处理器 则处理子处理器
            all_new_handlers: list[StateHandler] = []
            for sub_handler in handler.sub_handlers:
                new_handlers = self.load_template_for_state_handler(
                    sub_handler,
                    usage_states_handler_templates,
                )
                all_new_handlers.extend(new_handlers)
            handler.set_sub_handlers(all_new_handlers)
        elif len(handler.operations) > 0:
            all_new_operations: list[OperationDef] = []
            for operation in handler.operations:
                new_operations = self.load_template_for_operation(operation, set())
                all_new_operations.extend(new_operations)
            handler.set_operations(all_new_operations)

        return [handler]

    def load_template_for_operation(
        self,
        operation: OperationDef,
        usage_operation_templates: set[str]
    ) -> list[OperationDef]:
        """
        给指令加载内部模板 会递归处理

        Args:
            operation: 指令
            usage_operation_templates: 已使用的模板名称列表 用于判断循环引用

        Returns:
            list[OperationDef]: 加载模板后的指令列表
        """
        if operation.operation_template is not None:
            if operation.operation_template in usage_operation_templates:
                raise ValueError('指令模板循环引用 ' + operation.operation_template)
            usage_operation_templates.add(operation.operation_template)

            all_new_operations: list[OperationDef] = []
            data = ConditionalOperatorLoader.load_yaml_config(self._operation_template_sub_dir, operation.operation_template)
            operations = data.get("operations", [])
            for operation_data in operations:
                new_operations = self.load_template_for_operation(
                    OperationDef(operation_data),
                    usage_operation_templates,
                )
                all_new_operations.extend(new_operations)

            usage_operation_templates.remove(operation.operation_template)
            return all_new_operations
        else:
            return [operation]

    def save_as_one_file(self) -> None:
        """
        将配置保存为单个文件
        """
        full_sub_dir = ['config'] + self._sub_dir
        template_dir = os_utils.get_path_under_work_dir(*full_sub_dir)
        file_path = os.path.join(template_dir, f'{self._template_name}.merged.yml')
        with open(file_path, 'w', encoding='utf-8') as file:
            data = {
                'scenes': [scene.original_data for scene in self.scenes]
            }
            yaml.dump(data, file, allow_unicode=True, Dumper=MergedConfigDumper)

    def get_template_name(self) -> str:
        return self._template_name

    @staticmethod
    def get_yaml_file_path(
        sub_dir: list[str],
        template_name: str,
        read_from_merged: bool = True,
    ) -> str:
        """
        获取配置文件所在路径

        Args:
            sub_dir: 配置文件所在目录
            template_name: 配置文件名
            read_from_merged: 是否从合并后的文件中读取

        Returns:
            str: 配置文件所在路径
        """
        full_sub_dir = ["config"] + sub_dir
        template_dir = os_utils.get_path_under_work_dir(*full_sub_dir)
        if read_from_merged:
            merged_file_path = os.path.join(template_dir, f"{template_name}.merged.yml")
            if os.path.exists(merged_file_path):
                return merged_file_path

        normal_file_path = os.path.join(template_dir, f"{template_name}.yml")
        sample_file_path = os.path.join(template_dir, f"{template_name}.sample.yml")
        if os.path.exists(normal_file_path):
            return normal_file_path
        else:
            return sample_file_path

    @staticmethod
    def load_yaml_config(sub_dir: list[str], template_name: str, read_from_merged: bool = False) -> Any:
        """
        从 config 目录下加载yml配置文件
        Args:
            sub_dir: 配置文件所在目录
            template_name: 配置文件名
            read_from_merged: 是否从合并后的文件中读取

        Returns:
            Any: 配置文件内容
        """
        file_path = ConditionalOperatorLoader.get_yaml_file_path(
            sub_dir=sub_dir,
            template_name=template_name,
            read_from_merged=read_from_merged,
        )
        if not os.path.exists(file_path):
            raise FileNotFoundError(f'未找到配置文件 {"/".join(sub_dir)}/{template_name}')

        with open(file_path, 'r', encoding='utf-8') as file:
            log.debug(f"加载yaml: {file_path}")
            data = yaml.safe_load(file)
            return data


def __debug():
    loader = ConditionalOperatorLoader(
        sub_dir=['auto_battle'],
        template_name='全配队通用',
        operation_template_sub_dir=['auto_battle_operation'],
        state_handler_template_sub_dir=['auto_battle_state_handler'],
        read_from_merged=True,
    )
    import time
    t1 = time.time()
    loader.load()
    print(time.time() - t1)
    # loader.save_as_one_file()


if __name__ == '__main__':
    __debug()
