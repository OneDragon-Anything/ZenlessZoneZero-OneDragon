import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum


class ServerChan(PushChannel):

    def __init__(self):
        config_schema = [
            PushChannelConfigField(
                var_suffix="PUSH_KEY",
                title="PUSH_KEY",
                icon="MESSAGE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 Server酱 的 PUSH_KEY",
                required=True
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='SERVERCHAN',
            channel_name='Server酱',
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
        推送消息到 Server酱

        Args:
            config: 配置字典，包含 PUSH_KEY
            title: 消息标题
            content: 消息内容
            image: 图片数据（Server酱暂不支持图片推送）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            push_key = config.get('PUSH_KEY', '')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # Server酱 API 地址
            api_url = f"https://sctapi.ftqq.com/{push_key}.send"

            # 构建请求数据
            message_data = {
                "title": title,
                "desp": content
            }

            # 发送请求
            headers = {'Content-Type': 'application/json'}
            response = requests.post(api_url, json=message_data, headers=headers, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    return True, "推送成功"
                else:
                    return False, f"Server酱推送失败: {result.get('msg', '未知错误')}"
            else:
                return False, f"HTTP请求失败，状态码: {response.status_code}"

        except Exception as e:
            return False, f"Server酱推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 Server酱配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        push_key = config.get('PUSH_KEY', '')

        if len(push_key) == 0:
            return False, "PUSH_KEY 不能为空"

        return True, "配置验证通过"