import difflib
import json
import os
from pathlib import Path
from typing import Optional

from yaml import safe_dump, safe_load

from one_dragon.base.config.yaml_data_set_loader import YamlDataSetLoader
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log


class TranslationService:
    """
    翻译服务
    
    核心特性：
    - 整合三个 YamlDataSetLoader 分别管理角色、驱动盘、音擎数据
    - 内存映射缓存：_id_2_xxx 字典存储原始数据
    - 优先读取合并文件以减少 IO 操作
    """

    # 合并文件名（与 ScreenLoader、IntelManageConfig 保持一致）
    MERGED_FILE_NAME: str = "_od_merged.yml"

    def __init__(self):
        # 用户翻译字典（优先级最高）
        self.user_dict_path = os.path.join(
            os_utils.get_path_under_work_dir("assets", "wiki_data"),
            "zzz_translation.json",
        )

        # 翻译字典（最终用于翻译）
        self.translation_dict: dict[str, dict] = {}

        # 数据集加载器
        self.agent_loader = self._create_agent_loader()
        self.drive_disk_loader = self._create_drive_disk_loader()
        self.engine_weapon_loader = self._create_engine_weapon_loader()

        # 特殊名称映射（繁简转换、OCR错误修正）
        self.special_name_mapping = {
            "賽斯": "赛斯",
            "賽斯·洛威尔": "赛斯",
            "赛斯·洛威尔": "赛斯",
            "搖摆": "摇摆",
            "昇常": "异常",
            "異常": "异常",
            "昇常精通": "异常精通",
            "昇常掌控": "异常掌控",
            "流光詠叹": "流光咏叹",
            "詠叹": "咏叹",
        }

        # 初始化加载
        self._load_dict()

    def _create_agent_loader(self) -> 'YamlDataSetLoader[dict]':
        """创建角色数据加载器"""
        service = self

        class AgentLoader(YamlDataSetLoader[dict]):
            def _extract_primary_key(self, data: dict) -> str:
                return data.get("code", data["agent_name"].lower().replace(" ", "_"))

            def _extract_name_key(self, data: dict) -> str:
                return data.get("agent_name", "")

            def _convert_to_object(self, data: dict) -> dict:
                return data

            def _validate_data(self, data: dict) -> bool:
                return isinstance(data, dict) and "agent_name" in data

            def _load_from_memory(self) -> None:
                super()._load_from_memory()
                service._add_agent_to_dict_all()

            def _load_from_separated_files(self) -> None:
                super()._load_from_separated_files()
                service._add_agent_to_dict_all()

            def _load_from_merged_or_separated(self) -> None:
                super()._load_from_merged_or_separated()
                service._add_agent_to_dict_all()

        return AgentLoader("agent")

    def _create_drive_disk_loader(self) -> 'YamlDataSetLoader[dict]':
        """创建驱动盘数据加载器"""
        service = self

        class DriveDiskLoader(YamlDataSetLoader[dict]):
            def _extract_primary_key(self, data: dict) -> str:
                return data.get("code", data["set_name"].lower().replace(" ", "_"))

            def _extract_name_key(self, data: dict) -> str:
                return data.get("set_name", "")

            def _convert_to_object(self, data: dict) -> dict:
                return data

            def _validate_data(self, data: dict) -> bool:
                return isinstance(data, dict) and "set_name" in data

            def _load_from_memory(self) -> None:
                super()._load_from_memory()
                service._add_drive_disk_to_dict_all()

            def _load_from_separated_files(self) -> None:
                super()._load_from_separated_files()
                service._add_drive_disk_to_dict_all()

            def _load_from_merged_or_separated(self) -> None:
                super()._load_from_merged_or_separated()
                service._add_drive_disk_to_dict_all()

        return DriveDiskLoader("drive_disk")

    def _create_engine_weapon_loader(self) -> 'YamlDataSetLoader[dict]':
        """创建音擎数据加载器"""
        service = self

        class EngineWeaponLoader(YamlDataSetLoader[dict]):
            def _extract_primary_key(self, data: dict) -> str:
                return data.get("code", data["weapon_name"].lower().replace(" ", "_"))

            def _extract_name_key(self, data: dict) -> str:
                return data.get("weapon_name", "")

            def _convert_to_object(self, data: dict) -> dict:
                return data

            def _validate_data(self, data: dict) -> bool:
                return isinstance(data, dict) and "weapon_name" in data

            def _load_from_memory(self) -> None:
                super()._load_from_memory()
                service._add_engine_weapon_to_dict_all()

            def _load_from_separated_files(self) -> None:
                super()._load_from_separated_files()
                service._add_engine_weapon_to_dict_all()

            def _load_from_merged_or_separated(self) -> None:
                super()._load_from_merged_or_separated()
                service._add_engine_weapon_to_dict_all()

        return EngineWeaponLoader("engine_weapon")

    def _load_dict(self) -> None:
        """
        加载翻译字典
        
        加载优先级：
        1. 用户翻译字典（外部 wiki_data）
        2. 合并文件（_od_merged.yml）
        3. 单独文件（各 .yml 文件）
        """
        # 优先尝试加载用户翻译字典
        if self._try_load_user_dict():
            return

        log.warning("未找到用户翻译字典，从游戏数据目录加载")
        
        # 初始化空字典
        self.translation_dict = {"character": {}, "weapon": {}, "equipment": {}}

        # 加载各类数据（采用 YamlDataSetLoader 三模式的默认模式）
        self.agent_loader.load()
        self.drive_disk_loader.load()
        self.engine_weapon_loader.load()

    def reload(self, from_memory: bool = False, from_separated_files: bool = False) -> None:
        """
        重新加载翻译字典

        Args:
            from_memory: 是否从内存缓存加载
            from_separated_files: 是否从单独文件加载
        """
        self.translation_dict = {"character": {}, "weapon": {}, "equipment": {}}

        # 重新加载各类数据
        self.agent_loader.load(from_memory, from_separated_files)
        self.drive_disk_loader.load(from_memory, from_separated_files)
        self.engine_weapon_loader.load(from_memory, from_separated_files)

        log.info(f"TranslationService reloaded | "
                 f"角色: {len(self.translation_dict['character'])} | "
                 f"驱动盘: {len(self.translation_dict['equipment'])} | "
                 f"音擎: {len(self.translation_dict['weapon'])}")

    @property
    def _id_2_agent(self) -> dict:
        """兼容旧代码：代理 _id_2_agent 访问"""
        return self.agent_loader._id_2_data

    @property
    def _id_2_drive_disk(self) -> dict:
        """兼容旧代码：代理 _id_2_drive_disk 访问"""
        return self.drive_disk_loader._id_2_data

    @property
    def _id_2_engine_weapon(self) -> dict:
        """兼容旧代码：代理 _id_2_engine_weapon 访问"""
        return self.engine_weapon_loader._id_2_data

    def _add_agent_to_dict_all(self) -> None:
        """将所有角色数据添加到翻译字典"""
        for data in self.agent_loader.get_all():
            self._add_agent_to_dict(data)

    def _add_drive_disk_to_dict_all(self) -> None:
        """将所有驱动盘数据添加到翻译字典"""
        for data in self.drive_disk_loader.get_all():
            self._add_drive_disk_to_dict(data)

    def _add_engine_weapon_to_dict_all(self) -> None:
        """将所有音擎数据添加到翻译字典"""
        for data in self.engine_weapon_loader.get_all():
            self._add_engine_weapon_to_dict(data)

    def _try_load_user_dict(self) -> bool:
        """
        尝试加载用户翻译字典
        
        Returns:
            bool: 是否加载成功
        """
        if not os.path.exists(self.user_dict_path):
            return False

        try:
            with open(self.user_dict_path, "r", encoding="utf-8") as f:
                self.translation_dict = json.load(f)
            
            # 初始化内存映射
            for name, data in self.translation_dict.get("character", {}).items():
                code = data.get("EN", name.lower().replace(" ", "_"))
                self._id_2_agent[code] = data
            
            for name, data in self.translation_dict.get("equipment", {}).items():
                code = data.get("EN", name.lower().replace(" ", "_"))
                self._id_2_drive_disk[code] = data
            
            for name, data in self.translation_dict.get("weapon", {}).items():
                code = data.get("EN", name.lower().replace(" ", "_"))
                self._id_2_engine_weapon[code] = data

            log.info(f"从用户翻译字典加载 | "
                     f"角色: {len(self.translation_dict.get('character', {}))} | "
                     f"驱动盘: {len(self.translation_dict.get('equipment', {}))} | "
                     f"音擎: {len(self.translation_dict.get('weapon', {}))}")
            return True

        except Exception as e:
            log.error(f"加载用户翻译字典失败: {e}")
            return False



    def _add_agent_to_dict(self, data: dict) -> None:
        """将角色数据添加到翻译字典"""
        code = data.get("code")
        name = data.get("agent_name")
        if code and name:
            self.translation_dict["character"][name] = {"CHS": name, "EN": code}

    def _add_drive_disk_to_dict(self, data: dict) -> None:
        """将驱动盘数据添加到翻译字典"""
        code = data.get("code")
        name = data.get("set_name")
        if code and name:
            self.translation_dict["equipment"][name] = {"CHS": name, "EN": code}

    def _add_engine_weapon_to_dict(self, data: dict) -> None:
        """将音擎数据添加到翻译字典"""
        code = data.get("code")
        name = data.get("weapon_name")
        if code and name:
            self.translation_dict["weapon"][name] = {"CHS": name, "EN": code}

    def correct_text(self, text: str) -> str:
        """
        修正文本（繁简转换、OCR错误修正）
        
        Args:
            text: 原始文本
            
        Returns:
            修正后的文本
        """
        if not text:
            return text
        
        # 应用特殊名称映射
        corrected = text
        for wrong, right in self.special_name_mapping.items():
            if wrong in corrected:
                corrected = corrected.replace(wrong, right)
        
        return corrected

    def translate_character(self, name: str, target_lang: str = "EN") -> str:
        """翻译角色名称"""
        return self._translate("character", name, target_lang)

    def translate_weapon(self, name: str, target_lang: str = "EN") -> str:
        """翻译音擎名称"""
        return self._translate("weapon", name, target_lang)

    def translate_equipment(self, name: str, target_lang: str = "EN") -> str:
        """翻译驱动盘名称"""
        return self._translate("equipment", name, target_lang)

    def get_drive_disk_name_by_code(self, code: str) -> str:
        """
        根据驱动盘代码获取中文名称
        
        Args:
            code: 驱动盘英文代码
            
        Returns:
            驱动盘中文名称，未找到则返回原代码
        """
        data = self._id_2_drive_disk.get(code)
        if data:
            return data.get("set_name", code)
        return code

    def _translate(self, category: str, name: str, target_lang: str) -> str:
        """
        通用翻译方法（参考原有实现）
        
        Args:
            category: 翻译类别（character/weapon/equipment）
            name: 要翻译的名称
            target_lang: 目标语言
            
        Returns:
            翻译后的名称，未找到则返回原名
        """
        if not self.translation_dict:
            return name

        # 特殊名称映射（优先级最高）
        if name in self.special_name_mapping:
            name = self.special_name_mapping[name]

        category_dict = self.translation_dict.get(category, {})

        # 1. 直接匹配
        if name in category_dict:
            return self._extract_translation(category_dict[name], target_lang, name)

        # 2. 反向查找
        for key, translations in category_dict.items():
            if isinstance(translations, dict):
                for lang, translated_name in translations.items():
                    if translated_name == name:
                        return self._extract_translation(translations, target_lang, name)

        # 3. 模糊匹配
        best_match, confidence = self._fuzzy_match(name, category_dict)
        if best_match and confidence > 0.2:
            return self._extract_translation(category_dict[best_match], target_lang, name)

        # 4. 返回原名
        return name

    def _extract_translation(self, translations: dict, target_lang: str, default: str) -> str:
        """提取翻译结果"""
        if isinstance(translations, dict):
            return translations.get(target_lang, default)
        return default

    def _fuzzy_match(self, name: str, category_dict: dict) -> tuple[Optional[str], float]:
        """
        模糊匹配（参考原有实现）
        
        Returns:
            (匹配的key, 相似度)
        """
        best_match = None
        highest_confidence = 0

        for key in category_dict.keys():
            confidence = difflib.SequenceMatcher(None, name, key).ratio()
            if confidence > highest_confidence:
                highest_confidence = confidence
                best_match = key

        return best_match, highest_confidence


def __debug():
    """调试函数"""
    service = TranslationService()
    print("=== TranslationService Debug ===")
    print(f"角色数量: {len(service.translation_dict.get('character', {}))}")
    print(f"驱动盘数量: {len(service.translation_dict.get('equipment', {}))}")
    print(f"音擎数量: {len(service.translation_dict.get('weapon', {}))}")
    print(f"\n测试翻译:")
    print(f"安比 -> {service.translate_character('安比')}")
    print(f"原始朋克 -> {service.translate_equipment('原始朋克')}")
    print(f"硫磺石 -> {service.translate_weapon('硫磺石')}")


if __name__ == "__main__":
    __debug()