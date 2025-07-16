import os
import re

def find_yml_files(directory):
    """
    递归查找目录中的所有 .yml 文件。
    """
    yml_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".yml") or file.lower().endswith(".yaml"):
                file_path = os.path.join(root, file)
                print(f"Found: {file_path}")  # 调试信息
                yml_files.append(file_path)
    return yml_files

def convert_indent_to_spaces(content, spaces=2):
    """
    将缩进转换为指定数量的空格。
    """
    return content.expandtabs(spaces)

def trim_trailing_whitespace(content):
    """
    裁剪每行的尾随空格。
    """
    return "\n".join([line.rstrip() for line in content.splitlines()])

def ensure_newline_at_end(content):
    """
    确保文件末尾以新行结束。
    """
    if content and not content.endswith("\n"):
        content += "\n"
    return content

def ensure_document_start(content):
    """
    确保文件以 --- 开头。
    """
    if not content.lstrip().startswith("---"):
        content = "---\n" + content
    return content

def fix_comment_spacing(content):
    """
    修复注释中 # 后面缺少空格的问题。
    """
    # 使用正则表达式匹配 # 后面没有空格的情况
    fixed_content = re.sub(r"#(\S)", r"# \1", content)
    return fixed_content

def fix_comment_spacing_before(content):
    """
    修复注释中 # 前面缺少空格的问题（忽略整行注释）。
    """
    lines = content.splitlines()
    fixed_lines = []

    for line in lines:
        # 如果是以 # 开头的整行注释，直接跳过
        if line.lstrip().startswith("#"):
            fixed_lines.append(line)
        else:
            # 否则，修复非整行注释的 # 前面缺少空格的问题
            fixed_line = re.sub(r"(\S+)\s?#", r"\1  #", line)
            fixed_lines.append(fixed_line)

    return "\n".join(fixed_lines)

def fix_comma_spacing(content):
    """
    修复逗号后面缺少空格的问题。
    """
    # 使用正则表达式匹配逗号后面没有空格的情况
    fixed_content = re.sub(r",(\S)", r", \1", content)
    return fixed_content

def fix_bracket_spacing(content):
    """
    修复括号内多余空格的问题。
    """
    # 修复方括号内的多余空格
    content = re.sub(r"\[\s+", "[", content)  # 去掉 [ 后的空格
    content = re.sub(r"\s+\]", "]", content)  # 去掉 ] 前的空格

    # 修复圆括号内的多余空格
    content = re.sub(r"\(\s+", "(", content)  # 去掉 ( 后的空格
    content = re.sub(r"\s+\)", ")", content)  # 去掉 ) 前的空格

    return content

def process_file(file_path):
    """
    处理单个文件：转换缩进、裁剪尾随空格、确保末尾有新行，并修复注释空格和括号空格。
    """
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # 步骤 1：确保文件以 --- 开头 (暂未启用)
    # content = ensure_document_start(content)

    # 步骤 2：转换缩进为空格
    content = convert_indent_to_spaces(content)

    # 步骤 3：裁剪尾随空格
    content = trim_trailing_whitespace(content)

    # 步骤 4：确保文件末尾以新行结束
    content = ensure_newline_at_end(content)

    # 步骤 5：修复注释中 # 后面缺少空格的问题
    content = fix_comment_spacing(content)

    # 步骤 6：修复注释中 # 前面缺少空格的问题
    content = fix_comment_spacing_before(content)

    # 步骤 7：修复逗号后面缺少空格的问题
    content = fix_comma_spacing(content)

    # 步骤 8：修复括号内多余空格的问题
    content = fix_bracket_spacing(content)

    # 写回文件
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)

def main(directory):
    """
    主函数：递归处理目录中的所有 .yml 文件。
    """
    yml_files = find_yml_files(directory)
    for file_path in yml_files:
        print(f"Processing: {file_path}")
        process_file(file_path)
    print(f"Processed {len(yml_files)} .yml files.")

if __name__ == "__main__":
    target_directory = "."  # 当前目录
    main(target_directory)