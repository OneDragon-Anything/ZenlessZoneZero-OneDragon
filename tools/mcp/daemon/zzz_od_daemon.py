# -*- coding: utf-8 -*-
"""
ZZZ OD Server Management MCP Server

轻量级管理服务器，长期运行在 Session 1 中，用于管理 zzz_od MCP 服务器的启停。
"""
import subprocess
import time
import psutil
import uvicorn
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ZZZ OD Server Manage")

# 配置
PROJECT_ROOT = r"D:\code\workspace\ZenlessZoneZero-OneDragon"
MAIN_SERVER_SCRIPT = "src/zzz_mcp/zzz_mcp_server.py"
MAIN_SERVER_PORT = 23001


def find_main_server_process() -> Optional[psutil.Process]:
    """查找 zzz_od MCP 主服务器进程"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('zzz_mcp_server.py' in arg for arg in cmdline):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def is_port_in_use(port: int) -> bool:
    """检查端口是否被占用"""
    for conn in psutil.net_connections():
        if conn.laddr.port == port and conn.status == 'LISTEN':
            return True
    return False


@mcp.tool()
def start_zzz_od_server() -> str:
    """
    启动 ZZZ OD MCP 主服务器

    在 Session 1 中启动游戏操作 MCP 服务器，用于游戏窗口检测和操作。

    Returns:
        str: 启动结果信息
    """
    # 检查是否已经在运行
    existing_proc = find_main_server_process()
    if existing_proc:
        return f"[OK] ZZZ OD MCP Server 已在运行 (PID: {existing_proc.pid})"

    if is_port_in_use(MAIN_SERVER_PORT):
        return f"[WARN] 端口 {MAIN_SERVER_PORT} 已被占用，可能有其他程序在使用"

    # 启动服务器
    try:
        cmd = f'cd /d "{PROJECT_ROOT}" && uv run --env-file .env python {MAIN_SERVER_SCRIPT} --port {MAIN_SERVER_PORT}'

        # 使用 POPEN 启动，不阻塞
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )

        # 等待一下确保启动成功
        time.sleep(2)

        # 检查进程是否还在运行
        if process.poll() is None:
            return f"[SUCCESS] ZZZ OD MCP Server 启动成功 (PID: {process.pid})\n端口: {MAIN_SERVER_PORT}"
        else:
            stdout, stderr = process.communicate()
            error_msg = stderr if stderr else "未知错误"
            return f"[ERROR] 启动失败: {error_msg}"

    except Exception as e:
        return f"[ERROR] 启动异常: {str(e)}"


@mcp.tool()
def stop_zzz_od_server() -> str:
    """
    停止 ZZZ OD MCP 主服务器

    停止正在运行的 zzz_od MCP 服务器进程。

    Returns:
        str: 停止结果信息
    """
    proc = find_main_server_process()

    if not proc:
        # 检查端口是否被占用
        if is_port_in_use(MAIN_SERVER_PORT):
            return f"[WARN] 未找到 zzz_od_server 进程，但端口 {MAIN_SERVER_PORT} 被占用"
        return "[OK] ZZZ OD MCP Server 未运行"

    try:
        # 终止进程及其子进程
        children = proc.children(recursive=True)
        for child in children:
            child.terminate()
        proc.terminate()

        # 等待进程结束
        gone, alive = psutil.wait_procs([proc] + children, timeout=5)

        # 如果还有存活进程，强制杀掉
        if alive:
            for p in alive:
                p.kill()

        return f"[SUCCESS] ZZZ OD MCP Server 已停止 (PID: {proc.pid})"

    except psutil.NoSuchProcess:
        return "[OK] ZZZ OD MCP Server 已停止"
    except Exception as e:
        return f"[ERROR] 停止失败: {str(e)}"


@mcp.tool()
def restart_zzz_od_server() -> str:
    """
    重启 ZZZ OD MCP 主服务器

    先停止当前运行的服务器，然后重新启动。

    Returns:
        str: 重启结果信息
    """
    stop_result = stop_zzz_od_server()

    if "[ERROR]" in stop_result:
        return f"[ERROR] 重启失败 - 停止阶段出错:\n{stop_result}"

    # 等待端口释放
    time.sleep(2)

    start_result = start_zzz_od_server()

    return f"[RESTART]\n{stop_result}\n{start_result}"


@mcp.tool()
def get_zzz_od_server_status() -> str:
    """
    查看 ZZZ OD MCP 主服务器状态

    Returns:
        str: 服务器状态信息
    """
    proc = find_main_server_process()

    if not proc:
        port_status = "占用" if is_port_in_use(MAIN_SERVER_PORT) else "空闲"
        return f"[STATUS] ZZZ OD MCP Server 未运行\n端口 {MAIN_SERVER_PORT}: {port_status}"

    try:
        # 获取进程信息
        with proc.oneshot():
            pid = proc.pid
            create_time = time.ctime(proc.create_time())
            cpu_percent = proc.cpu_percent(interval=0.1)
            memory_info = proc.memory_info()

            # 检查子进程数量
            children = len(proc.children(recursive=True))

            status = f"""[STATUS] ZZZ OD MCP Server 运行中
PID: {pid}
启动时间: {create_time}
CPU 使用: {cpu_percent}%
内存使用: {memory_info.rss / 1024 / 1024:.2f} MB
子进程数: {children}
端口: {MAIN_SERVER_PORT}"""

            return status

    except Exception as e:
        return f"[STATUS] ZZZ OD MCP Server 运行中 (PID: {proc.pid})\n[ERROR] 无法获取详细信息: {str(e)}"


if __name__ == "__main__":
    # 运行管理服务器（HTTP stream，端口 8001）
    import argparse

    parser = argparse.ArgumentParser(description='ZZZ OD Server Management MCP Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=23002, help='Port to listen on')

    args = parser.parse_args()

    print("=" * 60)
    print("ZZZ OD Server Management MCP Server")
    print("=" * 60)
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"\n管理服务器地址: http://{args.host}:{args.port}/mcp")
    print("\n可用工具:")
    print("  - start_zzz_od_server: 启动主服务器")
    print("  - stop_zzz_od_server: 停止主服务器")
    print("  - restart_zzz_od_server: 重启主服务器")
    print("  - get_zzz_od_server_status: 查看状态")
    print("\n" + "=" * 60)

    # 获取 Starlette 应用并使用 uvicorn 运行
    app = mcp.streamable_http_app()
    uvicorn.run(app, host=args.host, port=args.port)
