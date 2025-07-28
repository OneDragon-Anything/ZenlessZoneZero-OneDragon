import json
import re
import shlex
from typing import Optional, Dict, List, Tuple


class CurlParser:
    """cURL 命令解析器"""

    def __init__(self):
        # cURL 参数映射
        self.method_args = ['-X', '--request']
        self.header_args = ['-H', '--header']
        self.data_args = ['-d', '--data', '--data-raw', '--data-binary']
        self.unsupported_args = [
            '-F', '--form', '-u', '--user', '--cert', '--key',
            '--proxy', '--cacert', '--insecure', '-k', '-L', '--location'
        ]

    def parse_curl_command(self, curl_command: str) -> Dict[str, str]:
        """
        解析 cURL 命令并返回配置字典

        Args:
            curl_command: cURL 命令字符串

        Returns:
            包含解析结果的配置字典

        Raises:
            ValueError: 当命令格式无效时
        """
        if not curl_command.strip():
            raise ValueError("cURL 命令不能为空")

        # 检查是否是 cURL 命令
        if not curl_command.strip().startswith('curl'):
            raise ValueError("输入内容不是有效的 cURL 命令")

        # 解析命令参数
        args = self._parse_curl_args(curl_command)

        # 检查不支持的参数
        unsupported = self._check_unsupported_args(args)
        if unsupported:
            raise ValueError(f"包含不支持的参数: {', '.join(unsupported)}")

        # 提取各个配置项
        config = {
            'method': self._extract_method(args),
            'url': self._extract_url(args),
            'content_type': 'application/json',  # 默认值
            'headers': '{}',
            'body': ''
        }

        # 提取请求头
        headers = self._extract_headers(args)
        if headers:
            # 提取 Content-Type
            content_type = headers.pop('Content-Type', headers.pop('content-type', None))
            if content_type:
                config['content_type'] = content_type

            # 剩余请求头转为 JSON
            if headers:
                config['headers'] = json.dumps(headers, ensure_ascii=False)

        # 提取请求体
        body = self._extract_data(args)
        if body:
            config['body'] = body

        # 验证必需的配置
        if not config['url']:
            raise ValueError("未找到有效的 URL")

        return config

    def _parse_curl_args(self, curl_command: str) -> List[str]:
        """
        解析 cURL 命令参数

        Args:
            curl_command: cURL 命令字符串

        Returns:
            参数列表
        """
        # 预处理：处理反斜杠换行
        processed_command = self._preprocess_curl_command(curl_command)

        # 使用 shlex 处理引号和转义字符
        args = shlex.split(processed_command)

        # 移除第一个 'curl' 参数
        return args[1:] if args and args[0] == 'curl' else args

    def _preprocess_curl_command(self, curl_command: str) -> str:
        """
        预处理 cURL 命令，处理换行和空格

        Args:
            curl_command: 原始 cURL 命令

        Returns:
            处理后的单行命令
        """
        # 1. 处理 Linux/Unix 风格的反斜杠换行：将 "\ \n" 替换为空格
        processed = re.sub(r'\\\s*\r?\n\s*', ' ', curl_command)

        # 2. 处理 PowerShell 风格的反引号换行：将 "` \n" 替换为空格
        processed = re.sub(r'`\s*\r?\n\s*', ' ', processed)

        # 3. 处理普通的换行符（如果没有续行符，也合并成空格）
        processed = re.sub(r'\r?\n\s*', ' ', processed)

        # 4. 处理多余的空格
        processed = re.sub(r'\s+', ' ', processed)

        # 5. 去除首尾空格
        return processed.strip()

    def _check_unsupported_args(self, args: List[str]) -> List[str]:
        """
        检查不支持的参数

        Args:
            args: 参数列表

        Returns:
            不支持的参数列表
        """
        unsupported = []
        for arg in args:
            if arg in self.unsupported_args:
                unsupported.append(arg)
        return unsupported

    def _extract_method(self, args: List[str]) -> str:
        """
        提取 HTTP 方法

        Args:
            args: 参数列表

        Returns:
            HTTP 方法，默认为 POST
        """
        for i, arg in enumerate(args):
            if arg in self.method_args and i + 1 < len(args):
                return args[i + 1].upper()
        return 'POST'  # 默认方法

    def _extract_url(self, args: List[str]) -> str:
        """
        提取 URL

        Args:
            args: 参数列表

        Returns:
            URL 字符串
        """
        # URL 可能在任何位置，需要更智能的识别
        i = 0
        url_candidates = []

        while i < len(args):
            arg = args[i]

            # 跳过已知的参数及其值
            if arg in self.method_args + self.header_args + self.data_args:
                i += 2  # 跳过参数和它的值
                continue

            # 如果不是参数（不以 - 开头），可能是 URL
            if not arg.startswith('-'):
                # 检查是否包含协议或域名特征
                if any(protocol in arg.lower() for protocol in ['http://', 'https://', 'ftp://']):
                    return arg
                elif '.' in arg and ('/' in arg or arg.count('.') >= 2):
                    # 可能是域名格式的 URL
                    url_candidates.append(arg)

            i += 1

        # 如果找到候选 URL，返回第一个
        if url_candidates:
            return url_candidates[0]

        # 最后尝试：返回最后一个不以 - 开头的参数
        for arg in reversed(args):
            if not arg.startswith('-'):
                return arg

        return ''

    def _extract_headers(self, args: List[str]) -> Dict[str, str]:
        """
        提取请求头

        Args:
            args: 参数列表

        Returns:
            请求头字典
        """
        headers = {}
        i = 0
        while i < len(args):
            if args[i] in self.header_args and i + 1 < len(args):
                header_value = args[i + 1]
                # 解析 header: value 格式
                if ':' in header_value:
                    key, value = header_value.split(':', 1)
                    headers[key.strip()] = value.strip()
                i += 2
            else:
                i += 1
        return headers

    def _extract_data(self, args: List[str]) -> str:
        """
        提取请求体数据

        Args:
            args: 参数列表

        Returns:
            请求体字符串
        """
        data_parts = []
        i = 0
        while i < len(args):
            if args[i] in self.data_args and i + 1 < len(args):
                data_parts.append(args[i + 1])
                i += 2
            else:
                i += 1

        # 合并多个 -d 参数
        if data_parts:
            combined_data = '&'.join(data_parts)
            return combined_data

        return ''
