from typing import List, Dict, Optional
from cv2.typing import MatLike
from one_dragon.utils.log_utils import log
from .agent_parser import AgentParser


class AgentNameParser:
    """只解析角色名称的解析器"""

    def __init__(self):
        """初始化名称解析器"""
        self.agent_parser = AgentParser()
        self.scanned_agent_keys = set()  # 记录已扫描的角色key
        self.agent_counter = 0

    def parse_ocr_result(
        self, ocr_items: List[Dict], screenshot: Optional[MatLike] = None
    ) -> Optional[Dict]:
        """
        解析OCR结果，只返回角色名称

        Args:
            ocr_items: OCR识别结果列表
            screenshot: 截图

        Returns:
            包含角色名称的字典，如果解析失败则返回None
        """
        try:
            agent_name = self.agent_parser._parse_agent_name(ocr_items, screenshot)
            if not agent_name:
                log.error("无法解析代理人名称")
                return None

            # _parse_agent_name 已经调用过 _match_translation
            # 如果返回的是 code（不含"(未匹配)"标记），直接使用
            if "(未匹配)" not in agent_name:
                matched_code = agent_name
                if matched_code in self.scanned_agent_keys:
                    log.warning(f"角色 {matched_code} 已扫描过，跳过重复")
                    return None
                self.scanned_agent_keys.add(matched_code)
                self.agent_counter += 1
                return {"key": matched_code, "id": f"zzz_agent_{self.agent_counter}"}

            # 如果有"(未匹配)"标记，使用原始名称
            chs_name = agent_name.replace("(未匹配)", "")
            if chs_name in self.scanned_agent_keys:
                log.warning(f"角色 {chs_name} 已扫描过，跳过重复")
                return None

            self.scanned_agent_keys.add(chs_name)
            self.agent_counter += 1
            return {"key": chs_name, "id": f"zzz_agent_{self.agent_counter}"}

        except Exception as e:
            log.error(f"解析代理人名称失败: {e}", exc_info=True)
            return None
