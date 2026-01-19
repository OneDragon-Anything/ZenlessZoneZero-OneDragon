"""
仓库扫描器启动脚本
"""
import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
src_path = Path(__file__).parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

# 启动扫描器GUI
from zzz_od.gui.inventory_scanner_window import main

if __name__ == "__main__":
    main()
