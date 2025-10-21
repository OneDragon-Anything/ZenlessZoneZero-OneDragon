"""
iGot 推送渠道

提供通过 iGot 服务发送消息的功能。
"""

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class IGot(PushChannel):
    """iGot 推送渠道实现类"""

    def __init__(self) -> None:
        """初始化 iGot 推送渠道配置"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="PUSH_KEY",
                title="推送 Key",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 iGot 的 推送 Key",
                required=True
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='IGOT',
            channel_name='iGot',
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
        推送消息到 iGot

        Args:
            config: 配置字典，包含 PUSH_KEY
            title: 消息标题
            content: 消息内容
            image: 图片数据（暂不支持）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            push_key = config.get('PUSH_KEY', '')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # 构建请求URL和数据
            url = f'https://push.hellyw.com/{push_key}'
            data = {"title": title, "content": content}
            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            # 发送请求
            response = requests.post(url, data=data, headers=headers, timeout=15)
            response.raise_for_status()
            response_json = response.json()

            # 检查响应结果
            if response_json.get("ret") == 0:
                return True, "推送成功"
            else:
                error_msg = response_json.get("errMsg", "未知错误")
                return False, f"推送失败：{error_msg}"

        except Exception as e:
            log.error("iGot 推送异常", exc_info=True)
            return False, f"iGot 推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 iGot 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        push_key = config.get('PUSH_KEY', '')

        if len(push_key) == 0:
            return False, "推送 Key 不能为空"

        return True, "配置验证通过"