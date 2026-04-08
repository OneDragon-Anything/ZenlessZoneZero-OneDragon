import json
import os

# 读取JSON文件
json_path = 'd:\\my\\project\\ZenlessZoneZero-OneDragon\\assets\\wiki_data\\zzz_translation.json'
output_dir = 'd:\\my\\project\\ZenlessZoneZero-OneDragon\\assets\\character_weight'

# 确保输出目录存在
os.makedirs(output_dir, exist_ok=True)

# 读取并解析JSON文件
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 提取角色信息
characters = data.get('character', {})

# 为每个角色创建name.json文件
for key, char_info in characters.items():
    en_name = char_info.get('EN')
    if en_name:
        file_name = f"{en_name}.json"
        file_path = os.path.join(output_dir, file_name)
        
        # 创建内容
        content = {"name": en_name}
        
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        
        print(f"Created file: {file_path}")

print("\nAll files created successfully!")

# 列出创建的文件
print("\nFiles in character_weight directory:")
for file in os.listdir(output_dir):
    print(f"- {file}")