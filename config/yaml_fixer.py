import os
import re

def fix_yaml_file(file_path):
    """修复单个YAML文件的格式问题"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 统一换行符为LF
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # 2. 修复行内注释前的空格（确保至少1个空格）
    content = re.sub(r'([^\s])\s*#', r'\1 #', content)
    
    with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)

def process_directory(directory):
    """递归处理目录下所有.yml文件"""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.yml'):
                file_path = os.path.join(root, file)
                print(f"正在处理: {file_path}")
                try:
                    fix_yaml_file(file_path)
                except Exception as e:
                    print(f"处理失败: {file_path} - {str(e)}")

if __name__ == '__main__':
    # 设置要处理的根目录
    target_dir = r'e:\github\pack\2025-04-04\config'
    if os.path.exists(target_dir):
        process_directory(target_dir)
        print("所有YAML文件处理完成！")
    else:
        print(f"目录不存在: {target_dir}")