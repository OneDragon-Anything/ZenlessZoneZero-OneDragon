import json
import os

# 读取JSON文件
json_path = 'd:\\my\\project\\ZenlessZoneZero-OneDragon\\assets\\wiki_data\\zzz_translation.json'
character_weight_dir = 'd:\\my\\project\\ZenlessZoneZero-OneDragon\\assets\\character_weight'

# 读取并解析JSON文件
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 提取角色信息
characters = data.get('character', {})

# 创建角色英文名到中文名的映射
en_to_chs_map = {}
for key, char_info in characters.items():
    en_name = char_info.get('EN')
    chs_name = char_info.get('CHS')
    if en_name and chs_name:
        en_to_chs_map[en_name] = chs_name

# 遍历character_weight目录中的所有JSON文件
updated_count = 0
for file_name in os.listdir(character_weight_dir):
    if file_name.endswith('.json') and file_name != 'character_weight.json' and file_name != '_character_weight.json':
        # 提取角色英文名（去掉.json后缀）
        en_name = file_name[:-5]  # 去掉.json后缀
        
        # 检查是否有对应的中文名
        if en_name in en_to_chs_map:
            chs_name = en_to_chs_map[en_name]
            file_path = os.path.join(character_weight_dir, file_name)
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = json.load(f)
            
            # 更新name值为中文名
            file_content['name'] = chs_name
            
            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(file_content, f, ensure_ascii=False, indent=2)
            
            print(f"Updated {file_name}: name = {chs_name}")
            updated_count += 1
        else:
            print(f"Warning: No Chinese name found for {en_name}")

print(f"\nUpdated {updated_count} files successfully!")

# 验证更新结果
print("\nVerifying some updated files:")
# 随机选择几个文件验证
for file_name in os.listdir(character_weight_dir)[:5]:  # 只验证前5个文件
    if file_name.endswith('.json') and file_name != 'character_weight.json' and file_name != '_character_weight.json':
        file_path = os.path.join(character_weight_dir, file_name)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        print(f"{file_name}: name = {content.get('name')}")