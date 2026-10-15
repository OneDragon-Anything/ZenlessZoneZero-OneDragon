"""PyInstaller 运行时 Hook：路径注入

冻结的 bundle 只保留了启动器必需的最小模块集（one_dragon.launcher、one_dragon.version），
其余代码（业务逻辑、配置、工具等）均从磁盘上的 src/ 目录动态加载。

本 hook 在主脚本执行前运行，完成两件事：
1. 先导入冻结的 one_dragon 和 one_dragon.launcher，锁定启动器及已冻结模块
2. 把磁盘 src/ 追加到搜索路径末尾，只补齐未冻结的业务模块
"""

import sys
from pathlib import Path

_src = Path(sys.executable).parent / "src"

# NOTE: 此处的包名必须与 OneDragon-RuntimeLauncher.spec 中的 KEEP_TREES 顶层包一致。
#       修改 KEEP_TREES 新增不同顶层包前缀时，需同步更新此处。
# PyInstaller 6.10 起按 sys.path 顺序查找模块。
# 先导入冻结模块，再把磁盘 src/ 放到末尾，已冻结模块继续使用 EXE 内实现；
# 磁盘代码只补齐未被冻结的业务模块。
import one_dragon  # noqa: E402
import one_dragon.launcher  # noqa: E402

sys.path.append(str(_src))
one_dragon.__path__.append(str(_src / "one_dragon"))
one_dragon.launcher.__path__.append(str(_src / "one_dragon" / "launcher"))
