class PushEmailServices:
    push_email_services = {
    "126": {
        "host": "smtp.126.com",
        "port": 465,
        "secure": True
    },
    "163": {
        "host": "smtp.163.com",
        "port": 465,
        "secure": True
    },
    "1und1": {
        "host": "smtp.1und1.de",
        "port": 465,
        "secure": True,
        "authMethod": "LOGIN"
    },
    "Aliyun": {
        "domains": [
            "aliyun.com"
        ],
        "host": "smtp.aliyun.com",
        "port": 465,
        "secure": True
    },
    "AliyunQiye": {
        "host": "smtp.qiye.aliyun.com",
        "port": 465,
        "secure": True
    },
    "AOL": {
        "domains": [
            "aol.com"
        ],
        "host": "smtp.aol.com",
        "port": 587
    },
    "Bluewin": {
        "host": "smtpauths.bluewin.ch",
        "domains": [
            "bluewin.ch"
        ],
        "port": 465
    },
    "DebugMail": {
        "host": "debugmail.io",
        "port": 25
    },
    "DynectEmail": {
        "aliases": [
            "Dynect"
        ],
        "host": "smtp.dynect.net",
        "port": 25
    },
    "Ethereal": {
        "aliases": [
            "ethereal.email"
        ],
        "host": "smtp.ethereal.email",
        "port": 587
    },
    "FastMail": {
        "domains": [
            "fastmail.fm"
        ],
        "host": "smtp.fastmail.com",
        "port": 465,
        "secure": True
    },
    "Forward Email": {
        "aliases": [
            "FE",
            "ForwardEmail"
        ],
        "domains": [
            "forwardemail.net"
        ],
        "host": "smtp.forwardemail.net",
        "port": 465,
        "secure": True
    },
    "Feishu Mail": {
        "aliases": [
            "Feishu",
            "FeishuMail"
        ],
        "domains": [
            "www.feishu.cn"
        ],
        "host": "smtp.feishu.cn",
        "port": 465,
        "secure": True
    },
    "GandiMail": {
        "aliases": [
            "Gandi",
            "Gandi Mail"
        ],
        "host": "mail.gandi.net",
        "port": 587
    },
    "Gmail": {
        "aliases": [
            "Google Mail"
        ],
        "domains": [
            "gmail.com",
            "googlemail.com"
        ],
        "host": "smtp.gmail.com",
        "port": 465,
        "secure": True
    },
    "Godaddy": {
        "host": "smtpout.secureserver.net",
        "port": 25
    },
    "GodaddyAsia": {
        "host": "smtp.asia.secureserver.net",
        "port": 25
    },
    "GodaddyEurope": {
        "host": "smtp.europe.secureserver.net",
        "port": 25
    },
    "hot.ee": {
        "host": "mail.hot.ee"
    },
    "Hotmail": {
        "aliases": [
            "Outlook",
            "Outlook.com",
            "Hotmail.com"
        ],
        "domains": [
            "hotmail.com",
            "outlook.com"
        ],
        "host": "smtp-mail.outlook.com",
        "port": 587
    },
    "iCloud": {
        "aliases": [
            "Me",
            "Mac"
        ],
        "domains": [
            "me.com",
            "mac.com"
        ],
        "host": "smtp.mail.me.com",
        "port": 587
    },
    "Infomaniak": {
        "host": "mail.infomaniak.com",
        "domains": [
            "ik.me",
            "ikmail.com",
            "etik.com"
        ],
        "port": 587
    },
    "Loopia": {
        "host": "mailcluster.loopia.se",
        "port": 465
    },
    "mail.ee": {
        "host": "smtp.mail.ee"
    },
    "Mail.ru": {
        "host": "smtp.mail.ru",
        "port": 465,
        "secure": True
    },
    "Mailcatch.app": {
        "host": "sandbox-smtp.mailcatch.app",
        "port": 2525
    },
    "Maildev": {
        "port": 1025,
        "ignoreTLS": True
    },
    "Mailgun": {
        "host": "smtp.mailgun.org",
        "port": 465,
        "secure": True
    },
    "Mailjet": {
        "host": "in.mailjet.com",
        "port": 587
    },
    "Mailosaur": {
        "host": "mailosaur.io",
        "port": 25
    },
    "Mailtrap": {
        "host": "live.smtp.mailtrap.io",
        "port": 587
    },
    "Mandrill": {
        "host": "smtp.mandrillapp.com",
        "port": 587
    },
    "Naver": {
        "host": "smtp.naver.com",
        "port": 587
    },
    "One": {
        "host": "send.one.com",
        "port": 465,
        "secure": True
    },
    "OpenMailBox": {
        "aliases": [
            "OMB",
            "openmailbox.org"
        ],
        "host": "smtp.openmailbox.org",
        "port": 465,
        "secure": True
    },
    "Outlook365": {
        "host": "smtp.office365.com",
        "port": 587,
        "secure": False
    },
    "OhMySMTP": {
        "host": "smtp.ohmysmtp.com",
        "port": 587,
        "secure": False
    },
    "Postmark": {
        "aliases": [
            "PostmarkApp"
        ],
        "host": "smtp.postmarkapp.com",
        "port": 2525
    },
    "Proton": {
        "aliases": [
            "ProtonMail",
            "Proton.me",
            "Protonmail.com",
            "Protonmail.ch"
        ],
        "domains": [
            "proton.me",
            "protonmail.com",
            "pm.me",
            "protonmail.ch"
        ],
        "host": "smtp.protonmail.ch",
        "port": 587,
        "requireTLS": True
    },
    "qiye.aliyun": {
        "host": "smtp.mxhichina.com",
        "port": "465",
        "secure": True
    },
    "QQ": {
        "domains": [
            "qq.com"
        ],
        "host": "smtp.qq.com",
        "port": 465,
        "secure": True
    },
    "QQex": {
        "aliases": [
            "QQ Enterprise"
        ],
        "domains": [
            "exmail.qq.com"
        ],
        "host": "smtp.exmail.qq.com",
        "port": 465,
        "secure": True
    },
    "SendCloud": {
        "host": "smtp.sendcloud.net",
        "port": 2525
    },
    "SendGrid": {
        "host": "smtp.sendgrid.net",
        "port": 587
    },
    "SendinBlue": {
        "aliases": [
            "Brevo"
        ],
        "host": "smtp-relay.brevo.com",
        "port": 587
    },
    "SendPulse": {
        "host": "smtp-pulse.com",
        "port": 465,
        "secure": True
    },
    "SES": {
        "host": "email-smtp.us-east-1.amazonaws.com",
        "port": 465,
        "secure": True
    },
    "SES-US-EAST-1": {
        "host": "email-smtp.us-east-1.amazonaws.com",
        "port": 465,
        "secure": True
    },
    "SES-US-WEST-2": {
        "host": "email-smtp.us-west-2.amazonaws.com",
        "port": 465,
        "secure": True
    },
    "SES-EU-WEST-1": {
        "host": "email-smtp.eu-west-1.amazonaws.com",
        "port": 465,
        "secure": True
    },
    "SES-AP-SOUTH-1": {
        "host": "email-smtp.ap-south-1.amazonaws.com",
        "port": 465,
        "secure": True
    },
    "SES-AP-NORTHEAST-1": {
        "host": "email-smtp.ap-northeast-1.amazonaws.com",
        "port": 465,
        "secure": True
    },
    "SES-AP-NORTHEAST-2": {
        "host": "email-smtp.ap-northeast-2.amazonaws.com",
        "port": 465,
        "secure": True
    },
    "SES-AP-NORTHEAST-3": {
        "host": "email-smtp.ap-northeast-3.amazonaws.com",
        "port": 465,
        "secure": True
    },
    "SES-AP-SOUTHEAST-1": {
        "host": "email-smtp.ap-southeast-1.amazonaws.com",
        "port": 465,
        "secure": True
    },
    "SES-AP-SOUTHEAST-2": {
        "host": "email-smtp.ap-southeast-2.amazonaws.com",
        "port": 465,
        "secure": True
    },
    "Seznam": {
        "aliases": [
            "Seznam Email"
        ],
        "domains": [
            "seznam.cz",
            "email.cz",
            "post.cz",
            "spoluzaci.cz"
        ],
        "host": "smtp.seznam.cz",
        "port": 465,
        "secure": True
    },
    "Sparkpost": {
        "aliases": [
            "SparkPost",
            "SparkPost Mail"
        ],
        "domains": [
            "sparkpost.com"
        ],
        "host": "smtp.sparkpostmail.com",
        "port": 587,
        "secure": False
    },
    "Tipimail": {
        "host": "smtp.tipimail.com",
        "port": 587
    },
    "Yahoo": {
        "domains": [
            "yahoo.com"
        ],
        "host": "smtp.mail.yahoo.com",
        "port": 465,
        "secure": True
    },
    "Yandex": {
        "domains": [
            "yandex.ru"
        ],
        "host": "smtp.yandex.ru",
        "port": 465,
        "secure": True
    },
    "Zoho": {
        "host": "smtp.zoho.com",
        "port": 465,
        "secure": True,
        "authMethod": "LOGIN"
    }
}

    @classmethod
    def get_configs(cls, keyword: str):
        """
        根据关键词、别名、域名查找邮箱服务配置。
        :param keyword: 用户输入的邮箱服务关键字（如 qq/gmail/163/域名等）
        :return: 匹配到的邮箱服务配置 dict 或 None
        """
        services = cls.push_email_services
        key = keyword.strip().lower()
        for service_name, config in services.items():
            # 关键词匹配
            if key == service_name.lower():
                return config
            # 匹配别名
            if "aliases" in config and key in [alias.lower() for alias in config["aliases"]]:
                return config
            # 匹配域名
            if "domains" in config and key in [domain.lower() for domain in config["domains"]]:
                return config
        return None

    @classmethod
    def load_services(cls):
        """
        加载所有邮箱服务配置。
        :return: 所有邮箱服务配置的字典
        """
        return cls.push_email_services
