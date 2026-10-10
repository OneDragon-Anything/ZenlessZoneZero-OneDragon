"""PyInstaller 运行时 Hook：路径注入

冻结的 bundle 只保留了启动器必需的最小模块集（one_dragon.launcher、one_dragon.version），
其余代码（业务逻辑、配置、工具等）均从磁盘上的 src/ 目录动态加载。

本 hook 在主脚本执行前运行，完成两件事：
1. 将 src/ 加入 sys.path，使 zzz_od、one_dragon_qt 等顶层包可被导入
2. 将 src/one_dragon 追加到冻结 one_dragon 包的 __path__，
   使其能找到未冻结的子模块（envs、utils 等）

注意：import one_dragon 必须发生在 sys.path 注入之前。否则磁盘上的 src/one_dragon
会抢先成为 one_dragon 包，冻结的 one_dragon.version 会被磁盘副本顶掉；而磁盘副本
在每次代码同步后都会变回占位符 v0.0.0，启动器就读不到自己的真实版本号了。
"""

import sys
from pathlib import Path

# NOTE: 此处的包名必须与 OneDragon-RuntimeLauncher.spec 中的 KEEP_TREES 顶层包一致。
#       修改 KEEP_TREES 新增不同顶层包前缀时，需同步更新此处。
import one_dragon
import one_dragon.launcher
import one_dragon.version

_src = Path(sys.executable).parent / "src"

sys.path.insert(0, str(_src))

one_dragon.__path__.append(str(_src / "one_dragon"))
one_dragon.launcher.__path__.append(str(_src / "one_dragon" / "launcher"))
