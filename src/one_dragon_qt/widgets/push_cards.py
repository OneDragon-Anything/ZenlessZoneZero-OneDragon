class PushCards:
    push_cards = {
    "WEBHOOK": [
        {
            "var_suffix": "URL",
            "title": "URL",
            "icon": "LINK",
            "placeholder": "请输入 Webhook URL",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "METHOD",
            "title": "HTTP 方法",
            "icon": "APPLICATION",
            "type": "combo",
            "options": ["POST", "GET", "PUT"],
            "default": "POST",
            "required": True
        },
        {
            "var_suffix": "CONTENT_TYPE",
            "title": "Content-Type",
            "icon": "CODE",
            "type": "combo",
            "options": ["application/json", "application/x-www-form-urlencoded", "application/xml", "text/plain"],
            "default": "application/json",
            "required": True
        },
        {
            "var_suffix": "HEADERS",
            "title": "请求头 (Headers)",
            "icon": "LEFT_ARROW",
            "type": "key_value",
            "placeholder": {"key": "Key", "value": "Value"}
        },
        {
            "var_suffix": "BODY",
            "title": "请求体 (Payload)",
            "icon": "DOCUMENT",
            "type": "code_editor",
            "language": "json",
            "placeholder": "请输入请求体内容",
            "required": True
        }
    ],
    "BARK": [
        {
            "var_suffix": "PUSH",
            "title": "推送地址或 Key",
            "icon": "SEND",
            "placeholder": "请输入 Bark 推送地址或 Key",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "DEVICE_KEY",
            "title": "设备码",
            "icon": "PHONE",
            "placeholder": "请填写设备码",
            "type": "text"
        },
        {
            "var_suffix": "ARCHIVE",
            "title": "推送是否存档",
            "icon": "FOLDER",
            "type": "combo",
            "options": ["", "1", "0"],
            "default": "0"
        },
        {
            "var_suffix": "GROUP",
            "title": "推送分组",
            "icon": "PEOPLE",
            "placeholder": "请填写推送分组",
            "type": "text"
        },
        {
            "var_suffix": "SOUND",
            "title": "推送铃声",
            "icon": "HEADPHONE",
            "placeholder": "请填写铃声名称",
            "type": "text"
        },
        {
            "var_suffix": "ICON",
            "title": "推送图标",
            "icon": "PHOTO",
            "placeholder": "请填写图标的URL",
            "type": "text"
        },
        {
            "var_suffix": "LEVEL",
            "title": "推送中断级别",
            "icon": "DATE_TIME",
            "type": "combo",
            "options": ["", "critical", "active", "timeSensitive", "passive"],
            "default": "active"
        },
        {
            "var_suffix": "URL",
            "title": "推送跳转URL",
            "icon": "LINK",
            "placeholder": "请填写推送跳转URL",
            "type": "text"
        }
    ],
    "DD_BOT": [
        {
            "var_suffix": "SECRET",
            "title": "Secret",
            "icon": "CERTIFICATE",
            "placeholder": "请输入钉钉机器人的Secret密钥",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "TOKEN",
            "title": "Token",
            "icon": "VPN",
            "placeholder": "请输入钉钉机器人的Token密钥",
            "type": "text",
            "required": True
        }
    ],
    "FS": [
        {
            "var_suffix": "CHANNEL",
            "title": "服务类型",
            "icon": "APPLICATION",
            "type": "combo",
            "options": ["飞书", "Lark"],
            "default": "飞书",
            "required": True
        },
        {
            "var_suffix": "KEY",
            "title": "密钥",
            "icon": "CERTIFICATE",
            "placeholder": "请输入飞书机器人的密钥",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "APPID",
            "title": "自建应用 App ID",
            "icon": "APPLICATION",
            "placeholder": "非必填，填写则用于发送图片",
            "type": "text",
            "required": False
        },
        {
            "var_suffix": "APPSECRET",
            "title": "自建应用 Secret",
            "icon": "VPN",
            "placeholder": "非必填，填写则用于发送图片",
            "type": "text",
            "required": False
        }
    ],
    "ONEBOT": [
        {
            "var_suffix": "URL",
            "title": "请求地址",
            "icon": "SEND",
            "placeholder": "请输入请求地址",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "USER",
            "title": "QQ 号",
            "icon": "PEOPLE",
            "placeholder": "请输入目标 QQ 号",
            "type": "text"
        },
        {
            "var_suffix": "GROUP",
            "title": "群号",
            "icon": "PEOPLE",
            "placeholder": "请输入目标群号",
            "type": "text"
        },
        {
            "var_suffix": "TOKEN",
            "title": "Token",
            "icon": "VPN",
            "placeholder": "请输入 OneBot 的 Token",
            "type": "text"
        }
    ],
    "GOTIFY": [
        {
            "var_suffix": "URL",
            "title": "Gotify 地址",
            "icon": "SEND",
            "placeholder": "https://push.example.de:8080",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "TOKEN",
            "title": "App Token",
            "icon": "VPN",
            "placeholder": "Gotify 的 App Token",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "PRIORITY",
            "title": "消息优先级",
            "icon": "CLOUD",
            "type": "combo",
            "options": ["", "0", "1", "2", "3", "4", "5"],
            "default": "5"
        }
    ],
    "IGOT": [
        {
            "var_suffix": "PUSH_KEY",
            "title": "推送 Key",
            "icon": "VPN",
            "placeholder": "请输入 iGot 的 推送 Key",
            "type": "text",
            "required": True
        }
    ],
    "SERVERCHAN": [
        {
            "var_suffix": "PUSH_KEY",
            "title": "PUSH_KEY",
            "icon": "MESSAGE",
            "placeholder": "请输入 Server 酱的 PUSH_KEY",
            "type": "text",
            "required": True
        }
    ],
    "DEER": [
        {
            "var_suffix": "KEY",
            "title": "KEY",
            "icon": "MESSAGE",
            "placeholder": "请输入 PushDeer 的 KEY",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "URL",
            "title": "推送URL",
            "icon": "SEND",
            "placeholder": "请输入 PushDeer 的 推送URL",
            "type": "text"
        }
    ],
    "CHAT": [
        {
            "var_suffix": "URL",
            "title": "URL",
            "icon": "SEND",
            "placeholder": "请输入 Synology Chat 的 URL",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "TOKEN",
            "title": "Token",
            "icon": "VPN",
            "placeholder": "请输入 Synology Chat 的 Token",
            "type": "text",
            "required": True
        }
    ],
    "PUSH_PLUS": [
        {
            "var_suffix": "TOKEN",
            "title": "用户令牌",
            "icon": "VPN",
            "placeholder": "请输入用户令牌",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "USER",
            "title": "群组编码",
            "icon": "PEOPLE",
            "placeholder": "请输入群组编码",
            "type": "text"
        },
        {
            "var_suffix": "TEMPLATE",
            "title": "发送模板",
            "icon": "CLOUD",
            "type": "combo",
            "options": ["", "html", "txt", "json", "markdown", "cloudMonitor", "jenkins", "route"],
            "default": "html"
        },
        {
            "var_suffix": "CHANNEL",
            "title": "发送渠道",
            "icon": "CLOUD",
            "type": "combo",
            "options": ["", "wechat", "webhook", "cp", "mail", "sms"],
            "default": "wechat"
        },
        {
            "var_suffix": "TO",
            "title": "好友令牌或用户ID",
            "icon": "CLOUD",
            "placeholder": "微信公众号：好友令牌；企业微信：用户ID",
            "type": "text"
        },
        {
            "var_suffix": "WEBHOOK",
            "title": "Webhook 编码",
            "icon": "CLOUD",
            "placeholder": "可在公众号上扩展配置出更多渠道",
            "type": "text"
        },
        {
            "var_suffix": "CALLBACKURL",
            "title": "发送结果回调地址",
            "icon": "SEND",
            "placeholder": "会把推送最终结果通知到这个地址上",
            "type": "text"
        }
    ],
    "WE_PLUS_BOT": [
        {
            "var_suffix": "TOKEN",
            "title": "用户令牌",
            "icon": "VPN",
            "placeholder": "请输入用户令牌",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "RECEIVER",
            "title": "消息接收者",
            "icon": "PEOPLE",
            "placeholder": "请输入消息接收者",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "VERSION",
            "title": "调用版本",
            "icon": "CLOUD",
            "placeholder": "可选",
            "type": "text"
        }
    ],
    "QMSG": [
        {
            "var_suffix": "KEY",
            "title": "KEY",
            "icon": "MESSAGE",
            "placeholder": "请输入 Qmsg 酱的 KEY",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "TYPE",
            "title": "通知类型",
            "icon": "PEOPLE",
            "type": "combo",
            "options": ["send", "group"],
            "default": "send",
            "required": True
        }
    ],
    "QYWX": [
        {
            "var_suffix": "ORIGIN",
            "title": "企业微信代理地址",
            "icon": "SEND",
            "placeholder": "可选",
            "type": "text"
        },
        {
            "var_suffix": "AM",
            "title": "企业微信应用",
            "icon": "APPLICATION",
            "placeholder": "http://note.youdao.com/s/HMiudGkb",
            "type": "text"
        },
        {
            "var_suffix": "KEY",
            "title": "企业微信机器人 Key",
            "icon": "VPN",
            "placeholder": "只填 Key",
            "type": "text"
        }
    ],
    "DISCORD": [
        {
            "var_suffix": "BOT_TOKEN",
            "title": "机器人 Token",
            "icon": "VPN",
            "placeholder": "请输入 Discord 机器人的 Token",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "USER_ID",
            "title": "用户 ID",
            "icon": "PEOPLE",
            "placeholder": "请输入要接收私信的用户 ID",
            "type": "text",
            "required": True
        }
    ],
    "TG": [
        {
            "var_suffix": "BOT_TOKEN",
            "title": "BOT_TOKEN",
            "icon": "VPN",
            "placeholder": "1234567890:AAAAAA-BBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "USER_ID",
            "title": "用户 ID",
            "icon": "PEOPLE",
            "placeholder": "1234567890",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "PROXY_HOST",
            "title": "代理 URL",
            "icon": "CLOUD",
            "placeholder": "127.0.0.1",
            "type": "text"
        },
        {
            "var_suffix": "PROXY_PORT",
            "title": "代理端口",
            "icon": "CLOUD",
            "placeholder": "7890",
            "type": "text"
        },
        {
            "var_suffix": "PROXY_AUTH",
            "title": "PROXY_AUTH",
            "icon": "CLOUD",
            "placeholder": "代理认证参数",
            "type": "text"
        },
        {
            "var_suffix": "API_HOST",
            "title": "API_HOST",
            "icon": "CLOUD",
            "placeholder": "可选",
            "type": "text"
        }
    ],
    "AIBOTK": [
        {
            "var_suffix": "KEY",
            "title": "APIKEY",
            "icon": "MESSAGE",
            "placeholder": "请输入个人中心的 APIKEY",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "TYPE",
            "title": "目标类型",
            "icon": "PEOPLE",
            "type": "combo",
            "options": ["room", "contact"],
            "default": "contact",
            "required": True
        },
        {
            "var_suffix": "NAME",
            "title": "目标名称",
            "icon": "CLOUD",
            "placeholder": "发送群名或者好友昵称，和 type 要对应",
            "type": "text",
            "required": True
        }
    ],
    "SMTP": [
        {
            "var_suffix": "SERVER",
            "title": "邮件服务器",
            "icon": "MESSAGE",
            "placeholder": "smtp.exmail.qq.com:465",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "SSL",
            "title": "使用 SSL",
            "icon": "PEOPLE",
            "type": "combo",
            "options": ["true", "false"],
            "default": "true",
            "required": True
        },
        {
            "var_suffix": "STARTTLS",
            "title": "使用 STARTTLS",
            "icon": "PEOPLE",
            "type": "combo",
            "options": ["true", "false"],
            "default": "false",
            "required": True
        },
        {
            "var_suffix": "EMAIL",
            "title": "收发件邮箱",
            "icon": "CLOUD",
            "placeholder": "将由自己发给自己",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "PASSWORD",
            "title": "登录密码",
            "icon": "CLOUD",
            "placeholder": "SMTP 登录密码，也可能为特殊口令",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "NAME",
            "title": "收发件人名称",
            "icon": "CLOUD",
            "placeholder": "可随意填写",
            "type": "text"
        }
    ],
    "PUSHME": [
        {
            "var_suffix": "KEY",
            "title": "KEY",
            "icon": "MESSAGE",
            "placeholder": "请输入 PushMe 的 KEY",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "URL",
            "title": "URL",
            "icon": "SEND",
            "placeholder": "请输入 PushMe 的 URL",
            "type": "text"
        }
    ],
    "CHRONOCAT": [
        {
            "var_suffix": "QQ",
            "title": "QQ",
            "icon": "MESSAGE",
            "placeholder": "user_id=xxx;group_id=yyy;group_id=zzz",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "TOKEN",
            "title": "TOKEN",
            "icon": "VPN",
            "placeholder": "填写在CHRONOCAT文件生成的访问密钥",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "URL",
            "title": "URL",
            "icon": "SEND",
            "placeholder": "http://127.0.0.1:16530",
            "type": "text",
            "required": True
        }
    ],
    "NTFY": [
        {
            "var_suffix": "URL",
            "title": "URL",
            "icon": "SEND",
            "placeholder": "https://ntfy.sh",
            "type": "text"
        },
        {
            "var_suffix": "TOPIC",
            "title": "TOPIC",
            "icon": "PEOPLE",
            "placeholder": "ntfy 应用 Topic",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "PRIORITY",
            "title": "消息优先级",
            "icon": "CLOUD",
            "type": "combo",
            "options": ["1", "2", "3", "4", "5"],
            "default": "3"
        },
        {
            "var_suffix": "TOKEN",
            "title": "TOKEN",
            "icon": "VPN",
            "placeholder": "ntfy 应用 token",
            "type": "text"
        },
        {
            "var_suffix": "USERNAME",
            "title": "用户名称",
            "icon": "PEOPLE",
            "placeholder": "ntfy 应用用户名",
            "type": "text"
        },
        {
            "var_suffix": "PASSWORD",
            "title": "用户密码",
            "icon": "VPN",
            "placeholder": "ntfy 应用密码",
            "type": "text"
        },
        {
            "var_suffix": "ACTIONS",
            "title": "用户动作",
            "icon": "APPLICATION",
            "placeholder": "ntfy 用户动作，最多三个",
            "type": "text"
        }
    ],
    "WXPUSHER": [
        {
            "var_suffix": "APP_TOKEN",
            "title": "appToken",
            "icon": "VPN",
            "placeholder": "请输入 appToken",
            "type": "text",
            "required": True
        },
        {
            "var_suffix": "TOPIC_IDS",
            "title": "TOPIC_IDs",
            "icon": "PEOPLE",
            "placeholder": "多个用英文分号;分隔",
            "type": "text"
        },
        {
            "var_suffix": "UIDS",
            "title": "UIDs",
            "icon": "CLOUD",
            "placeholder": "二者至少配置其中之一",
            "type": "text"
        }
    ]
}

    @classmethod
    def get_configs(cls):
        return cls.push_cards
