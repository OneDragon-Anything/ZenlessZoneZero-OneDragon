"""PyInstaller 运行时 Hook：路径注入

冻结的 bundle 只保留了启动器必需的最小模块集（one_dragon.launcher、one_dragon.version），
其余代码（业务逻辑、配置、工具等）均从磁盘上的 src/ 目录动态加载。

本 hook 在主脚本执行前运行，完成两件事：
1. 将 src/ 加入 sys.path，使 zzz_od、one_dragon_qt 等顶层包可被导入
2. 将 src/one_dragon 追加到冻结 one_dragon 包的 __path__，
   使其能找到未冻结的子模块（envs、utils 等）
"""

import sys
from pathlib import Path

_src = Path(sys.executable).parent / "src"

sys.path.insert(0, str(_src))

# NOTE: 此处的包名必须与 OneDragon-RuntimeLauncher.spec 中的 KEEP_TREES 顶层包一致。
#       修改 KEEP_TREES 新增不同顶层包前缀时，需同步更新此处。
import one_dragon
one_dragon.__path__.append(str(_src / "one_dragon"))
