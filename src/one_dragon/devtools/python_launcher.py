import sys
import time

import datetime
import os
import subprocess
import yaml
from colorama import init, Fore, Style

# 初始化 colorama
init(autoreset=True)

# 设置当前工作目录
# 最后exe存放的目录
path = os.path.dirname(sys.argv[0])
os.chdir(path)

def print_message(message, level="INFO"):
    # 打印消息，带有时间戳和日志级别
    delay(0.1)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    colors = {"INFO": Fore.CYAN, "ERROR": Fore.YELLOW + Style.BRIGHT, "PASS": Fore.GREEN}
    color = colors.get(level, Fore.WHITE)
    print(f"{timestamp} | {color}{level}{Style.RESET_ALL} | {message}")

def delay(seconds):
    # 暂停指定的秒数
    time.sleep(seconds)

def verify_path_issues():
    # 验证路径是否存在问题
    if any('\u4e00' <= char <= '\u9fff' for char in path):
        print_message("路径包含中文字符", "ERROR")
        sys.exit(1)
    if ' ' in path:
        print_message("路径中存在空格", "ERROR")
        sys.exit(1)
    print_message("目录核验通过", "PASS")

def load_yaml_config(file_path):
    # 读取 YAML 配置文件
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except Exception as e:
        print_message(f"读取 YAML 文件错误：{e}", "ERROR")
        sys.exit(1)

def configure_environment():
    # 从 YAML 文件中获取可执行文件路径
    yaml_file_path = os.path.join(path, "config", "env.yml")
    print_message("读取 YAML 文件中...", "INFO")
    config = load_yaml_config(yaml_file_path)
    print_message("YAML 文件读取成功", "PASS")
    python_path = config.get('python_path')
    if not python_path or not os.path.exists(python_path):
        print_message("获取 Python 路径失败，请检查路径设置。", "ERROR")
        sys.exit(1)
    uv_path = config.get('uv_path')
    if not uv_path or not os.path.exists(uv_path):
        print_message("获取 UV 路径失败，请检查路径设置。", "ERROR")
        sys.exit(1)
    auto_update = config.get('auto_update', True)
    # 配置环境变量
    print_message("开始配置环境变量...", "INFO")
    os.environ.update({
        'PYTHON': python_path,
        'PYTHONPATH': os.path.join(path, "src"),
        'UV_PATH': uv_path,
        'UV_DEFAULT_INDEX': config.get('pip_source', 'https://mirrors.aliyun.com/pypi/simple'),
        'AUTO_UPDATE': str(auto_update).lower(),
    })
    for var in ['PYTHON', 'PYTHONPATH', 'UV_PATH', 'AUTO_UPDATE']:
        if not os.environ.get(var):
            print_message(f"{var} 未设置", "ERROR")
            sys.exit(1)
    print_message(f"PYTHON：{os.environ['PYTHON']}", "PASS")
    print_message(f"PYTHONPATH：{os.environ['PYTHONPATH']}", "PASS")

def create_log_folder():
    # 创建日志文件夹
    print_message("开始配置日志...", "INFO")
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    log_folder = os.path.join(path, ".log", date_str)
    os.makedirs(log_folder, exist_ok=True)
    print_message(f"日志文件夹路径：{log_folder}", "PASS")
    return log_folder

def clean_old_logs(log_folder):
    # 删除旧的日志文件
    for root, _, files in os.walk(log_folder):
        for file in files:
            if file.startswith('bat_') and file.endswith('.log'):
                os.remove(os.path.join(root, file))
                print_message(f"已删除旧日志文件: {file}", "PASS")

def execute_python_script(app_path, log_folder, no_windows: bool, args: list = None):
    # 执行 Python 脚本并重定向输出到日志文件
    timestamp = datetime.datetime.now().strftime("%H.%M")
    log_file_path = os.path.join(log_folder, f"python_{timestamp}.log")
    app_script_path = os.environ.get('PYTHONPATH')
    for sub_path in app_path:
        app_script_path = os.path.join(app_script_path, sub_path)

    if not os.path.exists(app_script_path):
        print_message(f"PYTHONPATH 设置错误，无法找到 {app_script_path}", "ERROR")
        sys.exit(1)

    uv_path = os.environ.get('UV_PATH')
    if not uv_path:
        print_message("UV 路径未设置", "ERROR")
        sys.exit(1)

    auto_update = os.environ.get('AUTO_UPDATE', 'true').lower() == 'true'
    if not auto_update:
        print_message("未开启代码自动更新 跳过", "INFO")
    else:
        print_message("开始获取最新代码...", "INFO")
        try:
            result = subprocess.run([uv_path, 'run', '-m', 'one_dragon.envs.git_service'])
            if result.returncode == 0:
                print_message("代码更新完成", "PASS")
            else:
                print_message(f"代码更新失败: {result.stderr}", "ERROR")
        except Exception as e:
            print_message(f"代码更新异常: {e}", "ERROR")

    # 构建 uv run 命令参数
    run_args = ['run', app_script_path]
    if args:
        run_args.extend(args)
        print_message(f"传递参数：{' '.join(args)}", "INFO")

    # 构建 PowerShell 命令参数列表
    def escape_powershell_arg(arg):
        # 转义 PowerShell 中的特殊字符
        return arg.replace("'", "''").replace('"', '""')

    escaped_args = [escape_powershell_arg(arg) for arg in run_args]
    arg_list = ', '.join(f"'{arg}'" for arg in escaped_args)

    # 构建 PowerShell 命令
    powershell_command = [
        "Start-Process",
        f"'{escape_powershell_arg(uv_path)}'",
        "-ArgumentList",
        f"@({arg_list})",
        "-NoNewWindow",
        "-RedirectStandardOutput",
        f"'{escape_powershell_arg(log_file_path)}'",
        "-PassThru"
    ]
    full_command = " ".join(powershell_command)

    # 使用 subprocess.Popen 启动新的 PowerShell 窗口并执行命令
    if no_windows:
        subprocess.Popen(["powershell", "-Command", full_command], creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        subprocess.Popen(["powershell", "-Command", full_command])
    print_message("一条龙 正在启动中，大约 3+ 秒...", "INFO")

def run_python(app_path, no_windows: bool = True, args: list = None):
    # 主函数
    try:
        print_message(f"当前工作目录：{path}", "INFO")
        verify_path_issues()
        configure_environment()
        log_folder = create_log_folder()
        clean_old_logs(log_folder)
        execute_python_script(app_path, log_folder, no_windows, args)
    except SystemExit as e:
        print_message(f"程序已退出，状态码：{e.code}", "ERROR")
    except Exception as e:
        print_message(f"出现未处理的异常：{e}", "ERROR")
    finally:
        time.sleep(3)
