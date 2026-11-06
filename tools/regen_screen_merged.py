"""重生成 _od_merged.yml（运行时唯一加载的画面区域合并文件）

背景：
- 框架运行时只读 assets/game_data/screen_info/_od_merged.yml，往分离文件
  （如 drive_disc_dismantle.yml）新增区域后必须重生成合并文件才会生效。
- ScreenContext 的工作目录由 os_utils.get_work_dir() 解析：源码运行时取
  模块所在项目根，因此指定 PYTHONPATH 与 cwd 即可在任意实例内自跑；
  本脚本默认在仓库根目录内自跑，不再依赖 app 运行实例。

用法：
    .venv/Scripts/python.exe tools/regen_screen_merged.py
    .venv/Scripts/python.exe tools/regen_screen_merged.py --root E:\\Z1D\\app

2026-10-27 拆解修复时手工完成过一次（提交 1012a1f1），本脚本固化该步骤。
2026-10-30 参数化：根目录默认改为本仓根，--root 可指向其他实例。
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MERGED_REL = Path('assets') / 'game_data' / 'screen_info' / '_od_merged.yml'

REGEN_SNIPPET = '''
from one_dragon.base.screen.screen_loader import ScreenContext
sc = ScreenContext()
sc.reload(from_separated_files=True)
sc.save(reload_after_save=False)
print("merged screens:", len(sc.screen_info_list))
'''


def main() -> int:
    parser = argparse.ArgumentParser(description='重生成 _od_merged.yml')
    parser.add_argument('--root', type=Path, default=REPO_ROOT,
                        help='目标实例根目录（默认本仓根目录）')
    args = parser.parse_args()
    root = args.root.resolve()

    venv_python = root / '.venv' / 'Scripts' / 'python.exe'
    if not venv_python.exists():
        print(f'未找到 venv: {venv_python}')
        return 1

    result = subprocess.run(
        [str(venv_python), '-c', REGEN_SNIPPET],
        cwd=str(root),
        env={**os.environ, 'PYTHONPATH': str(root / 'src')},
        capture_output=True, text=True,
    )
    print(result.stdout.strip())
    if result.returncode != 0:
        print(result.stderr[-2000:])
        return 1

    print(f'已重生成: {root / MERGED_REL}')

    check = subprocess.run(['git', '-C', str(root), 'diff', '--stat', '--', MERGED_REL.as_posix()],
                           capture_output=True, text=True)
    print('git diff:', check.stdout.strip() or '(无变化)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
