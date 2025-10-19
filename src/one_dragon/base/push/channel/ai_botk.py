import json

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum


class AiBotK(PushChannel):
    """智能微秘书推送渠道"""

    def __init__(self):
        """初始化智能微秘书推送渠道"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="KEY",
                title="APIKEY",
                icon="MESSAGE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入个人中心的 APIKEY",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="TYPE",
                title="目标类型",
                icon="PEOPLE",
                field_type=FieldTypeEnum.COMBO,
                options=["room", "contact"],
                default="contact",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="NAME",
                title="目标名称",
                icon="CLOUD",
                field_type=FieldTypeEnum.TEXT,
                placeholder="发送群名或者好友昵称，和 type 要对应",
                required=True
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='AIBOTK',
            channel_name='智能微秘书',
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
        推送消息到智能微秘书

        Args:
            config: 配置字典，包含 KEY、TYPE 和 NAME
            title: 消息标题
            content: 消息内容
            image: 图片数据（智能微秘书暂不支持图片推送）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            # 验证配置
            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            api_key = config.get('KEY', '')
            target_type = config.get('TYPE', 'contact')
            target_name = config.get('NAME', '')

            # 根据目标类型选择不同的API端点
            if target_type == "room":
                url = "https://api-bot.aibotk.com/openapi/v1/chat/room"
                data = {
                    "apiKey": api_key,
                    "roomName": target_name,
                    "message": {"type": 1, "content": f"{title}\n{content}"},
                }
            else:  # contact
                url = "https://api-bot.aibotk.com/openapi/v1/chat/contact"
                data = {
                    "apiKey": api_key,
                    "name": target_name,
                    "message": {"type": 1, "content": f"{title}\n{content}"},
                }

            # 发送请求
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, data=json.dumps(data).encode("utf-8"), headers=headers, timeout=15)

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    return True, "推送成功"
                else:
                    return False, f"智能微秘书推送失败: {result.get('error', '未知错误')}"
            else:
                return False, f"HTTP请求失败，状态码: {response.status_code}"

        except requests.RequestException as e:
            return False, f"网络请求异常: {str(e)}"
        except Exception as e:
            return False, f"智能微秘书推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证智能微秘书配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        api_key = config.get('KEY', '')
        target_type = config.get('TYPE', '')
        target_name = config.get('NAME', '')

        if not api_key.strip():
            return False, "APIKEY不能为空"

        if not target_type.strip():
            return False, "目标类型不能为空"

        if target_type not in ["room", "contact"]:
            return False, "目标类型必须是 room 或 contact"

        if not target_name.strip():
            return False, "目标名称不能为空"

        return True, "配置验证通过"