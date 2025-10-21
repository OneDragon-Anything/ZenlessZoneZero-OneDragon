import json
from typing import Any

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class OneBot(PushChannel):

    def __init__(self):
        config_schema = [
            PushChannelConfigField(
                var_suffix="URL",
                title="请求地址",
                icon="SEND",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入请求地址",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="USER",
                title="QQ 号",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入目标 QQ 号"
            ),
            PushChannelConfigField(
                var_suffix="GROUP",
                title="群号",
                icon="PEOPLE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入目标群号"
            ),
            PushChannelConfigField(
                var_suffix="TOKEN",
                title="Token",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 OneBot 的 Token"
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='ONEBOT',
            channel_name='OneBot',
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
        推送消息到 OneBot

        Args:
            config: 配置字典，包含 URL、USER、GROUP、TOKEN
            title: 消息标题
            content: 消息内容
            image: 图片数据（可选）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            url = config.get('URL', '')
            user_id = config.get('USER', '')
            group_id = config.get('GROUP', '')
            token = config.get('TOKEN', '')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            if url:
                url = url.rstrip("/")
                url += "" if url.endswith("/send_msg") else "/send_msg"

            headers = {'Content-Type': "application/json"}
            message = [{"type": "text", "data": {"text": f"{title}\n{content}"}}]

            if image is not None:
                image_base64 = self.image_to_base64(image)
                if image_base64 is not None:
                    message.append({"type": "image", "data": {"file": f'base64://{image_base64}'}})

            data_private: dict[str, Any] = {"message": message}
            data_group: dict[str, Any] = {"message": message}

            if token and len(token) > 0:
                headers["Authorization"] = f"Bearer {token}"

            success_count = 0
            error_messages = []

            # 发送私聊消息
            if user_id and len(user_id) > 0:
                data_private["message_type"] = "private"
                data_private["user_id"] = user_id
                try:
                    response_private = requests.post(url, data=json.dumps(data_private), headers=headers, timeout=15)
                    response_private.raise_for_status()
                    result_private = response_private.json()

                    if result_private.get("status") == "ok":
                        success_count += 1
                        log.info("OneBot 私聊推送成功！")
                    else:
                        error_msg = f"OneBot 私聊推送失败: {result_private}"
                        error_messages.append(error_msg)
                        log.error(error_msg)
                except Exception as e:
                    error_msg = f"OneBot 私聊推送异常: {str(e)}"
                    error_messages.append(error_msg)
                    log.error(error_msg)

            # 发送群聊消息
            if group_id and len(group_id) > 0:
                data_group["message_type"] = "group"
                data_group["group_id"] = group_id
                try:
                    response_group = requests.post(url, data=json.dumps(data_group), headers=headers, timeout=15)
                    response_group.raise_for_status()
                    result_group = response_group.json()

                    if result_group.get("status") == "ok":
                        success_count += 1
                        log.info("OneBot 群聊推送成功！")
                    else:
                        error_msg = f"OneBot 群聊推送失败: {result_group}"
                        error_messages.append(error_msg)
                        log.error(error_msg)
                except Exception as e:
                    error_msg = f"OneBot 群聊推送异常: {str(e)}"
                    error_messages.append(error_msg)
                    log.error(error_msg)

            if success_count > 0:
                if len(error_messages) > 0:
                    return True, f"部分推送成功: {'; '.join(error_messages)}"
                else:
                    return True, "推送成功"
            else:
                return False, f"推送失败: {'; '.join(error_messages)}" if error_messages else "未配置有效的接收者"

        except Exception as e:
            return False, f"OneBot 推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 OneBot 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        url = config.get('URL', '')
        user_id = config.get('USER', '')
        group_id = config.get('GROUP', '')

        if len(url) == 0:
            return False, "请求地址不能为空"

        if len(user_id) == 0 and len(group_id) == 0:
            return False, "QQ 号和群号至少需要配置一个"

        return True, "配置验证通过"