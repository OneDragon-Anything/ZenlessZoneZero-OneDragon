import json
from typing import Any

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class Telegram(PushChannel):

    def __init__(self):
        config_schema = [
            PushChannelConfigField(
                var_suffix="BOT_TOKEN",
                title="BOT_TOKEN",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="1234567890:AAAAAA-BBBBBBBBBBBBBBBBBBBBBBBBBBB",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="USER_ID",
                title="用户 ID",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="1234567890",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="API_HOST",
                title="API_HOST",
                icon="CLOUD",
                field_type=FieldTypeEnum.TEXT,
                placeholder="可选"
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='TG',
            channel_name='Telegram',
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
        推送消息到 Telegram 机器人

        Args:
            config: 配置字典，包含 BOT_TOKEN、USER_ID
            title: 消息标题
            content: 消息内容
            image: 图片数据（可选）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            bot_token = config.get('BOT_TOKEN', '')
            user_id = config.get('USER_ID', '')
            api_host = config.get('API_HOST', '')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # 配置代理
            proxies = self.get_proxy(proxy_url)

            # 设置 API 地址
            if api_host:
                url = f"{api_host}/bot{bot_token}/sendMessage"
                photo_url = f"{api_host}/bot{bot_token}/sendPhoto"
            else:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                photo_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

            try:
                if image is not None:
                    # 发送图片
                    image_bytes = self.image_to_bytes(image)
                    if image_bytes is None:
                        return False, "图片处理失败"

                    image_bytes.seek(0)
                    files = {
                        'photo': ('image.jpg', image_bytes.getvalue(), 'image/jpeg'),
                        'chat_id': (None, str(user_id)),
                        'caption': (None, f"{title}\n{content}")
                    }
                    response = requests.post(photo_url, files=files, proxies=proxies, timeout=30)
                else:
                    # 发送消息
                    headers = {"Content-Type": "application/x-www-form-urlencoded"}
                    payload = {
                        "chat_id": str(user_id),
                        "text": f"{title}\n{content}",
                    }
                    response = requests.post(url, data=payload, proxies=proxies, timeout=15)

                response.raise_for_status()
                result = response.json()

                if result.get("ok"):
                    return True, "推送成功"
                else:
                    error_msg = f"Telegram 推送失败: {result.get('description', '未知错误')}"
                    log.error(error_msg)
                    return False, error_msg

            except requests.RequestException as e:
                error_msg = f"Telegram 请求异常: {str(e)}"
                log.error(error_msg)
                return False, error_msg
            except Exception as e:
                error_msg = f"Telegram 推送异常: {str(e)}"
                log.error(error_msg)
                return False, error_msg

        except Exception as e:
            return False, f"Telegram 推送系统异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 Telegram 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        bot_token = config.get('BOT_TOKEN', '')
        user_id = config.get('USER_ID', '')

        if len(bot_token) == 0:
            return False, "BOT_TOKEN 不能为空"

        if len(user_id) == 0:
            return False, "USER_ID 不能为空"

        return True, "配置验证通过"