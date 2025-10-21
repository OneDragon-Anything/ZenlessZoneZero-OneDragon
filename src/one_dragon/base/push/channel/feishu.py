import base64
import hashlib
import hmac
import time

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


def gen_sign(timestamp: int, secret: str):
    # 拼接timestamp和secret
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()

    # 对结果进行base64处理
    sign = base64.b64encode(hmac_code).decode('utf-8')

    return sign


class FeiShu(PushChannel):

    def __init__(self):
        config_schema = [
            PushChannelConfigField(
                var_suffix="CHANNEL",
                title="服务类型",
                icon="APPLICATION",
                field_type=FieldTypeEnum.COMBO,
                options=["飞书", "Lark"],
                default="飞书",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="KEY",
                title="Webhook地址后缀",
                icon="CERTIFICATE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入飞书机器人的Webhook地址后缀",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="BOT_SECRET",
                title="机器人签名校验密钥",
                icon="CERTIFICATE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="创建机器人时勾选签名校验显示的密钥",
            ),
            PushChannelConfigField(
                var_suffix="APPID",
                title="自建应用 App ID",
                icon="APPLICATION",
                field_type=FieldTypeEnum.TEXT,
                placeholder="非必填，填写则用于发送图片",
                required=False
            ),
            PushChannelConfigField(
                var_suffix="APPSECRET",
                title="自建应用 Secret",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="非必填，填写则用于发送图片",
                required=False
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='FS',
            channel_name='飞书/Lark 机器人',
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
        推送消息到飞书/Lark机器人

        Args:
            config: 配置字典，包含 CHANNEL、KEY、APPID、APPSECRET
            title: 消息标题
            content: 消息内容
            image: 图片数据（可选，需要APPID和APPSECRET）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            key = config.get('KEY', '')
            bot_secret = config.get('BOT_SECRET', '')
            channel = config.get('CHANNEL', '')
            app_id = config.get('APPID', '')
            app_secret = config.get('APPSECRET', '')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # 根据服务类型选择基础域名
            base_url = "open.feishu.cn" if channel == "飞书" else "open.larksuite.com"

            image_key = None
            # 如果有图片且配置了自建应用信息，先上传图片
            if image is not None and len(app_id) > 0 and len(app_secret) > 0:
                image_key = self._upload_image(image, app_id, app_secret, base_url)
                if image_key is None:
                    return False, "图片上传失败"

            # 构建消息内容
            if image_key:
                # 富文本消息（包含图片）
                message_data = {
                    "msg_type": "post",
                    "content": {
                        "post": {
                            "zh_cn": {
                                "title": title,
                                "content": [
                                    [{
                                        "tag": "text",
                                        "text": f"{content}"
                                    }, {
                                        "tag": "img",
                                        "image_key": image_key
                                    }]
                                ]
                            }
                        }
                    }
                }
            else:
                # 普通文本消息
                message_data = {
                    "msg_type": "text",
                    "content": {"text": f"{title}\n{content}"}
                }

            now = int(time.time())
            if len(bot_secret) > 0:
                message_data["timestamp"] = str(now)
                message_data["sign"] = gen_sign(now, bot_secret)

            # 发送消息
            url = f'https://{base_url}/open-apis/bot/v2/hook/{key}'
            response = requests.post(url, json=message_data, timeout=15)
            response.raise_for_status()
            result = response.json()

            if result.get("StatusCode") == 0 or result.get("code") == 0:
                return True, "推送成功"
            else:
                return False, f"推送失败: {result}"

        except Exception as e:
            return False, f"飞书推送异常: {str(e)}"

    def _upload_image(self, image: MatLike, app_id: str, app_secret: str, base_url: str) -> str | None:
        """
        上传图片到飞书/Lark

        Args:
            image: 图片数据
            app_id: 自建应用ID
            app_secret: 自建应用Secret
            base_url: 基础域名

        Returns:
            str | None: 图片的image_key，失败返回None
        """
        try:
            # 获取tenant_access_token
            auth_endpoint = f"https://{base_url}/open-apis/auth/v3/tenant_access_token/internal"
            auth_headers = {
                "Content-Type": "application/json; charset=utf-8"
            }
            auth_response = requests.post(
                auth_endpoint,
                headers=auth_headers,
                json={
                    "app_id": app_id,
                    "app_secret": app_secret
                },
                timeout=15
            )
            auth_response.raise_for_status()
            tenant_access_token = auth_response.json()["tenant_access_token"]

            # 上传图片
            image_endpoint = f"https://{base_url}/open-apis/im/v1/images"
            image_headers = {
                "Authorization": f"Bearer {tenant_access_token}"
            }

            # 确保图片在开头
            image_bytes = self.image_to_bytes(image)
            image_bytes.seek(0)

            files = {
                'image': ('image.jpg', image_bytes.getvalue(), 'image/jpeg'),
                'image_type': (None, 'message')
            }

            image_response = requests.post(
                image_endpoint,
                headers=image_headers,
                files=files,
                timeout=30
            )

            if image_response.status_code != 200:
                log.error(f"飞书图片上传失败 status_code={image_response.status_code}")
                return None

            response_json = image_response.json()
            if response_json.get('code', 1) != 0:
                log.error(f"飞书图片上传失败 {response_json}")
                return None

            image_key = response_json.get('data', {}).get('image_key')
            if image_key is None:
                log.error(f"飞书图片上传失败 无法获取image_key {response_json}")
                return None

            return image_key

        except Exception:
            log.error("飞书图片上传异常", exc_info=True)
            return None

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证飞书配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        key = config.get('KEY', '')
        channel = config.get('CHANNEL', '')

        if len(key) == 0:
            return False, "密钥不能为空"

        if len(channel) == 0:
            return False, "服务类型不能为空"

        return True, "配置验证通过"