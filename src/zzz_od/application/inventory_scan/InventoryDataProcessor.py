import json
from pathlib import Path
from typing import Any

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from one_dragon.utils.yaml_utils import safe_load
from zzz_od.game_data.drive_disk import (
    MAX_DISK_SCORE,
    MAX_LEVELS,
    MAX_SUB_PROPERTIES,
    SLOT_MAIN_POOLS,
    SLOT_MAPPING,
    SUB_STATS_POOL,
)


class InventoryDataProcessor:
    """库存数据处理器"""

    AGENT_DATA_YAML_PATH = os_utils.get_path_under_work_dir(
        "assets", "game_data", "agent", "_od_merged.yml"
    )

    def __init__(self) -> None:
        """初始化处理器"""
        self._agent_data_cache: dict[str, Any] | None = None

    def load_inventory_data_files(self, inventory_data_dir):
        """加载inventory_data目录下的所有JSON文件，提取key值"""
        inventory_files = []
        inventory_path = Path(inventory_data_dir)

        for file_path in inventory_path.glob("*.json"):
            if file_path.name == "agent_names.json":
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                    # 提取key值
                    key = data.get("key", "")
                    if key:
                        inventory_files.append(
                            {"file_path": str(file_path), "key": key, "data": data}
                        )
            except Exception as e:
                log.error(f"加载文件 {file_path} 失败: {e}", exc_info=True)

        return inventory_files

    def _load_agent_data_from_yaml(self) -> dict[str, Any]:
        """从YAML文件加载角色数据"""
        if self._agent_data_cache is not None:
            return self._agent_data_cache

        try:
            with open(self.AGENT_DATA_YAML_PATH, encoding="utf-8") as f:
                agents = safe_load(f)
                self._agent_data_cache = {agent["code"]: agent for agent in agents}
                return self._agent_data_cache
        except Exception as e:
            log.error(f"加载角色数据YAML文件失败: {e}", exc_info=True)
            return {}

    def load_character_weight(self, key: str) -> dict[str, float] | None:
        """加载指定角色的权重配置"""
        agent_data = self._load_agent_data_from_yaml()
        agent_info = agent_data.get(key)

        if agent_info is None:
            log.warning(f"未在YAML中找到角色 {key}")
            return None

        weight = agent_info.get("weight")
        if weight is None:
            log.warning(f"角色 {key} 没有配置权重")
            return None

        return weight

    def convert_drive_disc_stats_to_chinese(self, drive_discs, slot_mapping=SLOT_MAPPING):
        """将驱动盘的词条名转换为中文"""
        converted_discs = {}

        for slot_key, disc_data in drive_discs.items():
            converted_disc = disc_data.copy()

            # 转换主词条
            main_stat_key = disc_data.get("mainStatKey", "")
            if main_stat_key in slot_mapping:
                converted_disc["mainStatKeyChinese"] = slot_mapping[main_stat_key]

            # 转换副词条
            substats = disc_data.get("substats", [])
            converted_substats = []

            # 获取驱动盘品质
            rarity = disc_data.get("rarity", "B")
            # 获取该品质的最大副词条数量
            max_substats = MAX_SUB_PROPERTIES.get(rarity, 2)

            for substat in substats:
                # 检查是否达到最大副词条数量
                if len(converted_substats) >= max_substats:
                    break

                converted_substat = substat.copy()
                stat_key = substat.get("key", "")

                # 转换为中文
                if stat_key in slot_mapping:
                    converted_substat["keyChinese"] = slot_mapping[stat_key]
                    # 检查是否在副词条池中
                    if converted_substat["keyChinese"] in SUB_STATS_POOL:
                        converted_substats.append(converted_substat)

            converted_disc["substats"] = converted_substats
            converted_discs[slot_key] = converted_disc

        return converted_discs

    def calculate_optimal_disc_config(self, position, character_weight, rarity):
        """计算驱动盘的最优配置

        Args:
            position: 驱动盘位置（1-6）
            character_weight: 角色权重配置
            rarity: 驱动盘品质

        Returns:
            最优配置字典，包含主词条和副词条
        """
        # 过滤出权重大于0的属性
        weighted_stats = []
        for stat, weight in character_weight.items():
            if weight > 0:
                weighted_stats.append((stat, weight))

        # 按权重降序排序
        weighted_stats.sort(key=lambda x: x[1], reverse=True)

        # 计算升级次数
        max_level = MAX_LEVELS.get(rarity, 9)
        total_upgrades = max_level // 3
        max_substats = MAX_SUB_PROPERTIES.get(rarity, 2)

        # 生成所有可能的配置并计算得分
        best_config = None
        best_score = -1

        # 对于4-6号位，需要考虑主词条
        if 4 <= position <= 6:
            # 获取当前位置的主词条可选池
            main_pool = SLOT_MAIN_POOLS.get(position, [])

            # 尝试每个可能的主词条（从主词条可选池中选择）
            for main_stat_candidate in main_pool:
                # 检查主词条是否有权重
                if (
                    main_stat_candidate in character_weight
                    and character_weight[main_stat_candidate] > 0
                ):
                    main_weight = character_weight[main_stat_candidate]

                    # 选择剩余权重较高的属性作为副词条，确保不与主词条重合且在副词条可选池中
                    substats = []
                    for stat, weight in weighted_stats:
                        if (
                            stat != main_stat_candidate
                            and stat in SUB_STATS_POOL
                            and len(substats) < max_substats
                        ):
                            substats.append((stat, weight))

                    # 计算每个副词条的升级次数
                    # 只升级权重值最高的词条
                    substat_configs = []
                    for i, (stat, weight) in enumerate(substats):
                        if i == 0:  # 权重最高的词条
                            upgrades = 1 + total_upgrades
                        else:  # 其他词条只保持初始值
                            upgrades = 1
                        substat_configs.append({"key": stat, "upgrades": upgrades})

                    # 计算得分
                    score = 0
                    # 计算主词条得分
                    score += main_weight * (
                        1 + total_upgrades
                    )  # 主词条等值升级次数*权重
                    # 计算副词条得分
                    for substat in substat_configs:
                        stat_key = substat["key"]
                        if stat_key in character_weight:
                            score += character_weight[stat_key] * substat["upgrades"]

                    # 更新最佳配置
                    if score > best_score:
                        best_score = score
                        best_config = {
                            "mainStatKey": main_stat_candidate,
                            "substats": substat_configs,
                            "maxLevel": max_level,
                            "maxSubstats": max_substats,
                            "totalUpgrades": total_upgrades,
                            "score": score,
                        }

            # 如果没有找到符合条件的主词条，返回一个默认配置
            if best_config is None:
                # 选择权重较高的属性作为副词条，确保在副词条可选池中
                substats = []
                for stat, weight in weighted_stats:
                    if stat in SUB_STATS_POOL and len(substats) < max_substats:
                        substats.append((stat, weight))

                # 计算每个副词条的升级次数
                # 只升级权重值最高的词条
                substat_configs = []
                for i, (stat, weight) in enumerate(substats):
                    if i == 0:  # 权重最高的词条
                        upgrades = 1 + total_upgrades
                    else:  # 其他词条只保持初始值
                        upgrades = 1
                    substat_configs.append({"key": stat, "upgrades": upgrades})

                # 计算得分
                score = 0
                # 计算副词条得分
                for substat in substat_configs:
                    stat_key = substat["key"]
                    if stat_key in character_weight:
                        score += character_weight[stat_key] * substat["upgrades"]

                best_config = {
                    "mainStatKey": "",
                    "substats": substat_configs,
                    "maxLevel": max_level,
                    "maxSubstats": max_substats,
                    "totalUpgrades": total_upgrades,
                    "score": score,
                }
        else:
            # 1-3号位，主属性词条得分设为0
            # 选择权重较高的属性作为副词条，确保在副词条可选池中且不与主词条重合
            substats = []
            # 获取当前位置的主词条
            main_pool = SLOT_MAIN_POOLS.get(position, [])
            main_stat = main_pool[0] if main_pool else ""

            for stat, weight in weighted_stats:
                if (
                    stat in SUB_STATS_POOL
                    and stat != main_stat
                    and len(substats) < max_substats
                ):
                    substats.append((stat, weight))

            # 计算每个副词条的升级次数
            # 只升级权重值最高的词条
            substat_configs = []
            for i, (stat, weight) in enumerate(substats):
                if i == 0:  # 权重最高的词条
                    upgrades = 1 + total_upgrades
                else:  # 其他词条只保持初始值
                    upgrades = 1
                substat_configs.append({"key": stat, "upgrades": upgrades})

            # 计算得分
            score = 0
            # 计算副词条得分
            for substat in substat_configs:
                stat_key = substat["key"]
                if stat_key in character_weight:
                    score += character_weight[stat_key] * substat["upgrades"]

            best_config = {
                "mainStatKey": "",
                "substats": substat_configs,
                "maxLevel": max_level,
                "maxSubstats": max_substats,
                "totalUpgrades": total_upgrades,
                "score": score,
            }

        return best_config

    def calculate_actual_disc_score(
        self, disc_data, character_weight, slot_mapping=SLOT_MAPPING
    ):
        """计算驱动盘的实际得分

        Args:
            disc_data: 驱动盘数据
            character_weight: 角色权重配置
            slot_mapping: 槽位映射配置

        Returns:
            得分字典，包含主词条得分、副词条得分和总得分
        """
        position = disc_data.get("position", 0)
        level = disc_data.get("level", 0)
        main_stat_key = disc_data.get("mainStatKey", "")
        substats = disc_data.get("substats", [])

        # 转换主词条key为中文
        main_stat_key_chinese = slot_mapping.get(main_stat_key, "")

        # 计算主词条得分
        main_stat_score = 0
        if 4 <= position <= 6:
            main_stat_weight = character_weight.get(main_stat_key_chinese, 0)
            main_stat_score = main_stat_weight * (level // 3 + 1)

        # 计算副词条得分
        substat_score = 0
        valid_substats = []
        for substat in substats:
            substat_key = substat.get("key", "")
            substat_upgrades = substat.get("upgrades", 0)
            # 转换副词条key为中文
            substat_key_chinese = slot_mapping.get(substat_key, "")
            substat_weight = character_weight.get(substat_key_chinese, 0)
            substat_score += substat_weight * substat_upgrades
            # 记录有效副词条
            if substat_weight > 0:
                valid_substats.append(
                    {
                        "key": substat_key_chinese,
                        "upgrades": substat_upgrades,
                        "weight": substat_weight,
                        "score": substat_weight * substat_upgrades,
                    }
                )

        # 总得分
        total_score = main_stat_score + substat_score

        # 计算当前位的最大得分
        max_score_config = self.calculate_optimal_disc_config(
            position, character_weight, disc_data.get("rarity", "S")
        )
        max_score = max_score_config.get("score", 1)  # 避免除以0

        # 相对得分
        relative_score = (total_score / max_score) * MAX_DISK_SCORE

        return {
            "score_ceiling": max_score,
            "relative_score_ceiling": MAX_DISK_SCORE,
            "relativeScore": relative_score,
            "mainStatScore": main_stat_score,
            "substatScore": substat_score,
            "totalScore": total_score,
            "validSubstats": valid_substats,
        }

    def calculate_disc_score_formatted(
        self,
        disc_data: dict[str, Any],
        character_weight: dict[str, float],
        slot_mapping: dict[str, str] | None = None,
        round_digits: int = 2,
    ) -> dict[str, Any]:
        """
        计算驱动盘评分并返回格式化结果（便捷方法）

        封装了 calculate_actual_disc_score 方法，自动处理 position 字段和结果格式化

        Args:
            disc_data: 驱动盘数据，需包含 slotKey 或 position 字段
            character_weight: 角色权重配置
            slot_mapping: 槽位映射配置，默认使用 SLOT_MAPPING
            round_digits: 保留小数位数，默认 2

        Returns:
            格式化后的评分字典，包含：
            - relativeScore: 相对得分
            - totalScore: 总得分
            - mainStatScore: 主词条得分
            - substatScore: 副词条得分
            - maxScore: 最大得分上限
            - validSubstats: 有效副词条列表
        """
        if slot_mapping is None:
            slot_mapping = SLOT_MAPPING

        disc_data_copy = disc_data.copy()

        if "position" not in disc_data_copy:
            slot_key = disc_data.get("slotKey", "1")
            disc_data_copy["position"] = int(slot_key) if str(slot_key).isdigit() else 1

        score_result = self.calculate_actual_disc_score(
            disc_data_copy, character_weight, slot_mapping
        )

        return {
            "relativeScore": round(score_result["relativeScore"], round_digits),
            "totalScore": round(score_result["totalScore"], round_digits),
            "mainStatScore": round(score_result["mainStatScore"], round_digits),
            "substatScore": round(score_result["substatScore"], round_digits),
            "maxScore": round(score_result["score_ceiling"], round_digits),
            "validSubstats": score_result["validSubstats"],
        }

    def process_inventory_data(
        self, inventory_data_dir: str
    ) -> list[dict[str, Any]]:
        """处理库存数据"""
        # 1. 加载 inventory_data 目录下的 JSON 文件
        inventory_files = self.load_inventory_data_files(inventory_data_dir)
        log.info(f"找到 {len(inventory_files)} 个库存数据文件")

        # 2. 处理每个角色数据
        processed_results = []
        for inventory_file in inventory_files:
            key = inventory_file["key"]

            # 检查对应的权重配置文件是否存在
            character_weight = self.load_character_weight(key)
            if character_weight is None:
                log.info(f"跳过角色 {key}：未找到权重配置文件")
                continue

            log.info(f"处理角色: {key}")

            # 转换驱动盘词条为中文
            equipped_discs = inventory_file["data"].get("equippedDiscs", {})
            converted_discs = self.convert_drive_disc_stats_to_chinese(equipped_discs)

            # 计算每个驱动盘的最优配置
            optimal_configs = {}
            for slot_key, disc_data in equipped_discs.items():
                position = int(slot_key)
                rarity = disc_data.get("rarity", "S")
                optimal_config = self.calculate_optimal_disc_config(
                    position, character_weight, rarity
                )
                optimal_configs[slot_key] = optimal_config

            # 计算实际驱动盘得分
            actual_scores = {}
            for slot_key, disc_data in equipped_discs.items():
                disc_data_with_position = disc_data.copy()
                disc_data_with_position["position"] = int(slot_key)
                actual_scores[slot_key] = self.calculate_actual_disc_score(
                    disc_data_with_position, character_weight
                )

            # 构建处理结果
            result = {
                "key": key,
                "original_file": inventory_file["file_path"],
                "character_weight": character_weight,
                "converted_drive_discs": converted_discs,
                "optimal_configs": optimal_configs,
                "actual_scores": actual_scores,
            }
            processed_results.append(result)

            log.debug(f"驱动盘数量: {len(converted_discs)}")
            for slot_key, disc_data in converted_discs.items():
                log.debug(f"{slot_key}号位: {disc_data.get('setKey', '未知')}")
                log.debug(
                    f"  主词条: {disc_data.get('mainStatKey', '')} -> {disc_data.get('mainStatKeyChinese', '未知')}"
                )
                log.debug(f"  副词条数量: {len(disc_data.get('substats', []))}")
                for substat in disc_data.get("substats", []):
                    log.debug(
                        f"    {substat.get('key', '')} -> {substat.get('keyChinese', '未知')} (升级次数: {substat.get('upgrades', 0)})"
                    )

            log.debug("最优配置:")
            for slot_key, config in optimal_configs.items():
                log.debug(f"{slot_key}号位:")
                log.debug(f"  主词条: {config['mainStatKey']}")
                log.debug(f"  得分: {config.get('score', 0):.2f}")
                log.debug("  副词条:")
                for substat in config["substats"]:
                    log.debug(f"    {substat['key']} (升级次数: {substat['upgrades']})")
                log.debug(f"  最大等级: {config['maxLevel']}")
                log.debug(f"  最大副词条数: {config['maxSubstats']}")
                log.debug(f"  总升级次数: {config['totalUpgrades']}")

            log.debug("实际得分:")
            for slot_key, score_data in actual_scores.items():
                log.debug(f"{slot_key}号位:")
                log.debug(f"  主词条得分: {score_data['mainStatScore']:.2f}")
                log.debug(f"  副词条得分: {score_data['substatScore']:.2f}")
                log.debug(f"  总得分: {score_data['totalScore']:.2f}")
                log.debug(f"  相对得分: {score_data.get('relativeScore', '未知'):.2f}")
                log.debug("  有效副词条:")
                for substat in score_data["validSubstats"]:
                    log.debug(
                        f"    {substat['key']} (升级次数: {substat['upgrades']}, 权重: {substat['weight']:.2f}, 得分: {substat['score']:.2f})"
                    )

        return processed_results

    def main(self):
        """主函数"""
        inventory_data_dir = os_utils.get_path_under_work_dir(
            ".debug", "inventory_data"
        )

        print("=" * 60)
        print("开始处理库存数据")
        print("=" * 60)

        # 处理库存数据
        results = self.process_inventory_data(inventory_data_dir)

        print("\n" + "=" * 60)
        print(f"处理完成！共处理 {len(results)} 个角色")
        print("=" * 60)

        # 保存处理结果
        output_file = os_utils.get_path_under_work_dir(
            ".debug", "processed_inventory_data.json"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"处理结果已保存到: {output_file}")


if __name__ == "__main__":
    processor = InventoryDataProcessor()
    processor.main()
