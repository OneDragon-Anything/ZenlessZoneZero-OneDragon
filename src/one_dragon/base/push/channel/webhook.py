import base64
import datetime
import json
import time
import urllib.parse

import requests
from cv2.typing import MatLike

from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.log_utils import log


class Webhook(PushChannel):
    """通用Webhook推送渠道"""

    def __init__(self):
        """初始化通用Webhook推送渠道"""
        config_schema = [
            PushChannelConfigField(
                var_suffix="URL",
                title="URL",
                icon="LINK",
                field_type=FieldTypeEnum.TEXT,
                placeholder="请输入 Webhook URL",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="METHOD",
                title="HTTP 方法",
                icon="APPLICATION",
                field_type=FieldTypeEnum.COMBO,
                options=["POST", "GET", "PUT"],
                default="POST",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="CONTENT_TYPE",
                title="Content-Type",
                icon="CODE",
                field_type=FieldTypeEnum.COMBO,
                options=["application/json", "application/x-www-form-urlencoded", "application/xml", "text/plain"],
                default="application/json",
                required=True
            ),
            PushChannelConfigField(
                var_suffix="HEADERS",
                title="请求头 (Headers)",
                icon="LEFT_ARROW",
                field_type=FieldTypeEnum.KEY_VALUE,
            ),
            PushChannelConfigField(
                var_suffix="BODY",
                title="请求体 (Payload)",
                icon="DOCUMENT",
                field_type=FieldTypeEnum.CODE_EDITOR,
                language="json",
                placeholder="请输入请求体内容",
                required=True
            ),
        ]

        PushChannel.__init__(
            self,
            channel_id='WEBHOOK',
            channel_name='通用Webhook',
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
        推送消息到通用Webhook

        Args:
            config: 配置字典，包含 URL、METHOD、CONTENT_TYPE、HEADERS 和 BODY
            title: 消息标题
            content: 消息内容
            image: 图片数据（支持base64编码）
            proxy_url: 代理地址

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        try:
            # 验证配置
            ok, msg = self.validate_config(config)
            if not ok:
                return False, msg

            url = config.get('URL', '')
            method = config.get('METHOD', 'POST')
            content_type = config.get('CONTENT_TYPE', 'application/json')
            headers_str = config.get('HEADERS', '{}')
            body = config.get('BODY', '')

            # 配置代理
            proxies = self.get_proxy(proxy_url)

            # 生成时间戳变量
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            iso_timestamp = datetime.datetime.now().isoformat()
            unix_timestamp = str(int(time.time()))

            # 变量替换
            replacements = {
                "$title": title, "{{title}}": title,
                "$content": content, "{{content}}": content,
                "$timestamp": timestamp, "{{timestamp}}": timestamp,
                "$iso_timestamp": iso_timestamp, "{{iso_timestamp}}": iso_timestamp,
                "$unix_timestamp": unix_timestamp, "{{unix_timestamp}}": unix_timestamp,
            }

            # 处理URL中的变量（需要URL编码）
            processed_url = url
            for placeholder, value in replacements.items():
                processed_url = processed_url.replace(placeholder, urllib.parse.quote_plus(str(value)))

            # 处理Body中的变量（不需要编码）
            processed_body = body
            for placeholder, value in replacements.items():
                processed_body = processed_body.replace(placeholder, str(value).replace("\n", "\\n"))

            # 处理图片变量
            if "$image" in processed_body:
                image_base64 = ""
                if image is not None:  # image是MatLike，可能具有多个参数，此时if image会歧义
                    try:
                        image_bytes = self.image_to_bytes(image)
                        if image_bytes:
                            image_bytes.seek(0)
                            image_base64 = base64.b64encode(image_bytes.getvalue()).decode('utf-8')
                    except Exception as e:
                        log.error(f"图片处理失败: {e}")
                        image_base64 = ""

                processed_body = processed_body.replace("$image", image_base64)

            # 解析请求头
            try:
                headers = json.loads(headers_str) if headers_str and headers_str != "{}" else {}
            except json.JSONDecodeError:
                # 如果解析失败，尝试解析为键值对格式
                headers = {}
                if headers_str and headers_str != "{}":
                    for line in headers_str.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            headers[key.strip()] = value.strip()

            # 添加Content-Type
            headers['Content-Type'] = content_type

            # GET 请求通常不包含 body
            request_data = None if method == "GET" else processed_body.encode("utf-8")
            # 发送请求
            response = requests.request(
                method=method,
                url=processed_url,
                headers=headers,
                data=request_data,
                timeout=15,
                proxies=proxies,
            )

            # 检查响应状态
            response.raise_for_status()

            return True, f"Webhook推送成功！状态码: {response.status_code}"

        except requests.RequestException as e:
            log.error("网络请求异常", exc_info=True)
            return False, f"网络请求异常: {str(e)}"
        except Exception as e:
            log.error("Webhook推送异常", exc_info=True)
            return False, f"Webhook推送异常: {str(e)}"

    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证Webhook配置

        Args:
            config: 配置字典

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        url = config.get('URL', '')
        method = config.get('METHOD', '')
        content_type = config.get('CONTENT_TYPE', '')
        body = config.get('BODY', '')

        if not url.strip():
            return False, "URL不能为空"

        if not method.strip():
            return False, "HTTP方法不能为空"

        if method not in ["POST", "GET", "PUT"]:
            return False, "HTTP方法必须是 POST、GET 或 PUT"

        if not content_type.strip():
            return False, "Content-Type不能为空"

        if not body.strip():
            return False, "请求体不能为空"

        return True, "配置验证通过"
