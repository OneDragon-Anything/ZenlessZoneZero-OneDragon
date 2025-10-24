import base64
import hashlib
import hmac
import time

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum


class DingDingBot(PushChannel):

    def __init__(self):
        config_schema = [
            PushChannelConfigField(
                var_suffix="SECRET",
                title="Secret",
                icon="CERTIFICATE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入钉钉机器人的Secret密钥",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="TOKEN",
                title="Token",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入钉钉机器人的Token密钥",
                required=True
            )
        ]

        super().__init__(
            channel_id='DD_BOT',
            channel_name='钉钉机器人',
            config_schema=config_schema
        )

    def _generate_sign(self, secret: str, timestamp: str) -> str:
        """
        生成钉钉机器人签名

        Args:
            secret: 密钥
            timestamp: 时间戳

        Returns:
            签名结果
        """
        secret_enc = secret.encode('utf-8')
        string_to_sign = '{}\n{}'.format(timestamp, secret)
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        return sign

    def push(
        self,
        config: dict[str, str],
        title: str,
        content: str,
        image: MatLike | None = None,
        proxy_url: str | None = None,
    ) -> tuple[bool, str]:
        """
        推送消息到钉钉机器人

        Args:
            config: 配置字典，包含 SECRET 和 TOKEN
            title: 消息标题
            content: 消息内容
            image: 图片数据（钉钉机器人暂不支持图片推送）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            secret = config.get('SECRET', '')
            token = config.get('TOKEN', '')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # 生成时间戳和签名
            timestamp = str(round(time.time() * 1000))
            sign = self._generate_sign(secret, timestamp)
            # 构建消息内容
            message_data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"{title}\n{content}",
                    #需要在"title"中添加消息具体内容{content},否则钉钉在系统通知栏只显示{title}部分无法识别对应的具体步骤
                    "text": f"## {title}\n\n{content}"
                }
            }

            # 发送请求
            headers = {'Content-Type': 'application/json'}

            # 构建请求URL与查询参数（由 requests 进行 URL 编码）
            webhook_base = "https://oapi.dingtalk.com/robot/send"
            params = {
                "access_token": token,
                "timestamp": timestamp,
                "sign": sign,
            }
            response = requests.post(
                webhook_base,
                params=params,
                json=message_data,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    return True, "推送成功"
                else:
                    return False, f"钉钉机器人推送失败: {result.get('errmsg', '未知错误')}"
            else:
                return False, f"HTTP请求失败，状态码: {response.status_code}"

        except Exception as e:
            return False, f"钉钉机器人推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证钉钉机器人配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        secret = config.get('SECRET', '')
        token = config.get('TOKEN', '')

        if len(secret) == 0:
            return False, "Secret不能为空"

        if len(token) == 0:
            return False, "Token不能为空"

        return True, "配置验证通过"