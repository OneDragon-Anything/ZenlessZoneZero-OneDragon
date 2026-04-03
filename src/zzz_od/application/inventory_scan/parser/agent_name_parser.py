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
    
    def parse_ocr_result(self, ocr_items: List[Dict], screenshot: Optional[MatLike] = None) -> Optional[Dict]:
        """
        解析OCR结果，只返回角色名称
        
        Args:
            ocr_items: OCR识别结果列表
            screenshot: 截图
            
        Returns:
            包含角色名称的字典，如果解析失败则返回None
        """
        try:
            # 解析角色名称
            agent_name = self.agent_parser._parse_agent_name(ocr_items, screenshot)
            if not agent_name:
                log.error("无法解析代理人名称")
                return None
            
            # 检查是否在翻译表中
            matched_key = self.agent_parser._match_translation(agent_name, screenshot)
            chs_name = agent_name  # 默认使用原始名称作为中文名称
            
            # 如果匹配到翻译表，获取对应的中文名称
            if matched_key:
                character_dict = self.agent_parser.translation_service.translation_dict.get('character', {})
                if matched_key in character_dict:
                    char_data = character_dict[matched_key]
                    if isinstance(char_data, dict) and 'CHS' in char_data:
                        chs_name = char_data['CHS']
                        log.debug(f"匹配到角色中文名称: {chs_name}")
            
            # 检查是否重复
            if chs_name in self.scanned_agent_keys:
                log.warning(f"角色 {chs_name} 已扫描过，跳过重复")
                return None
            
            # 记录已扫描
            self.scanned_agent_keys.add(chs_name)
            
            # 构建返回数据
            self.agent_counter += 1
            return {
                'key': chs_name,  # 使用中文名称作为key
                'id': f'zzz_agent_{self.agent_counter}'
            }
            
        except Exception as e:
            log.error(f"解析代理人名称失败: {e}", exc_info=True)
            return None
