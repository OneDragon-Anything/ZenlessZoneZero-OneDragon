from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseParser(ABC):
    """
    解析器抽象基类，定义解析器的统一接口
    
    所有解析器都应继承此类并实现抽象方法
    """

    def __init__(self, ctx: Any):
        """
        初始化解析器
        
        Args:
            ctx: ZContext上下文，用于访问服务和配置
        """
        self.ctx = ctx

    @abstractmethod
    def parse(self, ocr_result: str, *args, **kwargs) -> Optional[dict]:
        """
        解析OCR结果
        
        Args:
            ocr_result: OCR识别的文本结果
            *args: 额外的位置参数
            **kwargs: 额外的关键字参数
        
        Returns:
            解析后的字典数据，如果解析失败返回 None
        """
        pass

    @abstractmethod
    def get_supported_type(self) -> str:
        """
        获取解析器支持的类型
        
        Returns:
            解析器支持的数据类型标识（如 'agent', 'drive_disk', 'wengine'）
        """
        pass

    def preprocess(self, text: str) -> str:
        """
        预处理OCR文本（可选实现）
        
        Args:
            text: 原始OCR文本
        
        Returns:
            预处理后的文本
        """
        return text.strip()

    def postprocess(self, result: dict) -> dict:
        """
        后处理解析结果（可选实现）
        
        Args:
            result: 解析后的原始结果
        
        Returns:
            后处理后的结果
        """
        return result