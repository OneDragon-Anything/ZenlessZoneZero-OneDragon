import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class Smtp(PushChannel):
    """SMTP邮件推送渠道"""

    def __init__(self):
        """初始化SMTP邮件推送渠道"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="SERVER",
                title="邮件服务器",
                icon="MESSAGE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="smtp.exmail.qq.com:465",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="SSL",
                title="使用 SSL",
                icon="PEOPLE",
                field_type=FieldTypeEnum.COMBO,
                options=["true", "false"],
                default="true",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="STARTTLS",
                title="使用 STARTTLS",
                icon="PEOPLE",
                field_type=FieldTypeEnum.COMBO,
                options=["true", "false"],
                default="false",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="EMAIL",
                title="收发件邮箱",
                icon="CLOUD",
                field_type=FieldTypeEnum.TEXT,
                placeholder="将由自己发给自己",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="PASSWORD",
                title="登录密码",
                icon="CLOUD",
                field_type=FieldTypeEnum.TEXT,
                placeholder="SMTP 登录密码，也可能为特殊口令",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="NAME",
                title="收发件人名称",
                icon="CLOUD",
                field_type=FieldTypeEnum.TEXT,
                placeholder="可随意填写",
                required=False
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='SMTP',
            channel_name='SMTP邮件',
            config_schema=config_schema
        )

    def push(
        self,
        config: dict[str, str],
        title: str,
        content: str,
        image: MatLike | None = None,
        proxy_url: str | None = None,
    ) -> tuple[bool, str]:
        """
        推送消息到SMTP邮件

        Args:
            config: 配置字典，包含 SERVER、SSL、STARTTLS、EMAIL、PASSWORD 和 NAME
            title: 消息标题
            content: 消息内容
            image: 图片数据（SMTP邮件暂不支持图片推送）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            # 验证配置
            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            server = config.get('SERVER', '')
            use_ssl = config.get('SSL', 'true').lower() == 'true'
            use_starttls = config.get('STARTTLS', 'false').lower() == 'true'
            email = config.get('EMAIL', '')
            password = config.get('PASSWORD', '')
            name = config.get('NAME', 'OneDragon')

            # 创建邮件消息
            message = MIMEText(content, "plain", "utf-8")
            message["From"] = formataddr(
                (Header(name, "utf-8").encode(),
                 email)
            )
            message["To"] = formataddr(
                (Header(name, "utf-8").encode(),
                 email)
            )
            message["Subject"] = Header(title, "utf-8")
            # 解析服务器地址和端口
            host, port = server.split(":")
            port_int = int(port) if port else None
            # 连接SMTP服务器并发送邮件
            smtp_server = (
                smtplib.SMTP_SSL(host, port_int) if use_ssl
                else smtplib.SMTP(host, port_int)
            )

            try:
                # 使用STARTTLS（如果配置了）
                if use_starttls and not use_ssl:
                    smtp_server.starttls()

                # 登录
                smtp_server.login(email, password)

                # 发送邮件
                smtp_server.sendmail(
                    email,
                    email,
                    message.as_bytes()
                )

                return True, "SMTP邮件推送成功"

            except Exception as e:
                log.error('SMTP邮件推送异常', exc_info=True)
                return False, f"SMTP邮件推送异常: {str(e)}"

            finally:
                smtp_server.close()

        except Exception as e:
            log.error('SMTP邮件推送异常', exc_info=True)
            return False, f"SMTP邮件推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证SMTP配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        server = config.get('SERVER', '')
        use_ssl = config.get('SSL', 'true').lower()
        use_starttls = config.get('STARTTLS', 'false').lower()
        email = config.get('EMAIL', '')
        password = config.get('PASSWORD', '')

        if not server.strip():
            return False, "邮件服务器不能为空"

        if use_ssl not in ["true", "false"]:
            return False, "SSL配置必须为 true 或 false"

        if use_starttls not in ["true", "false"]:
            return False, "STARTTLS配置必须为 true 或 false"

        if not email.strip():
            return False, "收发件邮箱不能为空"

        # 简单的邮箱格式验证
        if "@" not in email or "." not in email.split("@")[-1]:
            return False, "邮箱格式不正确"

        if not password.strip():
            return False, "登录密码不能为空"

        # 检查服务器格式
        if ":" not in server:
            return False, "邮件服务器格式不正确，应包含端口号（如：smtp.exmail.qq.com:465）"

        try:
            host, port = server.split(":")
            port_int = int(port)
            if port_int < 1 or port_int > 65535:
                return False, "端口号必须在1-65535之间"
        except ValueError:
            return False, "端口号必须为数字"

        return True, "配置验证通过"