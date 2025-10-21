"""
Discord 机器人推送渠道

提供通过 Discord 机器人发送文本和图片消息的功能，支持私聊推送。
"""

import json

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class Discord(PushChannel):
    """Discord 机器人推送渠道实现类"""

    def __init__(self) -> None:
        """初始化 Discord 推送渠道配置"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="API_HOST",
                title="API 地址",
                icon="SEND",
                field_type=FieldTypeEnum.TEXT,
                placeholder="Discord API 地址 (默认使用官方地址)",
                required=True,
                default='https://discord.com/api/v9',
            ),
            PushChannelConfigField(
                var_suffix="BOT_TOKEN",
                title="机器人 Token",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 Discord 机器人的 Token",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="USER_ID",
                title="用户 ID",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入要接收私信的用户 ID",
                required=True
            ),
        ]

        PushChannel.__init__(
            self,
            channel_id='DISCORD',
            channel_name='Discord 机器人',
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
        推送消息到 Discord 机器人

        Args:
            config: 配置字典，包含 BOT_TOKEN、USER_ID、API_HOST
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
            api_host = config.get('API_HOST', 'https://discord.com/api/v9')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # 配置代理
            proxies = self.get_proxy(proxy_url)

            headers = {
                "Authorization": f"Bot {bot_token}",
                "User-Agent": "OneDragon"
            }

            # 创建私聊频道
            create_dm_url = f"{api_host}/users/@me/channels"
            dm_headers = headers.copy()
            dm_headers["Content-Type"] = "application/json"
            dm_payload = json.dumps({"recipient_id": user_id})

            response = requests.post(
                create_dm_url,
                headers=dm_headers,
                data=dm_payload,
                proxies=proxies,
                timeout=15,
            )
            response.raise_for_status()

            channel_data = response.json()
            channel_id = channel_data.get("id")
            if not channel_id:
                return False, "Discord 私聊频道建立失败"

            # 发送消息
            message_url = f"{api_host}/channels/{channel_id}/messages"
            message_payload = {"content": f"{title}\n{content}"}

            files = None
            if image is not None:
                image_data = self.image_to_bytes(image)
                if image_data is not None:
                    image_data.seek(0)
                    files = {'file': ('image.png', image_data, 'image/png')}
                    data = {'payload_json': json.dumps(message_payload)}
                    if "Content-Type" in headers:
                        del headers["Content-Type"]
                else:
                    data = json.dumps(message_payload)
                    headers["Content-Type"] = "application/json"
            else:
                data = json.dumps(message_payload)
                headers["Content-Type"] = "application/json"

            response = requests.post(message_url, headers=headers, data=data, files=files, timeout=30)
            response.raise_for_status()

            return True, "推送成功"

        except Exception as e:
            log.error("Discord 推送异常", exc_info=True)
            return False, f"Discord 推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 Discord 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        bot_token = config.get('BOT_TOKEN', '')
        user_id = config.get('USER_ID', '')

        if len(bot_token) == 0:
            return False, "机器人 Token 不能为空"

        if len(user_id) == 0:
            return False, "用户 ID 不能为空"

        return True, "配置验证通过"