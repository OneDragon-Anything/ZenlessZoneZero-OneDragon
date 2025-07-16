from enum import Enum
from typing import Optional

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig


class NotifyMethodEnum(Enum):

    SMTP = ConfigItem('邮件', 'SMTP')
    WEBHOOK = ConfigItem('Webhook', 'WEBHOOK')
    ONEBOT = ConfigItem('OneBot', 'ONEBOT')
    CHRONOCAT = ConfigItem('Chronocat', 'CHRONOCAT')
    QYWX = ConfigItem('企业微信', 'QYWX')
    DD_BOT = ConfigItem('钉钉机器人', 'DD_BOT')
    FS =  ConfigItem('飞书机器人', 'FS')
    DISCORD = ConfigItem('Discord', 'DISCORD')
    TELEGRAM = ConfigItem('Telegram', 'TG')
    BARK = ConfigItem('Bark', 'BARK')
    SERVERCHAN = ConfigItem('Server 酱', 'SERVERCHAN')
    NTFY = ConfigItem('ntfy', 'NTFY')
    DEER = ConfigItem('PushDeer', 'DEER')
    GOTIFY = ConfigItem('GOTIFY', 'GOTIFY')
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
        for group_name, items in PushConfigNames.get_configs().items():
            group_lower = group_name.lower()
            # 遍历组内的每个配置项
            for var_suffix in items:
                var_suffix_lower = var_suffix.lower()
                prop_name = f"{group_lower}_{var_suffix_lower}"

                # 定义getter和setter，使用闭包捕获当前的prop_name
                def create_getter(name: str):
                    def getter(self) -> float:
                        return self.get(name, None)
                    return getter

                def create_setter(name: str):
                    def setter(self, new_value: float) -> None:
                        self.update(name, new_value)
                    return setter

                # 创建property并添加到类
                prop = property(
                    create_getter(prop_name),
                    create_setter(prop_name)
                )
                setattr(PushConfig, prop_name, prop)

class PushConfigNames:
    # 推送配置项名称定义，用于动态生成PushConfig属性
    push_config_names = {
    "BARK": ["PUSH","DEVICE_KEY","ARCHIVE","GROUP","SOUND","ICON","LEVEL","URL"],
    "DD_BOT": ["SECRET","TOKEN"],
    "FS": ["KEY"],
    "ONEBOT": ["URL","USER","GROUP","TOKEN"],
    "GOTIFY": ["URL","TOKEN","PRIORITY"],
    "IGOT": ["PUSH_KEY"],
    "SERVERCHAN": ["PUSH_KEY"],
    "DEER": ["KEY","URL"],
    "CHAT": ["URL","TOKEN"],
    "PUSH_PLUS": ["TOKEN","USER","TEMPLATE","CHANNEL","WEBHOOK","CALLBACKURL","TO"],
    "WE_PLUS_BOT": ["TOKEN","RECEIVER","VERSION"],
    "QMSG": ["KEY","TYPE"],
    "QYWX": ["ORIGIN","AM","KEY"],
    "DISCORD": ["BOT_TOKEN","USER_ID"],
    "TG": ["BOT_TOKEN","USER_ID","PROXY_HOST","PROXY_PORT","PROXY_AUTH","API_HOST"],
    "AIBOTK": ["KEY","TYPE","NAME"],
    "SMTP": ["SERVER","SSL","EMAIL","PASSWORD","NAME"],
    "PUSHME": ["KEY","URL"],
    "CHRONOCAT": ["QQ","TOKEN","URL"],
    "WEBHOOK": ["URL","BODY","HEADERS","METHOD","CONTENT_TYPE"],
    "NTFY": ["URL","TOPIC","PRIORITY"],
    "WXPUSHER": ["APP_TOKEN","TOPIC_IDS","UIDS"]
    }

    @classmethod
    def get_configs(cls):
        return cls.push_config_names