import json
import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum


class Bark(PushChannel):

    def __init__(self):
        config_schema = [
            PushChannelConfigField(
                var_suffix="PUSH",
                title="推送地址或 Key",
                icon="SEND",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 Bark 推送地址或 Key",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="DEVICE_KEY",
                title="设备码",
                icon="PHONE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请填写设备码"
            ),
            PushChannelConfigField(
                var_suffix="ARCHIVE",
                title="推送是否存档",
                icon="FOLDER",
                field_type=FieldTypeEnum.COMBO,
                options=["", "1", "0"],
                default="0"
            ),
            PushChannelConfigField(
                var_suffix="GROUP",
                title="推送分组",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请填写推送分组"
            ),
            PushChannelConfigField(
                var_suffix="SOUND",
                title="推送铃声",
                icon="HEADPHONE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请填写铃声名称"
            ),
            PushChannelConfigField(
                var_suffix="ICON",
                title="推送图标",
                icon="PHOTO",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请填写图标的URL"
            ),
            PushChannelConfigField(
                var_suffix="LEVEL",
                title="推送中断级别",
                icon="DATE_TIME",
                field_type=FieldTypeEnum.COMBO,
                options=["", "critical", "active", "timeSensitive", "passive"],
                default="active"
            ),
            PushChannelConfigField(
                var_suffix="URL",
                title="推送跳转URL",
                icon="LINK",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请填写推送跳转URL"
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='BARK',
            channel_name='Bark',
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
        推送消息到 Bark

        Args:
            config: 配置字典，包含各种Bark配置项
            title: 消息标题
            content: 消息内容
            image: 图片数据（Bark暂不支持图片推送）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            bark_push = config.get('PUSH', '')

            if len(bark_push) == 0:
                return False, "PUSH 不能为空"

            # 根据输入判断是完整URL还是Key
            if bark_push.startswith("http"):
                url = bark_push
            else:
                url = f'https://api.day.app/{bark_push}'

            # 构建基础数据
            data = {
                "title": title,
                "body": content,
            }

            # 添加可选参数
            archive = config.get('ARCHIVE')
            if archive:
                data["isArchive"] = archive

            group = config.get('GROUP')
            if group:
                data["group"] = group

            sound = config.get('SOUND')
            if sound:
                data["sound"] = sound

            icon = config.get('ICON')
            if icon:
                data["icon"] = icon

            level = config.get('LEVEL')
            if level:
                data["level"] = level

            url_param = config.get('URL')
            if url_param:
                data["url"] = url_param

            # 发送请求
            headers = {"Content-Type": "application/json;charset=utf-8"}
            response = requests.post(
                url=url,
                data=json.dumps(data),
                headers=headers,
                timeout=15
            ).json()

            if response.get("code") == 200:
                return True, "推送成功"
            else:
                return False, f"Bark推送失败: {response.get('message', '未知错误')}"

        except Exception as e:
            return False, f"Bark推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 Bark 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        bark_push = config.get('PUSH', '')

        if len(bark_push) == 0:
            return False, "PUSH 不能为空"

        return True, "配置验证通过"