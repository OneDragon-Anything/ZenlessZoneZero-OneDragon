import json
import datetime
import time
import re
from typing import Dict, List, Optional, Any, Union


class CurlGenerator:
    """cURL 命令生成器"""

    # 常量定义
    DEFAULT_METHOD = "POST"
    DEFAULT_CONTENT_TYPE = "application/json"

    # 模板变量正则模式（提升性能）
    TEMPLATE_PATTERN = re.compile(r'\{\{(\w+)\}\}')

    def generate_curl_command(self, cards: Dict[str, Any]) -> Optional[str]:
        """
        生成 cURL 命令

        Args:
            cards: 包含 webhook 配置的卡片字典

        Returns:
            生成的 cURL 命令字符串，如果配置无效则返回 None
        """
        # 提取配置
        webhook_config = self._extract_config_from_cards(cards)
        if not webhook_config:
            return None

        # 生成模板变量替换映射
        replacements = self._create_template_replacements()

        # 构建 cURL 命令各部分
        curl_parts = self._build_curl_parts(webhook_config, replacements)

        # 返回完整的 cURL 命令
        return ' \\\n  '.join(curl_parts)

    def _extract_config_from_cards(self, cards: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """从卡片实例中提取配置"""
        # 检查必需的 URL 卡片
        url_card = cards.get('url')
        if not url_card:
            return None

        # 提取配置值
        config = {
            'url': self._safe_get_card_value(url_card),
            'method': self._safe_get_card_value(cards.get('method'), self.DEFAULT_METHOD),
            'content_type': self._safe_get_card_value(cards.get('content_type'), self.DEFAULT_CONTENT_TYPE),
            'headers': self._safe_get_card_value(cards.get('headers')),
            'body': self._safe_get_card_value(cards.get('body'), "{}")
        }

        # 验证 URL 不为空
        if not config['url']:
            return None

        return config

    def _safe_get_card_value(self, card: Any, default: str = "") -> str:
        """
        安全获取卡片值

        Args:
            card: 卡片对象
            default: 默认值

        Returns:
            卡片值或默认值
        """
        if card and hasattr(card, 'getValue'):
            value = card.getValue()
            return value if value is not None else default
        return default

    def _create_template_replacements(self) -> Dict[str, str]:
        """
        创建模板变量替换映射

        Returns:
            模板变量映射字典
        """
        now_datetime = datetime.datetime.now()
        unix_timestamp = int(time.time())

        return {
            "title": "测试通知标题",
            "content": "这是一条测试消息内容",
            "timestamp": now_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "iso_timestamp": now_datetime.isoformat(),
            "unix_timestamp": str(unix_timestamp)
        }

    def _build_curl_parts(self, config: Dict[str, str], replacements: Dict[str, str]) -> List[str]:
        """
        构建 cURL 命令各部分

        Args:
            config: 配置字典
            replacements: 模板变量替换映射

        Returns:
            cURL 命令部分列表
        """
        method = config.get("method", self.DEFAULT_METHOD)
        curl_parts = [f'curl -X {method}']

        # 添加 Content-Type
        content_type = config.get('content_type')
        if content_type:
            curl_parts.append(f'-H "Content-Type: {content_type}"')

        # 添加自定义 headers
        self._add_custom_headers(curl_parts, config.get('headers', ''), replacements)

        # 添加请求体
        self._add_request_body(curl_parts, config.get('body', ''), replacements)

        # 添加 URL
        url = self._replace_template_variables(config.get('url', ''), replacements)
        curl_parts.append(f'"{url}"')

        return curl_parts

    def _add_custom_headers(self, curl_parts: List[str], headers_str: str, replacements: Dict[str, str]) -> None:
        """
        添加自定义 headers 到 cURL 命令

        Args:
            curl_parts: cURL 命令部分列表
            headers_str: headers JSON 字符串
            replacements: 模板变量替换映射
        """
        if not headers_str.strip():
            return

        try:
            headers_data = json.loads(headers_str)

            if isinstance(headers_data, dict):
                self._add_headers_from_dict(curl_parts, headers_data, replacements)
            elif isinstance(headers_data, list):
                self._add_headers_from_list(curl_parts, headers_data, replacements)

        except (json.JSONDecodeError, TypeError) as e:
            # 解析失败时忽略 headers，但可以记录警告
            # TODO: 可以考虑添加日志记录
            pass

    def _add_headers_from_dict(self, curl_parts: List[str], headers: Dict[str, Any], replacements: Dict[str, str]) -> None:
        """
        从字典格式添加 headers

        Args:
            curl_parts: cURL 命令部分列表
            headers: headers 字典
            replacements: 模板变量替换映射
        """
        for key, value in headers.items():
            if key and value is not None:
                header_value = self._replace_template_variables(str(value), replacements)
                # 转义特殊字符
                escaped_key = self._escape_header_value(str(key))
                escaped_value = self._escape_header_value(header_value)
                curl_parts.append(f'-H "{escaped_key}: {escaped_value}"')

    def _add_headers_from_list(self, curl_parts: List[str], headers: List[Dict[str, Any]], replacements: Dict[str, str]) -> None:
        """
        从列表格式添加 headers（兼容旧格式）

        Args:
            curl_parts: cURL 命令部分列表
            headers: headers 列表
            replacements: 模板变量替换映射
        """
        for item in headers:
            if isinstance(item, dict):
                key = item.get("key", "")
                value = item.get("value", "")
                if key and value:
                    header_value = self._replace_template_variables(str(value), replacements)
                    escaped_key = self._escape_header_value(str(key))
                    escaped_value = self._escape_header_value(header_value)
                    curl_parts.append(f'-H "{escaped_key}: {escaped_value}"')

    def _add_request_body(self, curl_parts: List[str], body: str, replacements: Dict[str, str]) -> None:
        """
        添加请求体到 cURL 命令

        Args:
            curl_parts: cURL 命令部分列表
            body: 请求体内容
            replacements: 模板变量替换映射
        """
        if not body.strip():
            return

        # 替换模板变量并转义引号
        processed_body = self._replace_template_variables(body, replacements)
        escaped_body = self._escape_json_string(processed_body)
        curl_parts.append(f'-d "{escaped_body}"')

    def _replace_template_variables(self, text: str, replacements: Dict[str, str]) -> str:
        """
        替换文本中的模板变量

        使用正则表达式提升性能，支持 {{variable}} 格式

        Args:
            text: 待处理的文本
            replacements: 变量替换映射

        Returns:
            替换后的文本
        """
        def replace_func(match):
            var_name = match.group(1)
            return replacements.get(var_name, match.group(0))

        return self.TEMPLATE_PATTERN.sub(replace_func, text)

    def _escape_header_value(self, value: str) -> str:
        """
        转义 HTTP header 值中的特殊字符

        Args:
            value: 原始值

        Returns:
            转义后的值
        """
        return value.replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')

    def _escape_json_string(self, json_str: str) -> str:
        """
        转义 JSON 字符串中的特殊字符

        Args:
            json_str: 原始 JSON 字符串

        Returns:
            转义后的字符串
        """
        return json_str.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
