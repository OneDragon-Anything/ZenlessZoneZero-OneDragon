import json
import re
from typing import Optional, Any


class CurlGenerator:
    """cURL 命令生成器"""

    # 常量定义
    DEFAULT_METHOD = "POST"
    DEFAULT_CONTENT_TYPE = "application/json"

    # 模板变量正则
    TEMPLATE_PATTERN = re.compile(r'\$(\w+)')

    def generate_curl_command(self, config: dict[str, str], style: str = 'pwsh') -> Optional[str]:
        """
        生成 cURL 命令

        Args:
            config: 配置字典
            style: 命令风格，'pwsh' 或 'unix'

        Returns:
            生成的 cURL 命令字符串，如果配置无效则返回 None
        """
        # 验证必需的配置
        if not config or not config.get('url'):
            return None

        # 生成模板变量替换映射
        replacements = self._create_template_replacements()

        # 构建 cURL 命令各部分
        curl_parts = self._build_curl_parts(config, replacements, style)

        # 根据风格选择合适的连接符
        line_continuation = self._get_line_continuation_by_style(style)

        # 返回完整的 cURL 命令
        return line_continuation.join(curl_parts)

    def generate_pwsh_curl(self, config: dict[str, str]) -> Optional[str]:
        """
        生成 PowerShell 风格的 cURL 命令

        Args:
            config: 配置字典

        Returns:
            生成的 PowerShell cURL 命令字符串，如果配置无效则返回 None
        """
        return self.generate_curl_command(config, 'pwsh')

    def generate_unix_curl(self, config: dict[str, str]) -> Optional[str]:
        """
        生成 Unix/Linux 风格的 cURL 命令

        Args:
            config: 配置字典

        Returns:
            生成的 Unix cURL 命令字符串，如果配置无效则返回 None
        """
        return self.generate_curl_command(config, 'unix')

    def _create_template_replacements(self) -> dict[str, str]:
        """
        创建模板变量替换映射

        Returns:
            模板变量映射字典
        """

        return {
            "title": "一条龙运行通知",
            "content": "这是一条测试消息内容"
        }

    def _build_curl_parts(self, config: dict[str, str], replacements: dict[str, str], style: str = 'pwsh') -> list[str]:
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
        self._add_custom_headers(curl_parts, config.get('headers', ''), replacements, style)

        # 添加请求体
        self._add_request_body(curl_parts, config.get('body', ''), replacements, style)

        # 添加 URL
        url = self._replace_template_variables(config.get('url', ''), replacements)
        curl_parts.append(f'"{url}"')

        return curl_parts

    def _add_custom_headers(self, curl_parts: list[str], headers_str: str, replacements: dict[str, str], style: str) -> None:
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
                self._add_headers_from_dict(curl_parts, headers_data, replacements, style)
            elif isinstance(headers_data, list):
                self._add_headers_from_list(curl_parts, headers_data, replacements, style)

        except (json.JSONDecodeError, TypeError) as e:
            # 解析失败时忽略 headers，但可以记录警告
            # TODO: 可以考虑添加日志记录
            pass

    def _add_headers_from_dict(self, curl_parts: list[str], headers: dict[str, Any], replacements: dict[str, str], style: str) -> None:
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
                escaped_key = self._escape_header_value(str(key), style)
                escaped_value = self._escape_header_value(header_value, style)
                curl_parts.append(f'-H "{escaped_key}: {escaped_value}"')

    def _add_headers_from_list(self, curl_parts: list[str], headers: list[dict[str, Any]], replacements: dict[str, str], style: str) -> None:
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
                    escaped_key = self._escape_header_value(str(key), style)
                    escaped_value = self._escape_header_value(header_value, style)
                    curl_parts.append(f'-H "{escaped_key}: {escaped_value}"')

    def _add_request_body(self, curl_parts: list[str], body: str, replacements: dict[str, str], style: str) -> None:
        """
        添加请求体到 cURL 命令

        Args:
            curl_parts: cURL 命令部分列表
            body: 请求体内容
            replacements: 模板变量替换映射
        """
        if not body.strip():
            return

        # 替换模板变量
        processed_body = self._replace_template_variables(body, replacements)

        # 尝试将 JSON 转换为紧凑格式，去除格式化换行符
        try:
            # 如果是有效的 JSON，转换为紧凑格式
            json_obj = json.loads(processed_body)
            processed_body = json.dumps(json_obj, separators=(',', ':'), ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            # 如果不是有效的 JSON，保持原样
            pass

        # 根据不同 shell 选择引用方式
        if style == 'pwsh':
            # PowerShell: 使用单引号避免转义问题，只需要处理单引号本身
            escaped_body = processed_body.replace("'", "''")
            curl_parts.append(f"-d '{escaped_body}'")
        else:
            # Unix/Linux: 使用双引号并转义特殊字符
            escaped_body = self._escape_json_string(processed_body, style)
            curl_parts.append(f'-d "{escaped_body}"')

    def _replace_template_variables(self, text: str, replacements: dict[str, str]) -> str:
        """
        替换文本中的模板变量

        使用正则表达式提升性能，支持 $variable 格式

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

    def _get_line_continuation_by_style(self, style: str) -> str:
        """
        根据指定风格获取合适的命令行续行符

        Args:
            style: 命令风格，'pwsh' 或 'unix'

        Returns:
            续行符字符串
        """
        if style == 'pwsh':
            return ' `\r\n  '  # PowerShell 使用反引号
        else:  # unix
            return ' \\\n  '  # Unix/Linux 使用反斜杠

    def _escape_header_value(self, value: str, style: str) -> str:
        """
        转义 HTTP header 值中的特殊字符

        Args:
            value: 原始值
            style: 命令风格，'pwsh' 或 'unix'

        Returns:
            转义后的值
        """
        # 基本转义：双引号和换行符
        escaped = value.replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')

        # PowerShell 额外转义反引号
        if style == 'pwsh':
            escaped = escaped.replace('`', '``')

        return escaped

    def _escape_json_string(self, json_str: str, style: str) -> str:
        """
        转义 JSON 字符串中的特殊字符（仅用于 Unix/Linux）

        Args:
            json_str: 原始 JSON 字符串
            style: 命令风格（此方法仅处理 unix 风格）

        Returns:
            转义后的字符串
        """
        # Unix/Linux: 转义双引号、反斜杠和换行符
        return json_str.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
