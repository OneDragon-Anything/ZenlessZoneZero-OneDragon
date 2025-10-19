import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum


class WxPusher(PushChannel):
    """WxPusher推送渠道"""

    def __init__(self):
        """初始化WxPusher推送渠道"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="APP_TOKEN",
                title="appToken",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 appToken",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="TOPIC_IDS",
                title="TOPIC_IDs",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="多个用英文分号;分隔",
                required=False
            ),
            PushChannelConfigField(
                var_suffix="UIDS",
                title="UIDs",
                icon="CLOUD",
                field_type=FieldTypeEnum.TEXT,
                placeholder="二者至少配置其中之一",
                required=False
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='WXPUSHER',
            channel_name='WxPusher',
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
        推送消息到WxPusher

        Args:
            config: 配置字典，包含 APP_TOKEN、TOPIC_IDS 和 UIDS
            title: 消息标题
            content: 消息内容
            image: 图片数据（WxPusher暂不支持图片推送）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            # 验证配置
            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            app_token = config.get('APP_TOKEN', '')
            topic_ids_str = config.get('TOPIC_IDS', '')
            uids_str = config.get('UIDS', '')

            # 处理topic_ids和uids，将分号分隔的字符串转为数组
            topic_ids = []
            if topic_ids_str:
                topic_ids = [
                    int(id.strip())
                    for id in topic_ids_str.split(";")
                    if id.strip()
                ]

            uids = []
            if uids_str:
                uids = [
                    uid.strip()
                    for uid in uids_str.split(";")
                    if uid.strip()
                ]

            # topic_ids uids 至少有一个
            if not topic_ids and not uids:
                return False, "主题ID和用户ID至少需要配置其中之一"

            # 构建请求数据
            data = {
                "appToken": app_token,
                "content": f"<h1>{title}</h1><br/><div style='white-space: pre-wrap;'>{content}</div>",
                "summary": title,
                "contentType": 2,
                "topicIds": topic_ids,
                "uids": uids,
                "verifyPayType": 0,
            }

            # 发送请求
            url = "https://wxpusher.zjiecode.com/api/send/message"
            headers = {"Content-Type": "application/json"}
            response = requests.post(url=url, json=data, headers=headers, timeout=15)

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 1000:
                    return True, "推送成功"
                else:
                    return False, f"WxPusher推送失败: {result.get('msg', '未知错误')}"
            else:
                return False, f"HTTP请求失败，状态码: {response.status_code}"

        except requests.RequestException as e:
            return False, f"网络请求异常: {str(e)}"
        except Exception as e:
            return False, f"WxPusher推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证WxPusher配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        app_token = config.get('APP_TOKEN', '')
        topic_ids_str = config.get('TOPIC_IDS', '')
        uids_str = config.get('UIDS', '')

        if not app_token.strip():
            return False, "appToken不能为空"

        if not topic_ids_str.strip() and not uids_str.strip():
            return False, "主题ID和用户ID至少需要配置其中之一"

        # 验证主题ID格式（如果提供了）
        if topic_ids_str.strip():
            try:
                topic_ids = [
                    int(id.strip())
                    for id in topic_ids_str.split(";")
                    if id.strip()
                ]
                if not topic_ids:
                    return False, "主题ID格式不正确"
            except ValueError:
                return False, "主题ID必须为数字"

        return True, "配置验证通过"