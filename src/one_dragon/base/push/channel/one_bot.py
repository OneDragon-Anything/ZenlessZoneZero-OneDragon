import json
from typing import Any

import requests
from cv2.typing import MatLike

from one_dragon.base.operation.notify_pool import NotifyPoolItem
from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import (
    FieldTypeEnum,
    PushChannelConfigField,
)
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

    # QQ 合并转发 payload 上限约 18KB（节点数 × 开销 + 总文本字符数）
    _FORWARD_PAYLOAD_LIMIT: int = 16000  # 留 2KB 余量
    _TEXT_NODE_OVERHEAD: int = 17
    _IMAGE_NODE_OVERHEAD: int = 55  # 图片节点额外协议开销

    def _split_into_batches(
        self, nodes: list[dict], texts: list[str], has_images: list[bool]
    ) -> list[list[dict]]:
        """按 payload 上限将节点列表拆分为多个批次"""
        batches: list[list[dict]] = []
        batch: list[dict] = []
        payload = 0
        for node, text, has_img in zip(nodes, texts, has_images, strict=False):
            overhead = self._IMAGE_NODE_OVERHEAD if has_img else self._TEXT_NODE_OVERHEAD
            cost = overhead + len(text.encode('utf-8'))
            if batch and payload + cost > self._FORWARD_PAYLOAD_LIMIT:
                batches.append(batch)
                batch = []
                payload = 0
            batch.append(node)
            payload += cost
        if batch:
            batches.append(batch)
        return batches

    def _send_forward(
        self,
        url: str,
        data: dict,
        headers: dict[str, str],
        label: str,
    ) -> tuple[bool, str]:
        """发送单批合并转发请求"""
        try:
            resp = requests.post(url, data=json.dumps(data), headers=headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            if result.get('status') == 'ok':
                log.info(f'OneBot {label}成功！')
                return True, ''
            msg = f'OneBot {label}失败: {result}'
            log.error(msg)
            return False, msg
        except Exception as e:
            msg = f'OneBot {label}异常: {str(e)}'
            log.error(msg)
            return False, msg

    def push_merged(
        self,
        config: dict[str, str],
        title: str,
        items: list[NotifyPoolItem],
        proxy_url: str | None = None,
    ) -> tuple[bool, str]:
        """
        使用 OneBot 合并转发 API 推送合并消息。
        当消息量超过 QQ 单次合并上限时自动分批发送。
        """
        try:
            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            base_url = config.get('URL', '').rstrip('/')
            if base_url.endswith('/send_msg'):
                base_url = base_url[:-len('/send_msg')]

            user_id = config.get('USER', '')
            group_id = config.get('GROUP', '')
            token = config.get('TOKEN', '')

            headers = {'Content-Type': 'application/json'}
            if token and len(token) > 0:
                headers['Authorization'] = f'Bearer {token}'

            # 构建合并转发节点并记录每条文本和图片标记（用于拆批计算）
            nodes: list[dict] = []
            texts: list[str] = []
            has_images: list[bool] = []
            for item in items:
                msg_content: list[dict] = [{'type': 'text', 'data': {'text': item.content}}]
                has_img = False
                if item.image is not None:
                    image_base64 = self.image_to_base64(item.image)
                    if image_base64 is not None:
                        msg_content.append({'type': 'image', 'data': {'file': f'base64://{image_base64}'}})
                        has_img = True
                nodes.append({
                    'type': 'node',
                    'data': {
                        'name': title,
                        'uin': user_id or '10086',
                        'content': msg_content,
                    }
                })
                texts.append(item.content)
                has_images.append(has_img)

            batches = self._split_into_batches(nodes, texts, has_images)
            success_count = 0
            error_messages: list[str] = []

            for batch_idx, batch in enumerate(batches):
                suffix = f'(批次 {batch_idx + 1}/{len(batches)})' if len(batches) > 1 else ''

                if user_id and len(user_id) > 0:
                    ok, msg = self._send_forward(
                        base_url + '/send_private_forward_msg',
                        {'user_id': user_id, 'messages': batch},
                        headers,
                        f'私聊合并转发{suffix}',
                    )
                    if ok:
                        success_count += 1
                    else:
                        error_messages.append(msg)

                if group_id and len(group_id) > 0:
                    ok, msg = self._send_forward(
                        base_url + '/send_group_forward_msg',
                        {'group_id': group_id, 'messages': batch},
                        headers,
                        f'群聊合并转发{suffix}',
                    )
                    if ok:
                        success_count += 1
                    else:
                        error_messages.append(msg)

            if success_count > 0:
                if len(error_messages) > 0:
                    return True, f"部分推送成功: {'; '.join(error_messages)}"
                return True, '合并转发成功'
            return False, f"推送失败: {'; '.join(error_messages)}" if error_messages else '未配置有效的接收者'

        except Exception as e:
            return False, f'OneBot 合并转发异常: {str(e)}'
