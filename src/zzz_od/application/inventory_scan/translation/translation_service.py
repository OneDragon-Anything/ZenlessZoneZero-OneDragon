import json
import os
from typing import Optional, Dict, Tuple

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
import difflib

from .translation_updater import TranslationUpdater


class TranslationService:
    """翻译服务"""

    def __init__(self):
        # 从 assets/wiki_data 读取字典
        self.user_dict_path = os.path.join(
            os_utils.get_path_under_work_dir('assets', 'wiki_data'),
            'zzz_translation.json'
        )
        # 本项目只有一份字典：config/zzz_translation.json
        # “自带的默认字典”和“下载更新的字典”是同一个文件路径，只是我们预置了一份初始内容。
        self.translation_dict: Optional[Dict] = None

        # 特殊名称映射（繁简转换等）
        self.special_name_mapping = {
            '賽斯': '赛斯',  # 繁体 -> 简体
            '賽斯・洛威尔': '赛斯',  # 繁体 -> 简体
            '赛斯・洛威尔': '赛斯',  # 简体 -> 简体
            '搖摆': '摇摆',  # 错别字修复
            '昇常': '异常',  # 错别字修复
            '異常': '异常',  # 日繁体 -> 简体
            '昇常精通': '异常精通',  # 错别字修复
            '昇常掌控': '异常掌控',  # 错别字修复
        }

        self._check_update()
        self._load_dict()

    def _check_update(self):
        """检查并更新翻译字典"""
        try:
            updater = TranslationUpdater()
            updater.update_if_needed()
        except Exception as e:
            log.error(f"检查翻译更新失败: {e}")

    def _load_dict(self):
        """加载翻译字典"""
        # 1. 尝试加载用户字典
        if self._try_load_dict(self.user_dict_path, "用户"):
            return

        # 2. 加载失败，使用空字典
        log.warning("未找到任何翻译字典，使用空字典")
        self.translation_dict = {
            'character': {},
            'weapon': {},
            'equipment': {}
        }

    def _try_load_dict(self, path: str, type_name: str) -> bool:
        """尝试加载字典"""
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self.translation_dict = json.load(f)
                log.info(f"加载{type_name}翻译字典成功: {path}")
                return True
        except Exception as e:
            log.error(f"加载{type_name}翻译字典失败: {e}")
        return False

    def translate_character(self, name: str, target_lang: str = 'CHS') -> str:
        """翻译角色名称"""
        return self._translate('character', name, target_lang)

    def translate_weapon(self, name: str, target_lang: str = 'CHS') -> str:
        """翻译音擎名称"""
        return self._translate('weapon', name, target_lang)

    def translate_equipment(self, name: str, target_lang: str = 'CHS') -> str:
        """翻译驱动盘名称"""
        return self._translate('equipment', name, target_lang)

    def correct_text(self, text: str) -> str:
        """
        修正OCR文本中的常见错误
        该方法会对文本进行遍历替换，适用于包含错别字的长文本
        """
        if not text:
            return text

        result = text
        for wrong, right in self.special_name_mapping.items():
            if wrong in result:
                result = result.replace(wrong, right)

        return result

    def _translate(self, category: str, name: str, target_lang: str) -> str:
        """通用翻译方法，支持模糊匹配"""
        if not self.translation_dict:
            return name

        # 0. 检查特殊名称映射（优先级最高）
        if name in self.special_name_mapping:
            mapped_name = self.special_name_mapping[name]
            log.info(f"特殊名称映射: {name} -> {mapped_name}")
            name = mapped_name

        category_dict = self.translation_dict.get(category, {})

        # 1. 尝试直接匹配（完全匹配）
        if name in category_dict:
            return category_dict[name].get(target_lang, name)

        # 2. 尝试从其他语言反向查找（完全匹配）
        for key, translations in category_dict.items():
            for lang, trans_name in translations.items():
                if trans_name == name:
                    return translations.get(target_lang, name)

        # 3. 模糊匹配（相似度>0.2，取最接近的）
        best_match, confidence = self._fuzzy_match(name, category_dict)
        if best_match and confidence > 0.2:
            log.info(f"模糊匹配: {name} -> {best_match} (置信度: {confidence:.4f})")
            return category_dict[best_match].get(target_lang, name)

        # 4. 未匹配到，返回原名
        log.warning(f"未找到匹配: {name}")
        return name

    def _fuzzy_match(self, name: str, category_dict: Dict) -> Tuple[Optional[str], float]:
        """
        模糊匹配，返回最佳匹配的key和置信度

        Args:
            name: 待匹配的名称
            category_dict: 类别字典

        Returns:
            (best_match_key, confidence)
        """
        best_match = None
        best_ratio = 0.0

        # 收集所有可能的匹配候选
        candidates = []
        for key, translations in category_dict.items():
            candidates.append((key, key))  # 英文key
            for lang, trans_name in translations.items():
                candidates.append((key, trans_name))  # 各语言翻译

        # 计算相似度
        for key, candidate in candidates:
            ratio = difflib.SequenceMatcher(None, name, candidate).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = key

        return best_match, best_ratio

    def reload(self):
        """重新加载字典"""
        self._load_dict()


def __debug():
    """测试翻译"""
    service = TranslationService()

    # 测试角色翻译
    print(service.translate_character('Corin', 'CHS'))  # 应该输出: 可琳
    print(service.translate_character('可琳', 'EN'))    # 应该输出: Corin

    # 测试音擎翻译
    print(service.translate_weapon('The Brimstone', 'CHS'))  # 应该输出: 硫磺石

    # 测试驱动盘翻译
    print(service.translate_equipment('Proto Punk', 'CHS'))  # 应该输出: 原始朋克


if __name__ == '__main__':
    __debug()
