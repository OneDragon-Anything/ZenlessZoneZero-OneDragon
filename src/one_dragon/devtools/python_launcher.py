import atexit
import ctypes
import datetime
import os
import signal
import subprocess
import sys
import time
from ctypes import wintypes

from colorama import Fore, Style, init

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext

# 初始化 colorama
init(autoreset=True)

def print_message(message, level="INFO"):
    # 打印消息，带有时间戳和日志级别
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    colors = {"INFO": Fore.CYAN, "ERROR": Fore.YELLOW + Style.BRIGHT, "PASS": Fore.GREEN}
    color = colors.get(level, Fore.WHITE)
    print(f"{timestamp} | {color}{level}{Style.RESET_ALL} | {message}")

def verify_working_directory():
    # 设置当前工作目录
    if getattr(sys, 'frozen', False):
        cwd = os.path.dirname(sys.executable)

    # 如果目录为空，使用当前工作目录
    if not cwd:
        cwd = os.getcwd()

    os.chdir(cwd)
    print_message(f"当前工作目录：{cwd}", "INFO")

    # 验证路径是否存在问题
    if any('\u4e00' <= char <= '\u9fff' for char in cwd):
        print_message("路径包含中文字符", "ERROR")
        sys.exit(1)
    if ' ' in cwd:
        print_message("路径中存在空格", "ERROR")
        sys.exit(1)
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
    })

    for var in ['PYTHONPATH', 'UV_DEFAULT_INDEX']:
        if not os.environ.get(var):
            print_message(f"{var} 未设置", "ERROR")
            sys.exit(1)

    print_message(f"PYTHONPATH：{os.environ['PYTHONPATH']}", "PASS")
    print_message(f"UV_DEFAULT_INDEX：{os.environ['UV_DEFAULT_INDEX']}", "PASS")

def execute_python_script(ctx: OneDragonEnvContext, app_path, no_windows: bool, args: list | None = None, piped: bool = False):
    app_script_path = os.environ.get('PYTHONPATH')
    for sub_path in app_path:
        app_script_path = os.path.join(app_script_path, sub_path)

    if not os.path.exists(app_script_path):
        print_message(f"PYTHONPATH 设置错误，无法找到 {app_script_path}", "ERROR")
        sys.exit(1)

    uv_path = ctx.env_config.uv_path
    # 构建 uv run 命令参数
    run_args = ['run', '--frozen', app_script_path]
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
            try:
                kernel32.CloseHandle(job_handle)
            except Exception:
                pass
        atexit.register(_cleanup)

        # 注册信号处理，当前程序收到CTRL+C信号时，将信号传递给python子进程，这会使得 `process.wait()` 退出, 并得到返回值
        # 此时控制台打印的错误信息是子进程输出的
        def _on_signal(signum, frame):
            try:
                process.send_signal(signal.CTRL_BREAK_EVENT)
            except Exception:
                process.terminate()
        signal.signal(signal.SIGINT, _on_signal)
        try:
            signal.signal(signal.SIGTERM, _on_signal)
        except Exception:
            pass

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
            ["powershell", "-Command", full_command],
            creationflags=subprocess.CREATE_NO_WINDOW if no_windows else 0
        )
        print_message("一条龙 正在启动中，大约 3+ 秒...", "INFO")

def fetch_latest_code(ctx: OneDragonEnvContext) -> None:
    """
    获取最新代码
    """
    if not ctx.env_config.auto_update:
        print_message("未开启代码自动更新 跳过", "INFO")
        return
    print_message("开始获取最新代码...", "INFO")
    success, msg = ctx.git_service.fetch_latest_code()
    if success:
        print_message("最新代码获取成功", "PASS")
    else:
        print_message(f'代码更新失败 {msg}', "ERROR")

def run_python(app_path, no_windows: bool = True, args: list | None = None, piped: bool = False):
    # 主函数
    try:
        cwd = verify_working_directory()
        ctx = OneDragonEnvContext()
        configure_environment(ctx, cwd)
        fetch_latest_code(ctx)
        execute_python_script(ctx, app_path, no_windows, args, piped)
    except SystemExit as e:
        print_message(f"程序已退出，状态码：{e.code}", "ERROR")
    except Exception as e:
        print_message(f"出现未处理的异常：{e}", "ERROR")
    finally:
        time.sleep(3)
