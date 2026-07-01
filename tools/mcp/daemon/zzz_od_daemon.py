"""ZZZ OD 后端管理 daemon。

轻量级管理服务器,长期运行在游戏本机 Session 1(交互式桌面、管理员权限),
用于管理主 MCP server(``zzz_od.backend.entry.server``,默认端口 23001)的启停。

远程 SSH 场景下,Claude Code 挂载本 daemon(默认端口 23000),经它的 tool
间接 start/stop/restart/status 主 server——主 server 由 daemon 在 Session 1
拉起、继承管理员权限,才能操作游戏(绕开 SSH 的 Session 0 隔离)。
"""

import subprocess
import time
from pathlib import Path

import psutil
import uvicorn
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ZZZ OD Server Manage")

# 配置
# 本文件位于 tools/mcp/daemon/，向上 3 级到项目根
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# 主 MCP server 默认端口（start tool 的 port 参数默认值；区别于 daemon 自身监听端口）
MCP_SERVER_PORT = 23001


def find_zzz_od_mcp_server_process() -> psutil.Process | None:
    """按命令行匹配查找运行中的主 MCP server 进程。

    通过全局进程枚举按命令行特征(``zzz_od.backend.entry.server``)匹配,
    不依赖易失的 ``Popen`` handle,故 daemon 自身重启后仍能找回主 server。

    Returns:
        主 server 进程;未找到时返回 ``None``。
    """
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('zzz_od.backend.entry.server' in arg for arg in cmdline):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def _get_server_port(proc: psutil.Process) -> int | None:
    """从主 server 进程命令行解析 ``--port``。

    Args:
        proc: 主 server 进程。

    Returns:
        解析到的端口;解析失败或无法读取时返回 ``None``。
    """
    try:
        cmdline = proc.cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None
    for i, arg in enumerate(cmdline):
        if arg == '--port' and i + 1 < len(cmdline):
            try:
                return int(cmdline[i + 1])
            except ValueError:
                return None
    return None


def is_port_in_use(port: int) -> bool:
    """检查端口是否处于监听状态。"""
    for conn in psutil.net_connections(kind='inet'):
        if conn.laddr and conn.laddr.port == port and conn.status == 'LISTEN':
            return True
    return False


@mcp.tool()
def start_zzz_od_mcp_server(port: int = MCP_SERVER_PORT) -> str:
    """启动主 MCP server(游戏操作),在 Session 1 拉起。

    Args:
        port: 主 server 监听端口,默认 23001。

    Returns:
        启动结果信息。
    """
    existing_proc = find_zzz_od_mcp_server_process()
    if existing_proc:
        return f"[OK] 主 MCP server 已在运行 (PID: {existing_proc.pid})"

    if is_port_in_use(port):
        return f"[WARN] 端口 {port} 已被占用，可能有其他程序在使用"

    try:
        # 输出重定向到日志文件:长驻 server 若用 PIPE 且不持续消费,buffer 满会阻塞子进程
        log_path = PROJECT_ROOT / '.debug' / 'zzz_od_mcp' / 'main_server.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, 'w', encoding='utf-8')  # noqa: SIM115 daemon 持有,生命周期内不 close
        cmd = [
            'uv', 'run', '--env-file', '.env',
            'python', '-m', 'zzz_od.backend.entry.server', '--port', str(port),
        ]
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

        time.sleep(2)

        if process.poll() is None:
            return f"[SUCCESS] 主 MCP server 启动成功 (PID: {process.pid})\n端口: {port}\n日志: {log_path}"
        return f"[ERROR] 启动失败(返回码 {process.returncode})\n日志: {log_path}"

    except Exception as e:
        return f"[ERROR] 启动异常: {e}"


@mcp.tool()
def stop_zzz_od_mcp_server() -> str:
    """停止主 MCP server(含其子进程)。"""
    proc = find_zzz_od_mcp_server_process()

    if not proc:
        if is_port_in_use(MCP_SERVER_PORT):
            return f"[WARN] 未找到主 MCP server 进程，但端口 {MCP_SERVER_PORT} 被占用"
        return "[OK] 主 MCP server 未运行"

    try:
        children = proc.children(recursive=True)
        for child in children:
            child.terminate()
        proc.terminate()

        gone, alive = psutil.wait_procs([proc] + children, timeout=5)

        if alive:
            for p in alive:
                p.kill()

        return f"[SUCCESS] 主 MCP server 已停止 (PID: {proc.pid})"

    except psutil.NoSuchProcess:
        return "[OK] 主 MCP server 已停止"
    except Exception as e:
        return f"[ERROR] 停止失败: {e}"


@mcp.tool()
def restart_zzz_od_mcp_server() -> str:
    """重启主 MCP server(先停再启,沿用原监听端口)。"""
    # 停止前读取当前端口,重启后沿用,避免非默认端口被静默改回 23001
    proc = find_zzz_od_mcp_server_process()
    port = _get_server_port(proc) if proc else None

    stop_result = stop_zzz_od_mcp_server()

    if "[ERROR]" in stop_result:
        return f"[ERROR] 重启失败 - 停止阶段出错:\n{stop_result}"

    time.sleep(2)

    start_result = (
        start_zzz_od_mcp_server(port) if port is not None
        else start_zzz_od_mcp_server()
    )

    return f"[RESTART]\n{stop_result}\n{start_result}"


@mcp.tool()
def get_zzz_od_mcp_server_status() -> str:
    """查看主 MCP server 运行状态。"""
    proc = find_zzz_od_mcp_server_process()

    if not proc:
        port_status = "占用" if is_port_in_use(MCP_SERVER_PORT) else "空闲"
        return f"[STATUS] 主 MCP server 未运行\n端口 {MCP_SERVER_PORT}: {port_status}"

    try:
        with proc.oneshot():
            pid = proc.pid
            create_time = time.ctime(proc.create_time())
            cpu_percent = proc.cpu_percent(interval=0.1)
            memory_info = proc.memory_info()
            children = len(proc.children(recursive=True))
            server_port = _get_server_port(proc)

            return f"""[STATUS] 主 MCP server 运行中
PID: {pid}
启动时间: {create_time}
CPU 使用: {cpu_percent}%
内存使用: {memory_info.rss / 1024 / 1024:.2f} MB
子进程数: {children}
端口: {server_port if server_port is not None else '未知(见进程命令行)'}"""

    except Exception as e:
        return f"[STATUS] 主 MCP server 运行中 (PID: {proc.pid})\n[ERROR] 无法获取详细信息: {e}"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='ZZZ OD 后端管理 daemon')
    parser.add_argument('--host', default='127.0.0.1', help='监听地址')
    parser.add_argument('--port', type=int, default=23000, help='监听端口')
    args = parser.parse_args()

    print("=" * 60)
    print("ZZZ OD 后端管理 daemon")
    print("=" * 60)
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"\n管理服务器地址: http://{args.host}:{args.port}/mcp")
    print("\n可用工具:")
    print("  - start_zzz_od_mcp_server: 启动主 MCP server")
    print("  - stop_zzz_od_mcp_server: 停止主 MCP server")
    print("  - restart_zzz_od_mcp_server: 重启主 MCP server")
    print("  - get_zzz_od_mcp_server_status: 查看主 MCP server 状态")
    print("\n" + "=" * 60)

    app = mcp.streamable_http_app()
    uvicorn.run(app, host=args.host, port=args.port)
