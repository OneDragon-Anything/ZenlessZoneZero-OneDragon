"""PyInstaller 运行时 Hook：路径注入

冻结的 bundle 只保留了启动器必需的最小模块集（one_dragon.launcher、one_dragon.version），
其余代码（业务逻辑、配置、工具等）均从磁盘上的 src/ 目录动态加载。

本 hook 在主脚本执行前运行，完成三件事：
1. 先导入冻结的 one_dragon 和 one_dragon.launcher，锁定启动器版本等冻结模块
2. 把磁盘 src/ 放到搜索路径前面，让 zzz_od 等未冻结业务包优先使用磁盘代码
3. 将磁盘 src/one_dragon 追加到冻结包路径末尾，只补齐未冻结的 one_dragon 子模块
"""

import sys
from pathlib import Path

_src = Path(sys.executable).parent / "src"

# NOTE: 此处的包名必须与 OneDragon-RuntimeLauncher.spec 中的 KEEP_TREES 顶层包一致。
#       修改 KEEP_TREES 新增不同顶层包前缀时，需同步更新此处。
# 先导入冻结模块，解释器会记住它们的冻结模块对象。
# 随后即使把磁盘 src/ 放到 sys.path 前面，也不会改用磁盘上的 one_dragon.version。
import one_dragon  # noqa: E402
import one_dragon.launcher  # noqa: E402

sys.path.insert(0, str(_src))
one_dragon.__path__.append(str(_src / "one_dragon"))
one_dragon.launcher.__path__.append(str(_src / "one_dragon" / "launcher"))
