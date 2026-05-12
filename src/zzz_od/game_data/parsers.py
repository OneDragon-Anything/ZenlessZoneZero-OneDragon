from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from cv2.typing import MatLike


class IAgentNameParser(ABC):
    """代理人名称解析器接口"""

    @abstractmethod
    def parse_ocr_result(
        self,
        ocr_items: List[Dict],
        screenshot: Optional[MatLike] = None
    ) -> Optional[Dict]:
        """
        解析OCR结果，返回代理人信息

        Args:
            ocr_items: OCR识别结果列表
            screenshot: 截图

        Returns:
            包含代理人信息的字典，如果解析失败则返回None
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """重置解析器状态"""
        pass
