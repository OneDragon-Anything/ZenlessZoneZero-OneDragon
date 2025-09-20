from enum import Enum
from typing import Optional

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon_qt.widgets.push_cards import PushCards


class NotifyMethodEnum(Enum):

    WEBHOOK = ConfigItem('Webhook', 'WEBHOOK')
    SMTP = ConfigItem('邮件', 'SMTP')
    ONEBOT = ConfigItem('OneBot', 'ONEBOT')
    QYWX = ConfigItem('企业微信', 'QYWX')
    DD_BOT = ConfigItem('钉钉机器人', 'DD_BOT')
    FS =  ConfigItem('飞书/Lark 机器人', 'FS')
    DISCORD = ConfigItem('Discord', 'DISCORD')
    TELEGRAM = ConfigItem('Telegram', 'TG')
    BARK = ConfigItem('Bark', 'BARK')
    SERVERCHAN = ConfigItem('Server 酱', 'SERVERCHAN')
    NTFY = ConfigItem('ntfy', 'NTFY')
    GOTIFY = ConfigItem('GOTIFY', 'GOTIFY')
    UNKNOWN = ConfigItem('下面的方法无人维护，遇到问题请自行解决', 'UNKNOWN')
    CHRONOCAT = ConfigItem('Chronocat', 'CHRONOCAT')
    DEER = ConfigItem('PushDeer', 'DEER')
    IGOT = ConfigItem('iGot', 'IGOT')
    CHAT = ConfigItem('Synology Chat', 'CHAT')
    PUSH_PLUS = ConfigItem('PushPlus', 'PUSH_PLUS')
    WE_PLUS_BOT = ConfigItem('微加机器人', 'WE_PLUS_BOT')
    QMSG = ConfigItem('Qmsg 酱', 'QMSG')
    AIBOTK = ConfigItem('智能微秘书', 'AIBOTK')
    PUSHME = ConfigItem('PushMe', 'PUSHME')
    WXPUSHER = ConfigItem('WxPusher', 'WXPUSHER')

class PushConfig(YamlConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        YamlConfig.__init__(self, 'push', instance_idx=instance_idx)
        self._generate_dynamic_properties()

    @property
    def custom_push_title(self) -> str:
        return self.get('custom_push_title', '一条龙运行通知')

    @custom_push_title.setter
    def custom_push_title(self, new_value: str) -> None:
        self.update('custom_push_title', new_value)

    @property
    def send_image(self) -> bool:
        return self.get('send_image', True)

    @send_image.setter
    def send_image(self, new_value: bool) -> None:
        self.update('send_image', new_value)

    def _generate_dynamic_properties(self):
        # 遍历所有配置组
        for group_name, items in PushCards.get_configs().items():
            group_lower = group_name.lower()
            # 遍历组内的每个配置项
            for item in items:
                var_suffix = item['var_suffix']
                var_suffix_lower = var_suffix.lower()
                prop_name = f'{group_lower}_{var_suffix_lower}'

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
                    create_getter(prop_name, item.get('default', '')),
                    create_setter(prop_name)
                )
                setattr(PushConfig, prop_name, prop)
