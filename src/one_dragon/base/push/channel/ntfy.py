import base64
import json
from typing import Any

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class Ntfy(PushChannel):

    def __init__(self):
        config_schema = [
            PushChannelConfigField(
                var_suffix="URL",
                title="URL",
                icon="SEND",
                field_type=FieldTypeEnum.TEXT,
                default="https://ntfy.sh",
                placeholder="ntfy服务器",
                required=True,
            ),
            PushChannelConfigField(
                var_suffix="TOPIC",
                title="TOPIC",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="ntfy 应用 Topic",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="PRIORITY",
                title="消息优先级",
                icon="CLOUD",
                field_type=FieldTypeEnum.COMBO,
                options=["1", "2", "3", "4", "5"],
                default="3"
            ),
            PushChannelConfigField(
                var_suffix="TOKEN",
                title="TOKEN",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="ntfy 应用 token"
            ),
            PushChannelConfigField(
                var_suffix="USERNAME",
                title="用户名称",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="ntfy 应用用户名"
            ),
            PushChannelConfigField(
                var_suffix="PASSWORD",
                title="用户密码",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="ntfy 应用密码"
            ),
            PushChannelConfigField(
                var_suffix="ACTIONS",
                title="用户动作",
                icon="APPLICATION",
                field_type=FieldTypeEnum.TEXT,
                placeholder="ntfy 用户动作，最多三个"
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='NTFY',
            channel_name='ntfy',
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
        推送消息到 ntfy

        Args:
            config: 配置字典，包含 URL、TOPIC、PRIORITY、TOKEN、USERNAME、PASSWORD、ACTIONS
            title: 消息标题
            content: 消息内容
            image: 图片数据（可选）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        url = config.get('URL', 'https://ntfy.sh')
        topic = config.get('TOPIC', '')
        priority = config.get('PRIORITY', '3')
        token = config.get('TOKEN', '')
        username = config.get('USERNAME', '')
        password = config.get('PASSWORD', '')
        actions = config.get('ACTIONS', '')

        ok, msg = self.validate_config(config)
        if not ok:
            return False, msg

        def encode_rfc2047(text: str) -> str:
            """将文本编码为符合 RFC 2047 标准的格式"""
            encoded_bytes = base64.b64encode(text.encode("utf-8"))
            encoded_str = encoded_bytes.decode("utf-8")
            return f"=?utf-8?B?{encoded_str}?="

        # 使用 RFC 2047 编码 title
        encoded_title = encode_rfc2047(title)

        data_list = []
        # 处理图片
        if image is not None:
            image_bytes = self.image_to_bytes(image)
            if image_bytes is None:
                return False, "图片处理失败"

            image_bytes.seek(0)
            data_list.append(image_bytes.getvalue())
        data_list.append(content.encode(encoding="utf-8"))

        # 构建请求头
        headers = {"Title": encoded_title, "Priority": priority}

        # 添加认证信息
        if token:
            headers['Authorization'] = "Bearer " + token
        elif username and password:
            auth_str = f"{username}:{password}"
            headers['Authorization'] = "Basic " + base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')

        # 添加用户动作
        if actions:
            headers['Actions'] = encode_rfc2047(actions)

        # 构建完整URL
        full_url = f"{url}/{topic}"

        success_cnt = 0
        try:
            for data in data_list:
                response = requests.post(full_url, data=data, headers=headers, timeout=15)
                response.raise_for_status()

                if response.status_code == 200:
                    success_cnt += 1
                else:
                    error_msg = f"Ntfy 推送失败！错误信息：{response.text}"
                    log.error(error_msg)

            if success_cnt == len(data_list):
                return True, "Ntfy 推送成功！"
            elif success_cnt > 0:
                return True, "部分 Ntfy 推送成功！"
            else:
                return False, "Ntfy 推送失败！"

        except Exception as e:
            error_msg = f"Ntfy 推送异常: {str(e)}"
            log.error(error_msg, exc_info=True)
            return False, error_msg


    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 ntfy 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        topic = config.get('TOPIC', '')

        if len(topic) == 0:
            return False, "TOPIC 不能为空"

        return True, "配置验证通过"