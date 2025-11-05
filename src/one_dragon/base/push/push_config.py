import os
import shutil
from enum import Enum, StrEnum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.base.push.push_channel_config import PushChannelConfigField
from one_dragon.utils import os_utils


class PushProxy(Enum):

    NONE = ConfigItem(label="不启用", value="NONE", desc="不使用代理发送")
    PERSONAL = ConfigItem(label="个人代理", value="PERSONAL", desc="沿用脚本环境的个人代理发送")


class PushConfig(YamlConfig):

    def __init__(self):
        """
        推送配置
        应该是一个全局配置
        """
        # 将账号实例下的配置复制到全局 预计 2026-01-01 可删除这部分兼容代码
        instance_config_file_path = os.path.join(
            os_utils.get_path_under_work_dir('config', '01'),
            'push.yml'
        )
        global_config_file_path = os.path.join(
            os_utils.get_path_under_work_dir('config'),
            'push.yml'
        )
        if not os.path.exists(global_config_file_path) and os.path.exists(instance_config_file_path):
            shutil.copy(instance_config_file_path, global_config_file_path)

        YamlConfig.__init__(self, 'push')

    @property
    def custom_push_title(self) -> str:
        return self.get('custom_push_title', '一条龙运行通知')

    @custom_push_title.setter
    def custom_push_title(self, new_value: str) -> None:
        self.update('custom_push_title', new_value)

    @property
    def send_image(self) -> bool:
        """ 是否发送图片 """
        return self.get('send_image', True)

    @send_image.setter
    def send_image(self, new_value: bool) -> None:
        self.update('send_image', new_value)

    @property
    def proxy(self) -> str:
        return self.get('proxy', PushProxy.NONE.value.value)

    @proxy.setter
    def proxy(self, new_value: str) -> None:
        self.update('proxy', new_value)

    def generate_channel_fields(self, channel_config_schemas: dict[str, list[PushChannelConfigField]]) -> None:
        """
        动态生成各个推送渠道的配置字段

        Args:
            channel_config_schemas: 各个渠道所需的配置字段

        """
        # 遍历所有配置组
        for channel_id, field_list in channel_config_schemas.items():
            # 遍历组内的每个配置项
            for field in field_list:
                var_suffix = field.var_suffix
                prop_name = self.get_channel_config_key(channel_id, var_suffix)

                # 定义getter和setter，使用闭包捕获当前的prop_name和default值
                def create_getter(name: str, default_value):
                    def getter(self) -> str:
                        return self.get(name, default_value)

                    return getter

                def create_setter(name: str):
                    def setter(self, new_value: str) -> None:
                        self.update(name, new_value)

                    return setter

                # 创建property并添加到类
                prop = property(
                    create_getter(prop_name, field.default),
                    create_setter(prop_name)
                )
                setattr(PushConfig, prop_name, prop)

    def get_channel_config_value(
        self,
        channel_id: str,
        field_name: str,
        default_value: str = ''
    ) -> str:
        """
        获取推送渠道某个特定配置值

        Args:
            channel_id: 推送渠道ID
            field_name: 配置字段名称
            default_value: 默认值

        Returns:
            配置值
        """
        key = self.get_channel_config_key(channel_id, field_name)
        return self.get(key, default_value)

    def update_channel_config_value(
        self,
        channel_id: str,
        field_name: str,
        new_value: str
    ) -> None:
        """
        更新推送渠道某个特定配置值

        Args:
            channel_id: 推送渠道ID
            field_name: 配置字段名称
            new_value: 新值
        """
        key = self.get_channel_config_key(channel_id, field_name)
        self.update(key, new_value)

    def get_channel_config_key(self, channel_id: str, field_name: str) -> str:
        """
        获取推送渠道某个特定配置的key

        Args:
            channel_id: 推送渠道ID
            field_name: 配置字段名称

        Returns:
            配置key
        """
        return f'{channel_id.lower()}_{field_name.lower()}'
