"""
Synology Chat 推送渠道

提供通过 Synology Chat 服务发送消息的功能。
"""

import json

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class SynologyChat(PushChannel):
    """Synology Chat 推送渠道实现类"""

    def __init__(self) -> None:
        """初始化 Synology Chat 推送渠道配置"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="URL",
                title="URL",
                icon="SEND",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 Synology Chat 的 URL",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="TOKEN",
                title="Token",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 Synology Chat 的 Token",
                required=True
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='SYNOLOGY_CHAT',
            channel_name='Synology Chat',
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
        推送消息到 Synology Chat

        Args:
            config: 配置字典，包含 URL、TOKEN
            title: 消息标题
            content: 消息内容
            image: 图片数据（暂不支持）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            url = config.get('URL', '')
            token = config.get('TOKEN', '')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # 构建完整的请求URL
            full_url = url + token

            # 构建请求数据
            message_text = f"{title}\n{content}"
            payload_data = {"text": message_text}
            data = "payload=" + json.dumps(payload_data)

            # 发送请求
            response = requests.post(full_url, data=data, timeout=15)

            # 检查响应状态码
            if response.status_code == 200:
                return True, "推送成功"
            else:
                return False, f"推送失败，状态码：{response.status_code}"

        except Exception as e:
            log.error("Synology Chat 推送异常", exc_info=True)
            return False, f"Synology Chat 推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 Synology Chat 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        url = config.get('URL', '')
        token = config.get('TOKEN', '')

        if len(url) == 0:
            return False, "URL 不能为空"

        if len(token) == 0:
            return False, "Token 不能为空"

        return True, "配置验证通过"