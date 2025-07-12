from qfluentwidgets import FluentIcon

class PushCards:
    push_cards = {
    "BARK": [
        {
            "var_suffix": "PUSH",
            "title": "推送地址或 Key",
            "icon": FluentIcon.SEND,
            "placeholder": "请输入 Bark 推送地址或 Key"
        },
        {
            "var_suffix": "DEVICE_KEY",
            "title": "设备码",
            "icon": FluentIcon.PHONE,
            "placeholder": "请填写设备码（可选）"
        },
        {
            "var_suffix": "ARCHIVE",
            "title": "推送是否存档",
            "icon": FluentIcon.FOLDER,
            "placeholder": "填写1为存档，0为不存档"
        },
        {
            "var_suffix": "GROUP",
            "title": "推送分组",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "请填写推送分组（可选）"
        },
        {
            "var_suffix": "SOUND",
            "title": "推送铃声",
            "icon": FluentIcon.HEADPHONE,
            "placeholder": "请填写铃声名称（可选）"
        },
        {
            "var_suffix": "ICON",
            "title": "推送图标",
            "icon": FluentIcon.PHOTO,
            "placeholder": "请填写图标的URL（可选）"
        },
        {
            "var_suffix": "LEVEL",
            "title": "推送中断级别",
            "icon": FluentIcon.DATE_TIME,
            "placeholder": "critical, active, timeSensitive, passive"
        },
        {
            "var_suffix": "URL",
            "title": "推送跳转URL",
            "icon": FluentIcon.LINK,
            "placeholder": "请填写推送跳转URL（可选）"
        }
    ],
    "DD_BOT": [
        {
            "var_suffix": "SECRET",
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
    "FS": [
        {
            "var_suffix": "KEY",
            "title": "密钥",
            "icon": FluentIcon.CERTIFICATE,
            "placeholder": "请输入飞书机器人的密钥"
        }
    ],
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
    "IGOT": [
        {
            "var_suffix": "PUSH_KEY",
            "title": "推送 Key",
            "icon": FluentIcon.VPN,
            "placeholder": "请输入 iGot 的 推送 Key"
        }
    ],
    "SERVERCHAN": [
        {
            "var_suffix": "PUSH_KEY",
            "title": "PUSH_KEY",
            "icon": FluentIcon.MESSAGE,
            "placeholder": "请输入 Server 酱的 PUSH_KEY"
        }
    ],
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
            "title": "Webhook编码",
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
    "QYWX": [
        {
            "var_suffix": "ORIGIN",
            "title": "企业微信代理地址",
            "icon": FluentIcon.SEND,
            "placeholder": "可选"
        },
        {
            "var_suffix": "AM",
            "title": "企业微信应用",
            "icon": FluentIcon.APPLICATION,
            "placeholder": "http://note.youdao.com/s/HMiudGkb"
        },
        {
            "var_suffix": "KEY",
            "title": "企业微信机器人 Key",
            "icon": FluentIcon.VPN,
            "placeholder": "只填 Key"
        }
    ],
    "DISCORD": [
        {
            "var_suffix": "BOT_TOKEN",
            "title": "机器人 Token",
            "icon": FluentIcon.VPN,
            "placeholder": "请输入 Discord 机器人的 Token"
        },
        {
            "var_suffix": "USER_ID",
            "title": "用户 ID",
            "icon": FluentIcon.PEOPLE,
            "placeholder": "请输入要接收私信的用户 ID"
        }
    ],
    "TG": [
        {
            "var_suffix": "BOT_TOKEN",
            "title": "BOT_TOKEN",
            "icon": FluentIcon.VPN,
            "placeholder": "请输入 BOT_TOKEN，例：1407203283:AAG9rt-6RDaaX0HBLZQq0laNOh898iFYaRQ"
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
    "CHRONOCAT": [
        {
            "var_suffix": "QQ",
            "title": "QQ",
            "icon": FluentIcon.MESSAGE,
            "placeholder": "user_id=xxx;group_id=yyy;group_id=zzz"
        },
        {
            "var_suffix": "TOKEN",
            "title": "TOKEN",
            "icon": FluentIcon.VPN,
            "placeholder": "填写在CHRONOCAT文件生成的访问密钥"
        },
        {
            "var_suffix": "URL",
            "title": "URL",
            "icon": FluentIcon.SEND,
            "placeholder": "http://127.0.0.1:16530"
        }
    ],
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
    ]
}

    @classmethod
    def get_configs(cls):
        return cls.push_cards