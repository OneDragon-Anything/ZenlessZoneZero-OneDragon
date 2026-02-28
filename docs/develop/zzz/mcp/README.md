# ZZZ OD MCP Server

ZZZ OD MCP Server 是为绝区零游戏自动化项目定制的 MCP 服务器，提供游戏画面感知、截图、窗口操作等功能。

## 使用场景

### 场景 1：本地开发（默认方式）⭐

在游戏本机上直接使用 Claude Code，**不需要 daemon**。

```powershell
# 安装到 Claude Code
.\tools\mcp\install.ps1

# 启动 MCP Server（使用默认端口 23001）
uv run python src\zzz_mcp\zzz_mcp_server.py

# 或指定端口
uv run python src\zzz_mcp\zzz_mcp_server.py --port 9000
```

在 Claude Code 中直接使用：
```
请检查游戏窗口状态
请捕获游戏画面
```

### 场景 2：远程 SSH 开发（高级用法）⚙️

通过 SSH 远程连接到游戏电脑，**需要使用 daemon**。

详见：[Daemon 远程开发指南](remote-ssh.md)

## 快速开始（本地开发）

### 1. 安装依赖

```bash
cd D:\code\workspace\ZenlessZoneZero-OneDragon
uv sync --group dev
```

### 2. 安装 MCP Server

```powershell
# 安装到 Claude Code（默认端口 23001）
.\tools\mcp\install.ps1

# 检查安装状态
.\tools\mcp\install.ps1 -Check

# 指定端口安装
.\tools\mcp\install.ps1 -Port 9001
```

### 3. 启动 MCP Server

```powershell
# 使用默认端口（23001）
uv run python src\zzz_mcp\zzz_mcp_server.py

# 指定端口
uv run python src\zzz_mcp\zzz_mcp_server.py --port 9000

# 指定监听地址
uv run python src\zzz_mcp\zzz_mcp_server.py --host 0.0.0.0 --port 9000
```

启动后会显示：
```
============================================================
ZZZ OD MCP Server (HTTP传输方式)
============================================================

监听地址: http://127.0.0.1:23001/mcp

按 Ctrl+C 停止服务器
------------------------------------------------------------
```

### 4. 重启 Claude Code

安装完成后需要重启 Claude Code 以使配置生效。

### 5. 测试连接

在 Claude Code 中输入：
```
请调用 check_game_window 工具测试连接
```

如果成功，应该返回游戏窗口状态信息。

## 端口说明

| 服务 | 默认端口 | 说明 |
|-----|---------|------|
| ZZZ OD MCP Server | 23001 | 游戏操作服务器 |
| ZZZ OD Daemon | 23002 | 管理服务器（仅 SSH 场景） |

## 停止 MCP Server

### 方法 1：Ctrl+C

如果 MCP Server 在前台运行，直接按 `Ctrl+C` 停止。

### 方法 2：通过端口查找并停止

```powershell
# 通过端口 23001 找到进程ID并停止
$pid = (netstat -ano | Select-String ":23001.*LISTENING").ToString().Split()[-1]
Stop-Process -Id $pid -Force
```

## 可用工具

| 工具 | 说明 | 状态 |
|------|------|------|
| `check_game_window` | 检查游戏窗口状态 | ✅ |
| `capture_game_screen` | 捕获游戏画面 | ✅ |
| `open_and_enter_game` | 打开并进入游戏 | ✅ |

## 详细文档

- [安装指南](installation.md) - 详细安装步骤
- [远程 SSH 开发](remote-ssh.md) - Daemon 架构和远程开发
- [架构设计](architecture.md) - 系统架构和设计原理
- [故障排查](troubleshooting.md) - 常见问题解决
