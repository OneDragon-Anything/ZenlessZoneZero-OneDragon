import json
import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum


class PushPlus(PushChannel):

    def __init__(self):
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
                var_suffix="USER",
                title="群组编码",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入群组编码"
            ),
            PushChannelConfigField(
                var_suffix="TEMPLATE",
                title="发送模板",
                icon="CLOUD",
                field_type=FieldTypeEnum.COMBO,
                options=["", "html", "txt", "json", "markdown", "cloudMonitor", "jenkins", "route"],
                default="html"
            ),
            PushChannelConfigField(
                var_suffix="CHANNEL",
                title="发送渠道",
                icon="CLOUD",
                field_type=FieldTypeEnum.COMBO,
                options=["", "wechat", "webhook", "cp", "mail", "sms"],
                default="wechat"
            ),
            PushChannelConfigField(
                var_suffix="TO",
                title="好友令牌或用户ID",
                icon="CLOUD",
                field_type=FieldTypeEnum.TEXT,
                placeholder="微信公众号：好友令牌；企业微信：用户ID"
            ),
            PushChannelConfigField(
                var_suffix="WEBHOOK",
                title="Webhook 编码",
                icon="CLOUD",
                field_type=FieldTypeEnum.TEXT,
                placeholder="可在公众号上扩展配置出更多渠道"
            ),
            PushChannelConfigField(
                var_suffix="CALLBACKURL",
                title="发送结果回调地址",
                icon="SEND",
                field_type=FieldTypeEnum.TEXT,
                placeholder="会把推送最终结果通知到这个地址上"
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='PUSH_PLUS',
            channel_name='PushPlus',
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
        推送消息到 PushPlus

        Args:
            config: 配置字典，包含各种PushPlus配置项
            title: 消息标题
            content: 消息内容
            image: 图片数据（PushPlus暂不支持图片推送）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            token = config.get('TOKEN', '')

            if len(token) == 0:
                return False, "TOKEN 不能为空"

            url = "https://www.pushplus.plus/send"

            # 构建请求数据
            data = {
                "token": token,
                "title": title,
                "content": content,
                "topic": config.get('USER'),
                "template": config.get('TEMPLATE'),
                "channel": config.get('CHANNEL'),
                "webhook": config.get('WEBHOOK'),
                "callbackUrl": config.get('CALLBACKURL'),
                "to": config.get('TO'),
            }

            # 发送请求
            headers = {"Content-Type": "application/json"}
            response = requests.post(url=url, json=data, headers=headers, timeout=15).json()

            code = response.get("code")
            if code == 200:
                return True, f"推送请求成功，流水号: {response.get('data', '')}"
            elif code in [900, 903, 905, 999]:
                return True, response.get("msg", "推送成功")
            else:
                # 尝试备用地址
                url_old = "http://pushplus.hxtrip.com/send"
                headers["Accept"] = "application/json"
                response_old = requests.post(url=url_old, json=data, headers=headers, timeout=15).json()

                if response_old.get("code") == 200:
                    return True, "PushPlus(hxtrip) 推送成功！"
                else:
                    return False, f"PushPlus推送失败: {response_old.get('msg', '未知错误')}"

        except Exception as e:
            return False, f"PushPlus推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 PushPlus 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        token = config.get('TOKEN', '')

        if len(token) == 0:
            return False, "TOKEN 不能为空"

        return True, "配置验证通过"