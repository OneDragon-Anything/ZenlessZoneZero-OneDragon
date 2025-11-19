#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 PyInstaller 冻结种子脚本
扫描源码目录中的所有导入，生成 freeze_seed.py 用于 PyInstaller 依赖分析
"""

import ast
from pathlib import Path


# 常量配置
SEED_FILE_NAME = "freeze_seed.py"  # 生成的 seed 文件名
SRC_DIR_NAME = "src"  # 源码目录名
DEPLOY_DIR_NAME = "deploy"  # 部署目录名

# 项目路径
DEPLOY_DIR = Path(__file__).parent  # 当前脚本所在目录（deploy）
REPO_ROOT = DEPLOY_DIR.parent  # 仓库根目录
SRC_DIR = REPO_ROOT / SRC_DIR_NAME  # 源码目录
SEED_FILE = DEPLOY_DIR / SEED_FILE_NAME  # seed 文件路径


def get_src_roots(src_dir: Path) -> list[Path]:
    """
    获取需要扫描的源码目录
    自动扫描 src/ 下所有一级子文件夹
    """
    if not src_dir.exists():
        print(f"[warn] Source directory does not exist: {src_dir}")
        return []

    src_roots = []
    for item in src_dir.iterdir():
        if item.is_dir():
            src_roots.append(item)

    return sorted(src_roots)


def get_local_package_names(src_roots: list[Path]) -> set[str]:
    """
    获取本地包名
    基于实际扫描的目录
    """
    return {root.name for root in src_roots}


def get_top_package(name: str) -> str:
    """获取模块的顶级包名"""
    return name.split(".", 1)[0] if name else ""


def collect_imports_from_file(py: Path, repo_root: Path) -> tuple[set[str], dict[str, set[str]]]:
    """
    返回该文件中出现的导入信息

    Returns:
        (import_stmts, from_imports)
        - import_stmts: 'import xxx' 语句的模块名集合
        - from_imports: {module: {name1, name2, ...}} 的字典
    """
    imports: set[str] = set()
    from_imports: dict[str, set[str]] = {}

    try:
        src = py.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src, filename=str(py))
    except SyntaxError as e:
        print(f"[warn] Syntax error {py.relative_to(repo_root)}: {e}")
        return imports, from_imports
    except Exception as e:
        print(f"[warn] Parsing failed {py.relative_to(repo_root)}: {e}")
        return imports, from_imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    name = alias.name.strip()
                    if name:
                        imports.add(name)
        elif isinstance(node, ast.ImportFrom):
            # 跳过相对导入
            if not node.level and node.module:
                module = node.module.strip()
                if module:
                    if module not in from_imports:
                        from_imports[module] = set()
                    for alias in node.names:
                        if alias.name:
                            from_imports[module].add(alias.name.strip())

    return imports, from_imports


def is_local_package(name: str, local_pkg_names: set[str]) -> bool:
    """判断 name 是否属于本地包（需要排除）"""
    if not name:
        return False
    # 相对导入标记
    if name.startswith("."):
        return True
    # 检查顶级包名
    return get_top_package(name) in local_pkg_names


def scan_all_imports(src_roots: list[Path], repo_root: Path, local_pkg_names: set[str]) -> list[str]:
    """扫描所有源码文件，收集第三方库和标准库导入"""
    # 验证源码目录存在
    missing = [p for p in src_roots if not p.is_dir()]
    if missing:
        raise SystemExit(f"[ERROR] 源码目录不存在: {', '.join(map(str, missing))}")

    all_imports: set[str] = set()
    all_from_imports: dict[str, set[str]] = {}
    py_files = []

    # 收集所有 Python 文件
    for root in src_roots:
        py_files.extend(root.rglob("*.py"))

    print(f"Scanning {len(py_files)} Python files...")

    # 解析所有文件的导入
    for py in py_files:
        imports, from_imports = collect_imports_from_file(py, repo_root)
        all_imports |= imports
        # 合并 from imports
        for module, names in from_imports.items():
            if module not in all_from_imports:
                all_from_imports[module] = set()
            all_from_imports[module] |= names

    # 生成导入语句列表
    statements = []

    # 处理 import 语句
    for module in sorted(all_imports):
        if not is_local_package(module, local_pkg_names):
            statements.append(f"import {module}")

    # 处理 from...import 语句（合并同一模块的导入）
    for module in sorted(all_from_imports.keys()):
        if module == "__future__":  # 排除 __future__
            continue
        if not is_local_package(module, local_pkg_names):
            names = sorted(all_from_imports[module])
            statements.append(f"from {module} import {', '.join(names)}")

    print(f"Found {len(statements)} external dependencies")
    return statements


def write_seed_script(seed_file: Path, mods: list[str], repo_root: Path) -> None:
    """
    生成 seed 脚本文件，用于 PyInstaller 依赖分析

    Args:
        seed_file: seed 文件路径
        mods: 完整的导入语句列表
        repo_root: 仓库根目录
    """
    if not mods:
        print("[warn] No external dependencies found")
        seed_file.write_text("# AUTO-GENERATED — DO NOT EDIT\npass\n", encoding="utf-8")
        return

    # 生成导入语句
    content = "# AUTO-GENERATED — DO NOT EDIT\n"
    content += "import sys\n"
    content += "if not getattr(sys, 'frozen', False):\n"
    for mod in mods:
        content += f"    {mod}\n"

    seed_file.write_text(content, encoding="utf-8")
    print(f"Writing -> {seed_file.relative_to(repo_root)} ({len(mods)} imports)")


def main():
    """主函数"""
    src_roots = get_src_roots(SRC_DIR)

    if not src_roots:
        print("[ERROR] No source directories found")
        return

    print(f"Found {len(src_roots)} source packages: {', '.join(r.name for r in src_roots)}")

    local_pkg_names = get_local_package_names(src_roots)

    # 扫描并生成
    mods = scan_all_imports(src_roots, REPO_ROOT, local_pkg_names)
    write_seed_script(SEED_FILE, mods, REPO_ROOT)

    print("Done!")

    return local_pkg_names


if __name__ == "__main__":
    main()
