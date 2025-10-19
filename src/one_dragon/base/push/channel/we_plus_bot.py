"""
微加机器人推送渠道

提供通过微加机器人服务发送消息的功能，支持自动模板选择。
"""

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class WePlusBot(PushChannel):
    """微加机器人推送渠道实现类"""

    def __init__(self) -> None:
        """初始化微加机器人推送渠道配置"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="TOKEN",
                title="用户令牌",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入用户令牌",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="RECEIVER",
                title="消息接收者",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入消息接收者",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="VERSION",
                title="调用版本",
                icon="CLOUD",
                field_type=FieldTypeEnum.TEXT,
                placeholder="可选",
                required=False
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='WE_PLUS_BOT',
            channel_name='微加机器人',
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
        推送消息到微加机器人

        Args:
            config: 配置字典，包含 TOKEN、RECEIVER、VERSION
            title: 消息标题
            content: 消息内容
            image: 图片数据（暂不支持）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            token = config.get('TOKEN', '')
            receiver = config.get('RECEIVER', '')
            version = config.get('VERSION', '')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # 根据内容长度自动选择模板
            template = "txt"
            if len(content) > 800:
                template = "html"

            # 构建请求数据
            data = {
                "token": token,
                "title": title,
                "content": content,
                "template": template,
                "receiver": receiver,
                "version": version,
            }

            # 发送请求
            url = "https://www.weplusbot.com/send"
            headers = {"Content-Type": "application/json"}
            response = requests.post(url=url, json=data, headers=headers, timeout=15)
            response.raise_for_status()
            response_json = response.json()

            # 检查响应结果
            if response_json.get("code") == 200:
                return True, "推送成功"
            else:
                return False, "推送失败"

        except Exception as e:
            log.error("微加机器人 推送异常", exc_info=True)
            return False, f"微加机器人推送异常：{str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证微加机器人配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        token = config.get('TOKEN', '')
        receiver = config.get('RECEIVER', '')

        if len(token) == 0:
            return False, "用户令牌不能为空"

        if len(receiver) == 0:
            return False, "消息接收者不能为空"

        return True, "配置验证通过"