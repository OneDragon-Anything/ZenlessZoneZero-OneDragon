"""
Chronocat 推送渠道

提供通过 Chronocat 发送 QQ 个人和群消息的功能，支持多用户和多群组推送。
"""

import json
import re
from typing import List

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class Chronocat(PushChannel):
    """Chronocat 推送渠道实现类"""

    def __init__(self) -> None:
        """初始化 Chronocat 推送渠道配置"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="URL",
                title="服务地址",
                icon="SEND",
                field_type=FieldTypeEnum.TEXT,
                placeholder="http://127.0.0.1:16530",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="TOKEN",
                title="访问令牌",
                icon="VPN",
                field_type=FieldTypeEnum.TEXT,
                placeholder="填写在CHRONOCAT文件生成的访问密钥",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="QQ",
                title="QQ 配置",
                icon="MESSAGE",
                field_type=FieldTypeEnum.TEXT,
                placeholder="user_id=xxx;group_id=yyy;group_id=zzz",
                required=True
            )
        ]

        PushChannel.__init__(
            self,
            channel_id='CHRONOCAT',
            channel_name='Chronocat',
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
        推送消息到 Chronocat

        Args:
            config: 配置字典，包含 URL、TOKEN、QQ
            title: 消息标题
            content: 消息内容
            image: 图片数据（暂不支持）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            url = config.get('URL', '')
            token = config.get('TOKEN', '')
            qq_config = config.get('QQ', '')

            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            # 解析用户ID和群ID
            user_ids = self._extract_user_ids(qq_config)
            group_ids = self._extract_group_ids(qq_config)

            if not user_ids and not group_ids:
                return False, "未找到有效的用户ID或群ID配置"

            # 构建请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f'Bearer {token}',
            }

            api_url = f'{url}/api/message/send'
            message_content = f"{title}\n{content}"
            success_count = 0
            total_count = 0

            # 发送个人消息 (chatType=1)
            for user_id in user_ids:
                total_count += 1
                data = {
                    "peer": {"chatType": 1, "peerUin": user_id},
                    "elements": [
                        {
                            "elementType": 1,
                            "textElement": {"content": message_content},
                        }
                    ],
                }

                if self._send_message(api_url, headers, data):
                    success_count += 1
                    log.info(f"Chronocat QQ个人消息:{user_id} 推送成功")
                else:
                    log.error(f"Chronocat QQ个人消息:{user_id} 推送失败")

            # 发送群消息 (chatType=2)
            for group_id in group_ids:
                total_count += 1
                data = {
                    "peer": {"chatType": 2, "peerUin": group_id},
                    "elements": [
                        {
                            "elementType": 1,
                            "textElement": {"content": message_content},
                        }
                    ],
                }

                if self._send_message(api_url, headers, data):
                    success_count += 1
                    log.info(f"Chronocat QQ群消息:{group_id} 推送成功")
                else:
                    log.error(f"Chronocat QQ群消息:{group_id} 推送失败")

            if success_count == 0:
                return False, "所有消息推送失败"
            elif success_count < total_count:
                return True, f"部分推送成功 ({success_count}/{total_count})"
            else:
                return True, "推送成功"

        except Exception as e:
            log.error("Chronocat 推送异常", exc_info=True)
            return False, f"Chronocat 推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证 Chronocat 配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        url = config.get('URL', '')
        token = config.get('TOKEN', '')
        qq_config = config.get('QQ', '')

        if len(url) == 0:
            return False, "服务地址不能为空"

        if len(token) == 0:
            return False, "访问令牌不能为空"

        if len(qq_config) == 0:
            return False, "QQ 配置不能为空"

        # 验证 QQ 配置格式
        user_ids = self._extract_user_ids(qq_config)
        group_ids = self._extract_group_ids(qq_config)

        if not user_ids and not group_ids:
            return False, "QQ 配置格式错误，需要包含 user_id 或 group_id"

        return True, "配置验证通过"

    def _extract_user_ids(self, qq_config: str) -> List[str]:
        """
        从 QQ 配置中提取用户 ID

        Args:
            qq_config: QQ 配置字符串

        Returns:
            List[str]: 用户 ID 列表
        """
        return re.findall(r"user_id=(\d+)", qq_config)

    def _extract_group_ids(self, qq_config: str) -> List[str]:
        """
        从 QQ 配置中提取群 ID

        Args:
            qq_config: QQ 配置字符串

        Returns:
            List[str]: 群 ID 列表
        """
        return re.findall(r"group_id=(\d+)", qq_config)

    def _send_message(self, url: str, headers: dict[str, str], data: dict) -> bool:
        """
        发送单条消息

        Args:
            url: API 地址
            headers: 请求头
            data: 请求数据

        Returns:
            bool: 是否发送成功
        """
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=15)
            return response.status_code == 200
        except Exception:
            log.error("Chronocat 推送异常", exc_info=True)
            return False