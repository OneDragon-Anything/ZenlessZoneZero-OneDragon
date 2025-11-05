import json
from typing import Any

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class Gotify(PushChannel):

    def __init__(self):
        config_schema = [
            PushChannelConfigField(
                var_suffix="URL",
                title="Gotify 地址",
                icon="SEND",
                field_type=FieldTypeEnum.TEXT,
                placeholder="https://push.example.de:8080",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="TOKEN",
                title="App Token",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="Gotify 的 App Token",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="PRIORITY",
                title="消息优先级",
                icon="CLOUD",
                field_type=FieldTypeEnum.COMBO,
                options=["", "0", "1", "2", "3", "4", "5"],
                default="5"
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='GOTIFY',
            channel_name='GOTIFY',
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
        推送消息到 Gotify

        Args:
            config: 配置字典，包含 URL、TOKEN、PRIORITY
            title: 消息标题
            content: 消息内容
            image: 图片数据（Gotify 暂不支持图片推送）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            url = config.get('URL', '')
            token = config.get('TOKEN', '')
            priority = config.get('PRIORITY', '5')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # Gotify 目前不支持图片推送，忽略图片参数
            if image is not None:
                log.info("Gotify 暂不支持图片推送，仅发送文本消息")

            # 构建请求数据
            data = {
                "title": title,
                "message": content,
                "priority": int(priority) if priority.isdigit() else 5
            }

            # 构建完整URL
            full_url = f"{url}/message?token={token}"

            try:
                response = requests.post(full_url, data=data, timeout=15)
                response.raise_for_status()
                result = response.json()

                if result.get("id"):
                    log.info("gotify 推送成功！")
                    return True, "推送成功"
                else:
                    error_msg = f"gotify 推送失败！"
                    log.error(error_msg)
                    return False, error_msg

            except requests.RequestException as e:
                error_msg = f"gotify 请求异常: {str(e)}"
                log.error(error_msg)
                return False, error_msg
            except Exception as e:
                error_msg = f"gotify 推送异常: {str(e)}"
                log.error(error_msg)
                return False, error_msg

        except Exception as e:
            return False, f"gotify 推送系统异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 Gotify 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        url = config.get('URL', '')
        token = config.get('TOKEN', '')

        if len(url) == 0:
            return False, "Gotify 地址不能为空"

        if len(token) == 0:
            return False, "App Token 不能为空"

        return True, "配置验证通过"