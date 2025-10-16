"""
阿里云 WebTracking 客户端
通过 HTTP GET 请求向 SLS 上传遥测数据
"""
from typing import Dict, Any
from urllib.parse import urlencode

import requests

from one_dragon.utils.log_utils import log


class AliyunWebTrackingClient:
    """简易的阿里云 WebTracking 发送器"""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint.strip()
        if not self.endpoint:
            raise ValueError("Aliyun WebTracking endpoint is required")

    def send(self, event_name: str, properties: Dict[str, Any]) -> None:
        """发送事件到阿里云 SLS"""
        try:
            payload = self._build_payload(event_name, properties)
            response = requests.get(self.endpoint, params=payload, timeout=3)
            if response.status_code != 200:
                log.debug(f"Aliyun WebTracking returned {response.status_code}: {response.text}")
        except Exception as exc:
            # 仅做调试记录，不影响主流程
            log.debug(f"Failed to send event to Aliyun WebTracking: {exc}")

    def _build_payload(self, event_name: str, properties: Dict[str, Any]) -> Dict[str, str]:
        """将属性打平并转换成字符串"""
        payload: Dict[str, str] = {}
        payload["event_name"] = event_name

        for key, value in properties.items():
            str_key = str(key)
            str_value = self._value_to_string(value)
            payload[str_key] = str_value

        return payload

    @staticmethod
    def _value_to_string(value: Any) -> str:
        """将值转换为适合 WebTracking 的字符串"""
        if value is None:
            return ""
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        try:
            import json
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
