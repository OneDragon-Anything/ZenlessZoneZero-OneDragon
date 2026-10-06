from one_dragon.launcher.runtime_launcher_bootstrap.launcher import (
    main as run_launcher,
)
from zzz_od.win_exe.runtime_launcher_profile import ZRuntimeLauncherProfile


def main(argv: list[str] | None = None) -> int:
    """使用绝区零项目配置启动集成启动器。"""
    return run_launcher(ZRuntimeLauncherProfile(), argv)


if __name__ == '__main__':
    raise SystemExit(main())
