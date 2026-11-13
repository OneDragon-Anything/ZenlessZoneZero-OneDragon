from __future__ import annotations

import atexit
import contextlib
import ctypes
import datetime
import os
import signal
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from typing import TYPE_CHECKING

from colorama import Fore, Style, init

from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import (
    LoggerConfig,
    configure_logger,
    get_log_file_path,
)
from one_dragon.utils.log_utils import (
    log as framework_log,
)

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext

PYTHON_LAUNCHER_FRAMEWORK_LOG_FILE_NAME = 'python_launcher_framework.log'

# 初始化 colorama
init(autoreset=True)


def print_message(message: str, level: str = "INFO", flush: bool = False) -> None:
    # 打印消息，带有时间戳和日志级别
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    colors = {
        "DEBUG": Fore.WHITE,
        "INFO": Fore.CYAN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.YELLOW + Style.BRIGHT,
        "PASS": Fore.GREEN,
    }
    color = colors.get(level, Fore.WHITE)
    if flush:
        print(f"{timestamp} | {color}{level}{Style.RESET_ALL} | {message}", end='\r', flush=True)
    else:
        print(f"{timestamp} | {color}{level}{Style.RESET_ALL} | {message}")


def create_git_progress_callback():
    def _report(_progress: float, message: str) -> None:
        refresh = '%' in message and 'done' not in message.lower()
        print_message(message, 'INFO', flush=refresh)

    return _report


def _configure_runtime_logger() -> None:
    if getattr(sys, 'frozen', False):
        log_dir = Path(sys.executable).resolve().parent / '.log'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = str(log_dir / PYTHON_LAUNCHER_FRAMEWORK_LOG_FILE_NAME)
    else:
        log_file_path = get_log_file_path(default_name=PYTHON_LAUNCHER_FRAMEWORK_LOG_FILE_NAME)

    configure_logger(
        framework_log,
        LoggerConfig(
            log_file_path=log_file_path,
            add_console_handler=False,
            propagate=False,
        ),
    )

def collect_path_problems(path: str) -> list[str]:
    """检查安装目录里已知会影响运行的情况。

    只做提示，不据此退出：这几项都不是启动的硬前提，出问题的是个别功能，
    用户按提示迁移安装目录即可。

    Args:
        path: 待检查的目录绝对路径。

    Returns:
        问题描述列表；空列表表示没有已知问题。
    """
    problems: list[str] = []
    if not path.isascii():
        problems.append('路径包含中文字符或其他非 ASCII 字符')
    if ' ' in path:
        problems.append('路径中存在空格')
    if '[' in path or ']' in path:
        problems.append('路径包含方括号 [ ]，启动时会被 PowerShell 当成通配符')
    return problems


def verify_working_directory() -> str:
    """切换并校验启动器工作目录。

    路径不符合建议格式时只打印提示并继续启动，不再直接退出。

    Returns:
        启动器使用的工作目录。
    """
    if getattr(sys, 'frozen', False):
        cwd = str(Path(sys.executable).resolve().parent)
    else:
        cwd = os.getcwd()

    os.chdir(cwd)
    print_message(f"当前工作目录：{cwd}", "INFO")

    problems = collect_path_problems(cwd)
    if problems:
        for problem in problems:
            print_message(problem, "WARNING")
        print_message(
            "以上只是提示，程序会继续启动；若随后出现截图保存失败、环境文件读写失败等问题，"
            "请把整个安装目录移动到纯英文且无空格的路径（例如 D:\\OneDragon）后重新运行",
            "WARNING",
        )
    else:
        print_message("目录核验通过", "PASS")

    return cwd

def configure_environment(ctx: OneDragonEnvContext, cwd):
    uv_path = ctx.env_config.uv_path
    if not uv_path or not os.path.exists(uv_path):
        print_message("获取 UV 路径失败，请运行安装程序。", "ERROR")
        sys.exit(1)

    # 配置环境变量
    print_message("开始配置环境变量...", "INFO")
    os.environ.update({
        'PYTHONPATH': os.path.join(cwd, "src"),
        'UV_DEFAULT_INDEX': ctx.env_config.pip_source,
        # uv 构建 vgamepad 时默认会弹出 ViGEmBus 驱动安装程序，启动器中跳过
        'VGAMEPAD_SKIP_VIGEMBUS_INSTALL': 'true',
    })

    for var in ['PYTHONPATH', 'UV_DEFAULT_INDEX']:
        if not os.environ.get(var):
            print_message(f"{var} 未设置", "ERROR")
            sys.exit(1)

    print_message(f"PYTHONPATH：{os.environ['PYTHONPATH']}", "PASS")
    print_message(f"UV_DEFAULT_INDEX：{os.environ['UV_DEFAULT_INDEX']}", "PASS")

def execute_python_script(
        ctx: OneDragonEnvContext,
        app_path: list[str],
        no_windows: bool,
        args: list[str] | None = None,
        piped: bool = False,
) -> None:
    uv_path = ctx.env_config.uv_path
    app_module_parts = app_path.copy()
    module_name = app_module_parts[-1]
    if module_name.endswith('.py'):
        module_name = module_name[:-3]
    app_module_parts[-1] = module_name
    app_module = '.'.join(app_module_parts)

    app_module_path = Path(os.environ.get('PYTHONPATH', '')).joinpath(*app_module_parts)
    app_file_path = app_module_path.with_suffix('.py')
    if not app_file_path.is_file():
        print_message(f"PYTHONPATH 设置错误，无法找到 {app_file_path}", "ERROR")
        sys.exit(1)

    # 构建 uv run 命令参数
    run_args = ['run', '--frozen', '-m', app_module]
    if args:
        run_args.extend(args)
        print_message(f"传递参数：{' '.join(args)}", "INFO")

    # 构建 PowerShell 命令参数列表
    def escape_powershell_arg(arg):
        # 转义 PowerShell 中的特殊字符
        return arg.replace("'", "''").replace('"', '""')

    escaped_args = [escape_powershell_arg(arg) for arg in run_args]
    arg_list = ', '.join(f"'{arg}'" for arg in escaped_args)

    if piped and os.name == 'nt':

        # 创建Job对象
        # 用于管理进程组，解决 `taskkill /f /im OneDragon-Launcher.exe` 后Python.exe进程仍然存活的问题
        # 设置JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE后， OneDragon-Launcher.exe 退出后将会kill掉所有分配进Job对象的子进程
        # （若希望进程从中jobobject逃离，则需要设置 JOB_OBJECT_LIMIT_BREAKAWAY_OK，并设置创建进程时使用 creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB）
        # https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
        # https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information
        kernel32 = ctypes.windll.kernel32
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
        JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
        JobObjectExtendedLimitInformation = 9

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        job_handle = kernel32.CreateJobObjectW(None, None)
        if not job_handle:
            raise OSError("CreateJobObjectW failed")
        job_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        job_info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
        if not kernel32.SetInformationJobObject(
            job_handle,
            JobObjectExtendedLimitInformation,
            ctypes.byref(job_info),
            ctypes.sizeof(job_info),
        ):
            kernel32.CloseHandle(job_handle)
            raise OSError("SetInformationJobObject failed")
        # 创建进程
        # stdout, stderr 设置为 None 将会输出到当前程序相应的管道中

        process = subprocess.Popen(
            [uv_path] + run_args,
            stdout=None,
            stderr=None,
            stdin=None,
            creationflags=subprocess.CREATE_NO_WINDOW if no_windows else 0,
            text=True,
            encoding='utf-8'
        )

        # 将进程加入Job对象
        if not kernel32.AssignProcessToJobObject(job_handle, process._handle):
            try:
                process.terminate()
            finally:
                kernel32.CloseHandle(job_handle)
            raise OSError("AssignProcessToJobObject failed")

        # 注册退出处理函数，当前程序退出时，尝试主动关闭Job对象
        def _cleanup():
            with contextlib.suppress(Exception):
                kernel32.CloseHandle(job_handle)
        atexit.register(_cleanup)

        # 注册信号处理，当前程序收到CTRL+C信号时，将信号传递给python子进程，这会使得 `process.wait()` 退出, 并得到返回值
        # 此时控制台打印的错误信息是子进程输出的
        def _on_signal(signum, frame):
            try:
                process.send_signal(signal.CTRL_BREAK_EVENT)
            except Exception:
                process.terminate()
        signal.signal(signal.SIGINT, _on_signal)
        with contextlib.suppress(Exception):
            signal.signal(signal.SIGTERM, _on_signal)

        # 等待进程结束
        exit_code = 0
        try:
            exit_code = process.wait()
        finally:
            ctypes.windll.kernel32.CloseHandle(job_handle)
        # 如果子进程退出码不为0，则以同样的退出码退出当前程序
        if exit_code != 0:
            sys.exit(exit_code)
    else:
        # 构建 PowerShell 命令
        powershell_command = [
            "Start-Process",
            f"'{escape_powershell_arg(uv_path)}'",
            "-ArgumentList",
            f"@({arg_list})",
            "-NoNewWindow",
            "-PassThru"
        ]
        full_command = " ".join(powershell_command)
        # 使用 subprocess.Popen 启动新的 PowerShell 窗口并执行命令
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", full_command],
            creationflags=subprocess.CREATE_NO_WINDOW if no_windows else 0
        )
        print_message("等待主界面弹出...", "INFO")

def fetch_latest_code(ctx: OneDragonEnvContext) -> None:
    """
    获取最新代码
    """
    if not ctx.env_config.auto_update_code:
        print_message(gt('未开启代码自动更新，跳过'), "INFO")
        return
    _configure_runtime_logger()
    from one_dragon.envs.git_service import GitSyncStatus

    progress_callback = create_git_progress_callback()
    status, message = ctx.git_service.fetch_latest_code(progress_callback=progress_callback)
    if status in (GitSyncStatus.SUCCESS, GitSyncStatus.UP_TO_DATE):
        level = 'PASS'
    elif status is GitSyncStatus.RUNTIME_INCOMPATIBLE:
        message = f'{message}, {gt("继续使用当前版本")}'
        level = 'WARNING'
    elif status is GitSyncStatus.BUILTIN_TAG_UNAVAILABLE:
        message = f'{message}, {gt("继续使用内置版本")}'
        level = 'WARNING'
    elif status in (GitSyncStatus.REMOTE_UNAVAILABLE, GitSyncStatus.LOCAL_CHANGES):
        message = f'{message}, {gt("继续使用当前版本")}'
        level = 'WARNING'
    elif status is GitSyncStatus.LOCAL_UPDATE_FAILED:
        message = f'{message}, {gt("请重新运行启动器；仍然失败时请重新安装")}'
        level = 'ERROR'
    else:
        message = f'{message}, {gt("请查看日志后重试")}'
        level = 'ERROR'
    print_message(message, level)


def sync_dependencies(ctx: OneDragonEnvContext) -> None:
    """按需同步运行依赖。"""
    print_message("开始检查运行环境...", "INFO")
    success, msg = ctx.python_service.uv_sync_runtime_dependencies()
    print_message(msg, "PASS" if success else "ERROR")
    if not success:
        with contextlib.suppress(EOFError):
            input("请重新启动程序；若问题仍然存在，请下载最新安装器重新配置运行环境。按回车键退出...")
        sys.exit(1)


def run_python(app_path, no_windows: bool = True, args: list[str] | None = None, piped: bool = False) -> None:
    # 主函数
    try:
        from one_dragon.version import __version__
        print_message(f"OneDragon 启动器 {__version__}", "INFO")
        cwd = verify_working_directory()
        from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
        ctx = OneDragonEnvContext(prefer_bundled_config=True)
        configure_environment(ctx, cwd)
        fetch_latest_code(ctx)
        sync_dependencies(ctx)
        execute_python_script(ctx, app_path, no_windows, args, piped)
    except SystemExit as e:
        print_message(f"程序已退出，状态码：{e.code}", "ERROR")
        raise
    except Exception as e:
        print_message(f"出现未处理的异常：{e}", "ERROR")
    finally:
        time.sleep(5)
