"""
Qmsg 酱推送渠道

提供通过 Qmsg 酱服务发送消息的功能，支持个人消息和群消息。
"""

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class QMsg(PushChannel):
    """Qmsg 酱推送渠道实现类"""

    def __init__(self) -> None:
        """初始化 Qmsg 酱推送渠道配置"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="KEY",
                title="KEY",
                icon="MESSAGE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 Qmsg 酱的 KEY",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="TYPE",
                title="通知类型",
                icon="PEOPLE",
                field_type=FieldTypeEnum.COMBO,
                options=["send", "group"],
                default="send",
                required=True
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='QMSG',
            channel_name='Qmsg 酱',
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
        推送消息到 Qmsg 酱

        Args:
            config: 配置字典，包含 KEY、TYPE
            title: 消息标题
            content: 消息内容
            image: 图片数据（暂不支持）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            key = config.get('KEY', '')
            msg_type = config.get('TYPE', 'send')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # 构建请求URL
            url = f'https://qmsg.zendee.cn/{msg_type}/{key}'

            # 处理消息内容：替换 ---- 为 -，并合并标题和内容
            message_content = f"{title}\n{content}"
            message_content = message_content.replace("----", "-")
            payload = {"msg": message_content.encode("utf-8")}

            # 发送请求
            response = requests.post(url=url, params=payload, timeout=15)
            response.raise_for_status()
            response_json = response.json()

            # 检查响应结果
            if response_json.get("code") == 0:
                return True, "推送成功"
            else:
                reason = response_json.get("reason", "未知错误")
                return False, f"推送失败：{reason}"

        except Exception as e:
            log.error("Qmsg酱 推送异常", exc_info=True)
            return False, f"Qmsg 酱推送异常：{str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 Qmsg 酱配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        key = config.get('KEY', '')
        msg_type = config.get('TYPE', '')

        if len(key) == 0:
            return False, "KEY 不能为空"

        if len(msg_type) == 0:
            return False, "通知类型不能为空"

        if msg_type not in ["send", "group"]:
            return False, "通知类型必须是 send 或 group"

        return True, "配置验证通过"