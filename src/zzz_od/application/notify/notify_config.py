from enum import Enum
from typing import Optional

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from qfluentwidgets import FluentIcon


class NotifyMethodEnum(Enum):

    DISABLED = ConfigItem('禁用', 'DISABLED')
    
    BARK = ConfigItem('Bark', 'BARK')
    DD_BOT = ConfigItem('钉钉机器人', 'DD_BOT')
    FS =  ConfigItem('飞书机器人', 'FS')
    ONEBOT = ConfigItem('OneBot', 'ONEBOT')
    GOTIFY = ConfigItem('GOTIFY', 'GOTIFY')
    IGOT = ConfigItem('iGot', 'IGOT')
    SERVERCHAN = ConfigItem('Server 酱', 'PUSH_KEY')
    DEER = ConfigItem('PushDeer', 'DEER')
    CHAT = ConfigItem('Synology Chat', 'CHAT')
    PUSH_PLUS = ConfigItem('PushPlus', 'PUSH_PLUS')
    WE_PLUS_BOT = ConfigItem('微加机器人', 'WE_PLUS_BOT')
    QMSG = ConfigItem('Qmsg 酱', 'QMSG')
    QYWX = ConfigItem('企业微信', 'QYWX')
    Telegram = ConfigItem('Telegram', 'TG')
    AIBOTK = ConfigItem('智能微秘书', 'AIBOTK')
    SMTP = ConfigItem('邮件', 'SMTP')
    PUSHME = ConfigItem('PushMe', 'PUSHME')
    CHRONOCAT = ConfigItem('Chronocat', 'CHRONOCAT')
    WEBHOOK = ConfigItem('Webhook', 'WEBHOOK')
    NTFY = ConfigItem('ntfy', 'NTFY')
    WXPUSHER = ConfigItem('WxPusher', 'WXPUSHER')



class NotifyConfig(YamlConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        YamlConfig.__init__(self, 'notify', instance_idx=instance_idx)
        self._generate_dynamic_properties()
    
    
    @property
    def notify_method(self) -> str:
        return self.get('notify_method', NotifyMethodEnum.DISABLED.value.value)

    @notify_method.setter
    def notify_method(self, new_value: str) -> None:
        self.update('notify_method', new_value)

    def _generate_dynamic_properties(self):
        # 遍历所有配置组
        for group_name, items in NotifyCard.configs.items():
            group_lower = group_name.lower()
            # 遍历组内的每个配置项
            for item in items:
                var_suffix = item["var_suffix"]
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
                setattr(NotifyConfig, prop_name, prop)

class NotifyCard():
    configs = {
    # Bark 相关配置
    "BARK": [
        {
            "var_suffix": "PUSH", 
            "title": "设备码",
            "icon": FluentIcon.MESSAGE,
            "placeholder": "请输入Bark IP 或设备码"
        },
        {
            "var_suffix": "ARCHIVE",
            "title": "推送是否存档",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "可选：true 或 false"
        },
        {
            "var_suffix": "GROUP",
            "title": "推送分组",
            "icon": FluentIcon.CLOUD,
            "placeholder": ""
        },
        {
            "var_suffix": "SOUND",
            "title": "推送声音",
            "icon": FluentIcon.CLOUD,
            "placeholder": ""
        },
        {
            "var_suffix": "ICON",
            "title": "推送图标",
            "icon": FluentIcon.CLOUD,
            "placeholder": ""
        },
        {
            "var_suffix": "LEVEL",
            "title": "推送时效性",
            "icon": FluentIcon.CLOUD,
            "placeholder": ""
        },
        {
            "var_suffix": "URL",
            "title": "推送跳转URL",
            "icon": FluentIcon.CLOUD,
            "placeholder": ""
        }
    ],
    # 钉钉机器人相关配置
    "DD_BOT": [
        {
            "var_suffix": "SECRET'",
            "title": "Secret",
            "icon": FluentIcon.CERTIFICATE,
            "placeholder": "请输入钉钉机器人的Secret密钥"
        },
        {
            "var_suffix": "TOKEN",
            "title": "Token",
            "icon": FluentIcon.VPN,
            "placeholder": "请输入钉钉机器人的Token密钥"
        }
    ],
    # 飞书机器人 相关配置
    "FS": [
        {
            "var_suffix": "KEY",
            "title": "密钥",
            "icon": FluentIcon.CERTIFICATE,
            "placeholder": "请输入飞书机器人的密钥"
        }
    ],
    # OneBot 相关配置
    "ONEBOT": [
        {
            "var_suffix": "URL",
            "title": "请求地址",
            "icon": FluentIcon.SEND,
            "placeholder": "请输入请求地址"
        },
        {
            "var_suffix": "USER",
            "title": "QQ 号",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "请输入目标 QQ 号"
        },
        {
            "var_suffix": "GROUP",
            "title": "群号",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "请输入目标群号"
        },
        {
            "var_suffix": "TOKEN",
            "title": "Token",
            "icon": FluentIcon.VPN,
            "placeholder": "请输入 OneBot 的 Token（可选）"
        }
    ],
    # Gotify 相关配置
    "GOTIFY": [
        {
            "var_suffix": "URL", 
            "title": "Gotify 地址",
            "icon": FluentIcon.SEND,
            "placeholder": "例：https://push.example.de:8080"
        },
        {
            "var_suffix": "TOKEN",
            "title": "App Token",
            "icon": FluentIcon.VPN,
            "placeholder": "Gotify 的 App Token"
        },
        {
            "var_suffix": "PRIORITY",
            "title": "消息优先级",
            "icon": FluentIcon.CLOUD,
            "placeholder": "0"
        }
    ],
    # iGot 相关配置
    "IGOT": [
        {
            "var_suffix": "PUSH_KEY", 
            "title": "推送 Key",
            "icon": FluentIcon.VPN,
            "placeholder": "请输入 iGot 的 推送 Key"
        }
    ],
    # ServerChan 相关配置
    "PUSH": [
        {
            "var_suffix": "KEY",
            "title": "PUSH_KEY",
            "icon": FluentIcon.MESSAGE,
            "placeholder": "请输入 Server 酱的 PUSH_KEY"
        }
    ],
    # PushDeer 相关配置
    "DEER": [
        {
            "var_suffix": "KEY", 
            "title": "KEY",
            "icon": FluentIcon.MESSAGE,
            "placeholder": "请输入 PushDeer 的 PUSHDEER_KEY"
        },
        {
            "var_suffix": "URL",
            "title": "推送URL",
            "icon": FluentIcon.SEND,
            "placeholder": "请输入 PushDeer 的 PUSHDEER_URL"
        }
    ],
    # Synology Chat 相关配置
    "CHAT": [
        {
            "var_suffix": "URL", 
            "title": "URL",
            "icon": FluentIcon.SEND,
            "placeholder": "请输入 Synology Chat 的 URL"
        },
        {
            "var_suffix": "TOKEN",
            "title": "Token",
            "icon": FluentIcon.VPN,
            "placeholder": "请输入 Synology Chat 的 Token"
        }
    ],
    # PUSH_PLUS 相关配置
    "PUSH_PLUS": [
        {
            "var_suffix": "TOKEN", 
            "title": "用户令牌",
            "icon": FluentIcon.VPN,
            "placeholder": "请输入用户令牌"
        },
        {
            "var_suffix": "USER",
            "title": "群组编码",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "请输入群组编码"
        },
        {
            "var_suffix": "TEMPLATE",
            "title": "发送模板",
            "icon": FluentIcon.CLOUD,
            "placeholder": "可选：html,txt,json,markdown,cloudMonitor,jenkins,route"
        },
        {
            "var_suffix": "CHANNEL",
            "title": "发送渠道",
            "icon": FluentIcon.CLOUD,
            "placeholder": "可选：wechat,webhook,cp,mail,sms"
        },
        {
            "var_suffix": "WEBHOOK",
            "title": "webhook编码",
            "icon": FluentIcon.CLOUD,
            "placeholder": "可在公众号上扩展配置出更多渠道"
        },
        {
            "var_suffix": "CALLBACKURL",
            "title": "发送结果回调地址",
            "icon": FluentIcon.SEND,
            "placeholder": "会把推送最终结果通知到这个地址上"
        },
        {
            "var_suffix": "TO",
            "title": "好友令牌或用户ID",
            "icon": FluentIcon.CLOUD,
            "placeholder": "微信公众号：好友令牌；企业微信：用户ID"
        }
    ],
    # 微加机器人 相关配置
    "WE_PLUS_BOT": [
        {
            "var_suffix": "TOKEN", 
            "title": "用户令牌",
            "icon": FluentIcon.VPN,
            "placeholder": "请输入用户令牌"
        },
        {
            "var_suffix": "RECEIVER",
            "title": "消息接收者",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "请输入消息接收者"
        },
        {
            "var_suffix": "VERSION",
            "title": "调用版本",
            "icon": FluentIcon.CLOUD,
            "placeholder": "可选"
        }
    ],
    # QMSG 相关配置
    "QMSG": [
        {
            "var_suffix": "KEY", 
            "title": "KEY",
            "icon": FluentIcon.MESSAGE,
            "placeholder": "请输入 Qmsg 酱的 QMSG_KEY"
        },
        {
            "var_suffix": "TYPE",
            "title": "TYPE",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "请输入 Qmsg 酱的 QMSG_TYPE"
        }
    ],
    # 企业微信 相关配置
    "QYWX": [
        {
            "var_suffix": "ORIGIN", 
            "title": "企业微信代理地址",
            "icon": FluentIcon.MESSAGE,
            "placeholder": "选一项填即可"
        },
        {
            "var_suffix": "AM",
            "title": "企业微信应用",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "选一项填即可"
        },
        {
            "var_suffix": "KEY",
            "title": "企业微信机器人",
            "icon": FluentIcon.CLOUD,
            "placeholder": "选一项填即可"
        }
    ],
    # TG_BOT 相关配置
    "TG": [
        {
            "var_suffix": "BOT_TOKEN", 
            "title": "BOT_TOKEN",
            "icon": FluentIcon.VPN,
            "placeholder": "请输入 Telegram 机器人的 TG_BOT_TOKEN，例：1407203283:AAG9rt-6RDaaX0HBLZQq0laNOh898iFYaRQ"
        },
        {
            "var_suffix": "USER_ID",
            "title": "USER_ID",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "请输入用户ID，例：1434078534"
        },
        {
            "var_suffix": "PROXY_HOST",
            "title": "PROXY_HOST",
            "icon": FluentIcon.CLOUD,
            "placeholder": "可选，例：127.0.0.1"
        },
        {
            "var_suffix": "PROXY_PORT",
            "title": "PROXY_PORT",
            "icon": FluentIcon.CLOUD,
            "placeholder": "可选，例：1080"
        },
        {
            "var_suffix": "PROXY_AUTH",
            "title": "PROXY_AUTH",
            "icon": FluentIcon.CLOUD,
            "placeholder": "代理认证参数"
        },
        {
            "var_suffix": "API_HOST",
            "title": "API_HOST",
            "icon": FluentIcon.CLOUD,
            "placeholder": "可选"
        }
    ],
    # 智能微秘书 相关配置
    "AIBOTK": [
        {
            "var_suffix": "KEY", 
            "title": "APIKEY",
            "icon": FluentIcon.MESSAGE,
            "placeholder": "请输入个人中心的 APIKEY"
        },
        {
            "var_suffix": "TYPE",
            "title": "目标类型",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "请输入 room 或 contact"
        },
        {
            "var_suffix": "NAME",
            "title": "目标名称",
            "icon": FluentIcon.CLOUD,
            "placeholder": "发送群名或者好友昵称，和 type 要对应"
        }
    ],
    # SMTP 相关配置
    "SMTP": [
        {
            "var_suffix": "SERVER", 
            "title": "邮件服务器",
            "icon": FluentIcon.MESSAGE,
            "placeholder": "例：smtp.exmail.qq.com:465"
        },
        {
            "var_suffix": "SSL",
            "title": "是否使用 SSL",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "true 或 false"
        },
        {
            "var_suffix": "EMAIL",
            "title": "收发件邮箱",
            "icon": FluentIcon.CLOUD,
            "placeholder": "将由自己发给自己"
        },
        {
            "var_suffix": "PASSWORD",
            "title": "登录密码",
            "icon": FluentIcon.CLOUD,
            "placeholder": "SMTP 登录密码，也可能为特殊口令"
        },
        {
            "var_suffix": "NAME",
            "title": "收发件人名称",
            "icon": FluentIcon.CLOUD,
            "placeholder": "可随意填写"
        }
    ],
    # PushMe 相关配置
    "PUSHME": [
        {
            "var_suffix": "KEY", 
            "title": "KEY",
            "icon": FluentIcon.MESSAGE,
            "placeholder": ""
        },
        {
            "var_suffix": "URL",
            "title": "URL",
            "icon": FluentIcon.SEND,
            "placeholder": ""
        }
    ],
    # Chronocat 相关配置
    "CHRONOCAT": [
        {
            "var_suffix": "QQ", 
            "title": "QQ",
            "icon": FluentIcon.MESSAGE,
            "placeholder": "请输入接收消息的 QQ 号"
        },
        {
            "var_suffix": "TOKEN",
            "title": "TOKEN",
            "icon": FluentIcon.VPN,
            "placeholder": ""
        },
        {
            "var_suffix": "URL",
            "title": "URL",
            "icon": FluentIcon.SEND,
            "placeholder": ""
        }
    ],
    # WEBHOOK 相关配置
    "WEBHOOK": [
        {
            "var_suffix": "URL", 
            "title": "URL",
            "icon": FluentIcon.SEND,
            "placeholder": "自定义通知 请求地址"
        },
        {
            "var_suffix": "BODY",
            "title": "BODY",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "自定义通知 请求体"
        },
        {
            "var_suffix": "HEADERS",
            "title": "HEADERS",
            "icon": FluentIcon.CLOUD,
            "placeholder": "自定义通知 请求头"
        },
        {
            "var_suffix": "METHOD",
            "title": "METHOD",
            "icon": FluentIcon.CLOUD,
            "placeholder": "自定义通知 请求方法"
        },
        {
            "var_suffix": "CONTENT_TYPE",
            "title": "CONTENT_TYPE",
            "icon": FluentIcon.CLOUD,
            "placeholder": "自定义通知 content-type"
        }
    ],
    # ntfy 相关配置
    "NTFY": [
        {
            "var_suffix": "URL", 
            "title": "URL",
            "icon": FluentIcon.SEND,
            "placeholder": "例：https://ntfy.sh"
        },
        {
            "var_suffix": "TOPIC",
            "title": "TOPIC",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "ntfy 的 Topic"
        },
        {
            "var_suffix": "PRIORITY",
            "title": "消息优先级",
            "icon": FluentIcon.CLOUD,
            "placeholder": "3"
        }
    ],
    # WxPusher 相关配置
    "WXPUSHER": [
        {
            "var_suffix": "APP_TOKEN", 
            "title": "appToken",
            "icon": FluentIcon.VPN,
            "placeholder": "请输入 appToken"
        },
        {
            "var_suffix": "TOPIC_IDS",
            "title": "TOPIC_IDs",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "多个用英文分号;分隔"
        },
        {
            "var_suffix": "UIDS",
            "title": "UIDs",
            "icon": FluentIcon.CLOUD,
            "placeholder": "二者至少配置其中之一"
        }
    ],
}