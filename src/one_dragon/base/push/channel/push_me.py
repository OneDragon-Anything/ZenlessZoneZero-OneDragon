"""
PushMe 推送渠道

提供通过 PushMe 服务发送消息的功能，支持自定义服务地址。
"""

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class PushMe(PushChannel):
    """PushMe 推送渠道实现类"""

    def __init__(self) -> None:
        """初始化 PushMe 推送渠道配置"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="KEY",
                title="KEY",
                icon="MESSAGE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 PushMe 的 KEY",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="URL",
                title="URL",
                icon="SEND",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 PushMe 的 URL",
                required=False
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='PUSHME',
            channel_name='PushMe',
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
        推送消息到 PushMe

        Args:
            config: 配置字典，包含 KEY、URL
            title: 消息标题
            content: 消息内容
            image: 图片数据（暂不支持）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            push_key = config.get('KEY', '')
            custom_url = config.get('URL', '')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # 构建请求数据
            data = {
                "push_key": push_key,
                "title": title,
                "content": content,
                "date": config.get('date', ''),
                "type": config.get('type', ''),
            }

            # 使用自定义URL或默认官方地址
            url = custom_url if custom_url else "https://push.i-i.me/"

            # 发送请求
            response = requests.post(url, data=data, timeout=15)

            # 检查响应结果
            if response.status_code == 200 and response.text == "success":
                return True, "推送成功"
            else:
                return False, f"推送失败：状态码 {response.status_code}，响应 {response.text}"

        except Exception as e:
            log.error("PushMe 推送异常", exc_info=True)
            return False, f"PushMe 推送异常：{str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 PushMe 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        push_key = config.get('KEY', '')

        if len(push_key) == 0:
            return False, "KEY 不能为空"

        return True, "配置验证通过"