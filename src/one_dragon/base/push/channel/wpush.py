import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import (
    FieldTypeEnum,
    PushChannelConfigField,
)


class WPush(PushChannel):
    """WPUSH 多渠道消息推送。文档：https://wpush.cn/docs"""

    def __init__(self) -> None:
        """初始化 WPUSH 推送渠道与配置项。"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="APIKEY",
                title="API Key",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 WPUSH API Key（https://wpush.cn/settings）",
                required=True,
            ),
            PushChannelConfigField(
                var_suffix="CHANNEL",
                title="发送渠道",
                icon="CLOUD",
                field_type=FieldTypeEnum.COMBO,
                options=[
                    "",
                    "wechat",
                    "app",
                    "sms",
                    "mail",
                    "webhook",
                    "dingtalk",
                    "feishu",
                    "wechat_work",
                    "clawbot",
                    "qqbot",
                ],
                default="wechat",
            ),
            PushChannelConfigField(
                var_suffix="TOPIC_CODE",
                title="Topic 编码",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="可选，Topic 广播编码",
            ),
        ]

        PushChannel.__init__(
            self,
            channel_id="WPUSH",
            channel_name="WPUSH",
            config_schema=config_schema,
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
        推送消息到 WPUSH

        Args:
            config: 配置字典，包含 APIKEY / CHANNEL / TOPIC_CODE
            title: 消息标题
            content: 消息内容
            image: 图片数据（WPUSH 暂不支持图片推送）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            apikey = config.get("APIKEY", "")
            channel = config.get("CHANNEL") or "wechat"
            topic_code = config.get("TOPIC_CODE", "")

            data: dict[str, str] = {
                "apikey": apikey,
                "title": title,
                "content": content,
                "channel": channel,
            }
            if topic_code:
                data["topic_code"] = topic_code

            headers = {"Content-Type": "application/json"}
            proxies = self.get_proxy(proxy_url)
            response = requests.post(
                url="https://api.wpush.cn/api/v1/send",
                json=data,
                headers=headers,
                timeout=15,
                proxies=proxies,
                allow_redirects=False,
            )
            if not 200 <= response.status_code < 300:
                return False, f"WPUSH 请求失败: HTTP {response.status_code}"
            result = response.json()

            if result.get("code") == 0:
                return True, "WPUSH 推送成功"
            return False, f"WPUSH 推送失败: {result.get('message', result)}"

        except Exception as e:
            return False, f"WPUSH 推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 WPUSH 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        apikey = config.get("APIKEY", "")
        if len(apikey) == 0:
            return False, "APIKEY 不能为空"
        return True, "配置验证通过"
