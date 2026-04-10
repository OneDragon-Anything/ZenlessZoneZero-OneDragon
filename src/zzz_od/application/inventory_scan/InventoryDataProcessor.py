import json
import os
from pathlib import Path

# 导入os_utils模块
from one_dragon.utils import os_utils

class InventoryDataProcessor:
    """库存数据处理器"""
    
    # 配置单个驱动盘的理论最高分数
    MAX_DISK_SCORE = 100
    
    # 配置品质权重
    QUALITY_WEIGHTS = {
        'S': 1,
        'A': 0.67,
        'B': 0.33
    }
    
    # 配置每个部位的主词条可选池
    SLOT_MAIN_POOLS = {
            1: ['小生命'],           # 1号位固定主词条
            2: ['小攻击'],          # 2号位固定主词条
            3: ['小防御'],         # 3号位固定主词条
            4: ['攻击力', '生命值', '防御力', '暴击率', '暴击伤害', '异常精通'],  # 4号位可选主词条
            5: ['攻击力', '生命值', '防御力', '穿透率', '火属性伤害加成', '冰属性伤害加成', '电属性伤害加成', '以太伤害加成', '物理伤害加成'],  # 5号位可选主词条
            6: ['攻击力', '生命值', '防御力', '异常掌控', '冲击力', '能量自动回复'],  # 6号位可选主词条
        }
    
    # 配置主词条的增益系数
    MAIN_STAT_GAIN = {
            '攻击力': 1.67,
            '防御力': 1.67,
            '暴击率': 1.67,
            '暴击伤害': 1.67,
            '异常精通': 1.7,
            '小生命': 3.27,
            '小攻击': 2.77,
            '小防御': 2.04,
            '穿透率': 2.06,
            '异常掌控': 2.06,
            '冲击力': 2.06,
            '能量自动回复': 2.06,
            '火属性伤害加成': 1.0,
            '冰属性伤害加成': 1.0,
            '电属性伤害加成': 1.0,
            '以太伤害加成': 1.0,
            '物理伤害加成': 1.0,
        }
    
    # 配置每个部位的副词条可选池
    SUB_STATS_POOL = [
            '生命值',
            '攻击力',
            '防御力',
            '暴击率',
            '暴击伤害',
            '异常精通',
            '穿透值',
            '小生命',
            '小攻击',
            '小防御'
        ]
    
    # 配置每种品质的驱动盘的最大等级
    MAX_LEVELS = {
            'S': 15,
            'A': 12,
            'B': 9
        }
    
    # 配置每种品质的驱动盘的副词条上限
    MAX_SUB_PROPERTIES = {
            'S': 4,
            'A': 3,
            'B': 2
        }
    
    def __init__(self):
        """初始化处理器"""
        pass
    
    def load_inventory_data_files(self, inventory_data_dir):
        """加载inventory_data目录下的所有JSON文件，提取key值"""
        inventory_files = []
        inventory_path = Path(inventory_data_dir)
        
        for file_path in inventory_path.glob('*.json'):
            if file_path.name == 'agent_names.json':
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 提取key值
                    key = data.get('key', '')
                    if key:
                        inventory_files.append({
                            'file_path': str(file_path),
                            'key': key,
                            'data': data
                        })
            except Exception as e:
                print(f"加载文件 {file_path} 失败: {e}")
        
        return inventory_files
    
    def load_character_weight(self, character_weight_dir, key):
        """加载指定角色的权重配置"""
        weight_file = Path(character_weight_dir) / f"{key}.json"
        if weight_file.exists():
            try:
                with open(weight_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载权重文件 {weight_file} 失败: {e}")
        return None
    
    def load_slot_mapping(self, slot_mapping_file):
        """加载槽位映射配置"""
        try:
            with open(slot_mapping_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载槽位映射文件失败: {e}")
            return {}
    
    def convert_drive_disc_stats_to_chinese(self, drive_discs, slot_mapping):
        """将驱动盘的词条名转换为中文"""
        converted_discs = {}
        
        for slot_key, disc_data in drive_discs.items():
            converted_disc = disc_data.copy()
            
            # 转换主词条
            main_stat_key = disc_data.get('mainStatKey', '')
            if main_stat_key in slot_mapping:
                converted_disc['mainStatKeyChinese'] = slot_mapping[main_stat_key]
            
            # 转换副词条
            substats = disc_data.get('substats', [])
            converted_substats = []
            for substat in substats:
                converted_substat = substat.copy()
                stat_key = substat.get('key', '')
                if stat_key in slot_mapping:
                    converted_substat['keyChinese'] = slot_mapping[stat_key]
                converted_substats.append(converted_substat)
            
            converted_disc['substats'] = converted_substats
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
        max_level = self.MAX_LEVELS.get(rarity, 9)
        total_upgrades = max_level // 3
        max_substats = self.MAX_SUB_PROPERTIES.get(rarity, 2)
        
        # 生成所有可能的配置并计算得分
        best_config = None
        best_score = -1
        
        # 对于4-6号位，需要考虑主词条
        if 4 <= position <= 6:
            # 获取当前位置的主词条可选池
            main_pool = self.SLOT_MAIN_POOLS.get(position, [])
            
            # 尝试每个可能的主词条（从主词条可选池中选择）
            for main_stat_candidate in main_pool:
                # 检查主词条是否有权重
                if main_stat_candidate in character_weight and character_weight[main_stat_candidate] > 0:
                    main_weight = character_weight[main_stat_candidate]
                    
                    # 选择剩余权重较高的属性作为副词条，确保不与主词条重合且在副词条可选池中
                    substats = []
                    for stat, weight in weighted_stats:
                        if stat != main_stat_candidate and stat in self.SUB_STATS_POOL and len(substats) < max_substats:
                            substats.append((stat, weight))
                    
                    # 计算每个副词条的升级次数
                    # 只升级权重值最高的词条
                    substat_configs = []
                    for i, (stat, weight) in enumerate(substats):
                        if i == 0:  # 权重最高的词条
                            upgrades = 1 + total_upgrades
                        else:  # 其他词条只保持初始值
                            upgrades = 1
                        substat_configs.append({
                            'key': stat,
                            'upgrades': upgrades
                        })
                    
                    # 计算得分
                    score = 0
                    # 计算主词条得分
                    score += main_weight * (1 + total_upgrades)  # 主词条等值升级次数*权重
                    # 计算副词条得分
                    for substat in substat_configs:
                        stat_key = substat['key']
                        if stat_key in character_weight:
                            score += character_weight[stat_key] * substat['upgrades']
                    
                    # 更新最佳配置
                    if score > best_score:
                        best_score = score
                        best_config = {
                            'mainStatKey': main_stat_candidate,
                            'substats': substat_configs,
                            'maxLevel': max_level,
                            'maxSubstats': max_substats,
                            'totalUpgrades': total_upgrades,
                            'score': score
                        }
            
            # 如果没有找到符合条件的主词条，返回一个默认配置
            if best_config is None:
                # 选择权重较高的属性作为副词条，确保在副词条可选池中
                substats = []
                for stat, weight in weighted_stats:
                    if stat in self.SUB_STATS_POOL and len(substats) < max_substats:
                        substats.append((stat, weight))
                
                # 计算每个副词条的升级次数
                # 只升级权重值最高的词条
                substat_configs = []
                for i, (stat, weight) in enumerate(substats):
                    if i == 0:  # 权重最高的词条
                        upgrades = 1 + total_upgrades
                    else:  # 其他词条只保持初始值
                        upgrades = 1
                    substat_configs.append({
                        'key': stat,
                        'upgrades': upgrades
                    })
                
                # 计算得分
                score = 0
                # 计算副词条得分
                for substat in substat_configs:
                    stat_key = substat['key']
                    if stat_key in character_weight:
                        score += character_weight[stat_key] * substat['upgrades']
                
                best_config = {
                    'mainStatKey': '',
                    'substats': substat_configs,
                    'maxLevel': max_level,
                    'maxSubstats': max_substats,
                    'totalUpgrades': total_upgrades,
                    'score': score
                }
        else:
            # 1-3号位，主属性词条得分设为0
            # 选择权重较高的属性作为副词条，确保在副词条可选池中且不与主词条重合
            substats = []
            # 获取当前位置的主词条
            main_pool = self.SLOT_MAIN_POOLS.get(position, [])
            main_stat = main_pool[0] if main_pool else ''
            
            for stat, weight in weighted_stats:
                if stat in self.SUB_STATS_POOL and stat != main_stat and len(substats) < max_substats:
                    substats.append((stat, weight))
            
            # 计算每个副词条的升级次数
            # 只升级权重值最高的词条
            substat_configs = []
            for i, (stat, weight) in enumerate(substats):
                if i == 0:  # 权重最高的词条
                    upgrades = 1 + total_upgrades
                else:  # 其他词条只保持初始值
                    upgrades = 1
                substat_configs.append({
                    'key': stat,
                    'upgrades': upgrades
                })
            
            # 计算得分
            score = 0
            # 计算副词条得分
            for substat in substat_configs:
                stat_key = substat['key']
                if stat_key in character_weight:
                    score += character_weight[stat_key] * substat['upgrades']
            
            best_config = {
                'mainStatKey': '',
                'substats': substat_configs,
                'maxLevel': max_level,
                'maxSubstats': max_substats,
                'totalUpgrades': total_upgrades,
                'score': score
            }
        
        return best_config
    
    def calculate_actual_disc_score(self, disc_data, character_weight, slot_mapping):
        """计算驱动盘的实际得分
        
        Args:
            disc_data: 驱动盘数据
            character_weight: 角色权重配置
            slot_mapping: 槽位映射配置
            
        Returns:
            得分字典，包含主词条得分、副词条得分和总得分
        """
        position = disc_data.get('position', 0)
        level = disc_data.get('level', 0)
        main_stat_key = disc_data.get('mainStatKey', '')
        substats = disc_data.get('substats', [])
        
        # 转换主词条key为中文
        main_stat_key_chinese = slot_mapping.get(main_stat_key, '')
        
        # 计算主词条得分
        main_stat_score = 0
        if 4 <= position <= 6:
            main_stat_weight = character_weight.get(main_stat_key_chinese, 0)
            main_stat_score = main_stat_weight * (level // 3 + 1)
        
        # 计算副词条得分
        substat_score = 0
        valid_substats = []
        for substat in substats:
            substat_key = substat.get('key', '')
            substat_upgrades = substat.get('upgrades', 0)
            # 转换副词条key为中文
            substat_key_chinese = slot_mapping.get(substat_key, '')
            substat_weight = character_weight.get(substat_key_chinese, 0)
            substat_score += substat_weight * substat_upgrades
            # 记录有效副词条
            if substat_weight > 0:
                valid_substats.append({
                    'key': substat_key_chinese,
                    'upgrades': substat_upgrades,
                    'weight': substat_weight,
                    'score': substat_weight * substat_upgrades
                })
        
        # 总得分
        total_score = main_stat_score + substat_score

        # 计算当前位的最大得分
        max_score_config = self.calculate_optimal_disc_config(position, character_weight, disc_data.get('rarity', 'S'))
        max_score = max_score_config.get('score', 1)  # 避免除以0

        # 相对得分
        relative_score = (total_score / max_score) * self.MAX_DISK_SCORE
        
        return {
            'score_ceiling': max_score,
            'relative_score_ceiling': self.MAX_DISK_SCORE,
            'relativeScore': relative_score,
            'mainStatScore': main_stat_score,
            'substatScore': substat_score,
            'totalScore': total_score,
            'validSubstats': valid_substats
        }
    
    def process_inventory_data(self, inventory_data_dir, character_weight_dir, slot_mapping_file):
        """处理库存数据"""
        # 1. 加载inventory_data目录下的JSON文件
        inventory_files = self.load_inventory_data_files(inventory_data_dir)
        print(f"找到 {len(inventory_files)} 个库存数据文件")
        
        # 2. 加载槽位映射
        slot_mapping = self.load_slot_mapping(slot_mapping_file)
        print(f"加载了 {len(slot_mapping)} 个槽位映射")
        
        # 3. 处理每个角色数据
        processed_results = []
        for inventory_file in inventory_files:
            key = inventory_file['key']
            
            # 检查对应的权重配置文件是否存在
            character_weight = self.load_character_weight(character_weight_dir, key)
            if character_weight is None:
                print(f"跳过角色 {key}：未找到权重配置文件")
                continue
            
            print(f"\n处理角色: {key}")
            
            # 转换驱动盘词条为中文
            equipped_discs = inventory_file['data'].get('equippedDiscs', {})
            converted_discs = self.convert_drive_disc_stats_to_chinese(equipped_discs, slot_mapping)
            
            # 计算每个驱动盘的最优配置
            optimal_configs = {}
            for slot_key, disc_data in equipped_discs.items():
                position = int(slot_key)
                rarity = disc_data.get('rarity', 'S')
                optimal_config = self.calculate_optimal_disc_config(position, character_weight, rarity)
                optimal_configs[slot_key] = optimal_config
            
            # 计算实际驱动盘得分
            actual_scores = {}
            for slot_key, disc_data in equipped_discs.items():
                disc_data_with_position = disc_data.copy()
                disc_data_with_position['position'] = int(slot_key)
                actual_scores[slot_key] = self.calculate_actual_disc_score(disc_data_with_position, character_weight, slot_mapping)
            
            # 构建处理结果
            result = {
                'key': key,
                'original_file': inventory_file['file_path'],
                'character_weight': character_weight,
                'converted_drive_discs': converted_discs,
                'optimal_configs': optimal_configs,
                'actual_scores': actual_scores
            }
            processed_results.append(result)
            
            # 打印转换结果
            print(f"  驱动盘数量: {len(converted_discs)}")
            for slot_key, disc_data in converted_discs.items():
                print(f"  {slot_key}号位: {disc_data.get('setKey', '未知')}")
                print(f"    主词条: {disc_data.get('mainStatKey', '')} -> {disc_data.get('mainStatKeyChinese', '未知')}")
                print(f"    副词条数量: {len(disc_data.get('substats', []))}")
                for substat in disc_data.get('substats', []):
                    print(f"      {substat.get('key', '')} -> {substat.get('keyChinese', '未知')} (升级次数: {substat.get('upgrades', 0)})")
            
            # 打印最优配置
            print("\n  最优配置:")
            for slot_key, config in optimal_configs.items():
                print(f"  {slot_key}号位:")
                print(f"    主词条: {config['mainStatKey']}")
                print(f"    得分: {config.get('score', 0):.2f}")
                print(f"    副词条:")
                for substat in config['substats']:
                    print(f"      {substat['key']} (升级次数: {substat['upgrades']})")
                print(f"    最大等级: {config['maxLevel']}")
                print(f"    最大副词条数: {config['maxSubstats']}")
                print(f"    总升级次数: {config['totalUpgrades']}")
            
            # 打印实际得分
            print("\n  实际得分:")
            for slot_key, score_data in actual_scores.items():
                print(f"  {slot_key}号位:")
                print(f"    主词条得分: {score_data['mainStatScore']:.2f}")
                print(f"    副词条得分: {score_data['substatScore']:.2f}")
                print(f"    总得分: {score_data['totalScore']:.2f}")
                print(f"    相对得分: {score_data.get('relativeScore', '未知'):.2f}")
                print(f"    有效副词条:")
                for substat in score_data['validSubstats']:
                    print(f"      {substat['key']} (升级次数: {substat['upgrades']}, 权重: {substat['weight']:.2f}, 得分: {substat['score']:.2f})")
        
        return processed_results
    
    def main(self):
        """主函数"""
        # 定义路径
        inventory_data_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_data')
        character_weight_dir = os_utils.get_path_under_work_dir('assets', 'character_weight')
        slot_mapping_file = os_utils.get_path_under_work_dir('assets', 'character_weight', '_tool', 'slot_Mapping.json')
        
        print("=" * 60)
        print("开始处理库存数据")
        print("=" * 60)
        
        # 处理库存数据
        results = self.process_inventory_data(inventory_data_dir, character_weight_dir, slot_mapping_file)
        
        print("\n" + "=" * 60)
        print(f"处理完成！共处理 {len(results)} 个角色")
        print("=" * 60)
        
        # 保存处理结果
        output_file = os_utils.get_path_under_work_dir('.debug', 'processed_inventory_data.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"处理结果已保存到: {output_file}")

if __name__ == "__main__":
    processor = InventoryDataProcessor()
    processor.main()
