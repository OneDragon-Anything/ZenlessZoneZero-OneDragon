# 安装指南

本文档介绍如何安装和配置 ZZZ OD MCP Server。

## 系统要求

- Windows 10/11
- Python 3.11+
- Claude Code CLI
- 绝区零游戏已安装

## 本地开发安装（默认方式）⭐

### 步骤 1：安装依赖

```bash
cd D:\code\workspace\ZenlessZoneZero-OneDragon
uv sync --group dev
```

### 步骤 2：安装 MCP Server

```powershell
# 安装到 Claude Code（默认端口 23001）
.\tools\mcp\install.ps1

# 检查安装状态
.\tools\mcp\install.ps1 -Check

# 卸载
.\tools\mcp\install.ps1 -Uninstall

# 指定端口安装
.\tools\mcp\install.ps1 -Port 9001
```

### 步骤 3：启动 MCP Server

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

### 步骤 4：重启 Claude Code

安装完成后需要重启 Claude Code 以使配置生效。

### 步骤 5：测试连接

在 Claude Code 中输入：
```
请调用 check_game_window 工具测试连接
```

如果成功，应该返回游戏窗口状态信息。

## 远程 SSH 开发安装（可选）⚙️

**如果你通过 SSH 远程连接到游戏电脑**，需要安装 Daemon。

详见：[远程 SSH 开发指南](remote-ssh.md)

## 端口配置

| 服务 | 默认端口 | 说明 | 必需 |
|-----|---------|------|------|
| ZZZ OD MCP Server | 23001 | 游戏操作服务器 | ✅ 是 |
| ZZZ OD Daemon | 23002 | 管理服务器 | ❌ 仅 SSH 场景 |

## 卸载

### 卸载 MCP Server

```powershell
# 停止 MCP Server（如果正在运行）
# 按 Ctrl+C 或通过端口查找并停止

# 卸载
.\tools\mcp\install.ps1 -Uninstall
```

### 卸载 Daemon

```powershell
# 停止 Daemon
$pid = (netstat -ano | Select-String ":23002.*LISTENING").ToString().Split()[-1]
Stop-Process -Id $pid -Force

# 卸载
.\tools\mcp\daemon\install_daemon.ps1 -Uninstall
```

## 常见问题

### 问题 1：找不到 claude 命令

确保已安装 Claude Code CLI 并在 PATH 中：
```bash
claude --version
```

### 问题 2：端口已被占用

```powershell
# 查找占用端口的进程
netstat -ano | findstr :23001

# 停止进程
$pid = (netstat -ano | Select-String ":23001.*LISTENING").ToString().Split()[-1]
Stop-Process -Id $pid -Force
```

或使用其他端口：
```powershell
# 安装到其他端口
.\tools\mcp\install.ps1 -Port 9001

# 启动时指定端口
uv run python src\zzz_mcp\zzz_mcp_server.py --port 9001
```

### 问题 3：模块导入失败

错误：`ModuleNotFoundError: No module named 'zzz_mcp'`

解决方法：
```bash
# 确保在项目根目录
cd D:\code\workspace\ZenlessZoneZero-OneDragon

# 安装依赖
uv sync --group dev
```

### 问题 4：配置未生效

1. 确认已重启 Claude Code
2. 检查配置：
   ```bash
   claude mcp list
   ```
3. 如果配置有问题，先卸载再重新安装：
   ```powershell
   .\tools\mcp\install.ps1 -Uninstall
   .\tools\mcp\install.ps1
   ```

## 验证安装

### 检查 MCP Server 状态

```powershell
# 检查端口是否监听
netstat -ano | findstr :23001
```

### 在 Claude Code 中测试

```
请调用 check_game_window 工具
```

应该返回游戏窗口状态信息。

## 下一步

- 本地开发：参考 [README.md](README.md)
- 远程 SSH 开发：参考 [远程 SSH 开发指南](remote-ssh.md)
- 架构说明：参考 [架构设计](architecture.md)
- 故障排查：参考 [故障排查](troubleshooting.md)
