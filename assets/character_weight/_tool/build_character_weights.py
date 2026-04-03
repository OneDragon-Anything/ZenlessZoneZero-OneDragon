import json
import os

# 文件路径
character_weight_json = 'd:\\my\project\ZenlessZoneZero-OneDragon\\assets\\character_weight\\_character_weight.json'
character_dir = 'd:\\my\project\ZenlessZoneZero-OneDragon\\assets\\character_weight'

# 读取_character_weight.json文件
with open(character_weight_json, 'r', encoding='utf-8') as f:
    weight_data = json.load(f)

# 读取zzz_translation.json文件以获取角色中文名
with open('d:\\my\\project\\ZenlessZoneZero-OneDragon\\assets\\wiki_data\\zzz_translation.json', 'r', encoding='utf-8') as f:
    translation_data = json.load(f)

# 创建角色英文名到中文名的映射
en_to_chs_map = {}
for key, char_info in translation_data.get('character', {}).items():
    en_name = char_info.get('EN')
    chs_name = char_info.get('CHS')
    if en_name and chs_name:
        en_to_chs_map[en_name] = chs_name

# 创建默认权重数据
default_weight = {
    "生命值": 0,
    "攻击力": 1,
    "防御力": 0,
    "冲击力": 0,
    "暴击率": 0.5,
    "暴击伤害": 0.5,
    "物理伤害加成": 0,
    "异常掌控": 0,
    "异常精通": 0,
    "穿透值": 0,
    "穿透率": 0,
    "能量自动回复": 1,
    "小攻击": 0.33,
    "小生命": 0,
    "小防御": 0
}

# 遍历character_weight目录中的所有JSON文件
processed_count = 0
for file_name in os.listdir(character_dir):
    if file_name.endswith('.json') and file_name != 'character_weight.json' and file_name != '_character_weight.json':
        # 提取角色英文名（去掉.json后缀）
        en_name = file_name[:-5]  # 去掉.json后缀
        file_path = os.path.join(character_dir, file_name)
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            char_data = json.load(f)
        
        # 获取角色中文名
        chs_name = char_data.get('name')
        
        # 查找权重数据
        char_weight = None
        if chs_name in weight_data:
            # 使用现有权重数据
            char_weight = weight_data[chs_name]
            print(f"Using existing weight data for {chs_name}")
        else:
            # 使用默认权重数据
            char_weight = default_weight.copy()
            print(f"Using default weight data for {chs_name}")
        
        # 将权重数据添加到角色文件中
        char_data['weight'] = char_weight
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(char_data, f, ensure_ascii=False, indent=2)
        
        processed_count += 1

print(f"\nProcessed {processed_count} files successfully!")

# 验证更新结果
print("\nVerifying some updated files:")
# 随机选择几个文件验证
for file_name in os.listdir(character_dir)[:3]:  # 只验证前3个文件
    if file_name.endswith('.json') and file_name != 'character_weight.json' and file_name != '_character_weight.json':
        file_path = os.path.join(character_dir, file_name)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        print(f"\n{file_name}:")
        print(f"Name: {content.get('name')}")
        print(f"Has weight data: {'weight' in content}")
        if 'weight' in content:
            print(f"Weight data keys: {list(content['weight'].keys())[:5]}...")  # 只显示前5个键