# ZZZ OD MCP 工具

ZZZ OD MCP Server 安装和启动工具。

## 快速开始（本地开发）⭐

### 1. 安装 MCP Server

```powershell
# 安装到 Claude Code
.\tools\mcp\install.ps1

# 检查安装状态
.\tools\mcp\install.ps1 -Check
```

### 2. 启动 MCP Server

```powershell
# 使用默认端口（23001）
uv run python src\zzz_mcp\zzz_mcp_server.py
```

### 3. 使用

在 Claude Code 中：
```
请检查游戏窗口状态
请捕获游戏画面
```

## 远程 SSH 开发（可选）⚙️

**如果你通过 SSH 远程连接到游戏电脑**，需要使用 Daemon。

```powershell
# 安装 Daemon
.\tools\mcp\daemon\install_daemon.ps1

# 启动 Daemon（在游戏本机）
.\tools\mcp\daemon\start_daemon.ps1

# 设置开机自启
.\tools\mcp\daemon\create_startup_shortcut.ps1
```

详见：[docs/develop/zzz/mcp/remote-ssh.md](../../docs/develop/zzz/mcp/remote-ssh.md)

## 文件说明

### 主服务器相关
- `install.ps1` - 安装 MCP Server 到 Claude

### Daemon 相关（仅 SSH 场景）
- `daemon/install_daemon.ps1` - 安装 Daemon 到 Claude
- `daemon/start_daemon.ps1` - 启动 Daemon
- `daemon/create_startup_shortcut.ps1` - 创建开机自启快捷方式
- `daemon/zzz_od_daemon.py` - Daemon 服务器

## 端口说明

| 服务 | 端口 | 必需 |
|-----|-----|------|
| ZZZ OD MCP Server | 23001 | ✅ 是 |
| ZZZ OD Daemon | 23002 | ❌ 仅 SSH 场景 |

## 详细文档

完整文档请查看：[docs/develop/zzz/mcp/](../../docs/develop/zzz/mcp/)

- [README](../../docs/develop/zzz/mcp/README.md) - 总览
- [安装指南](../../docs/develop/zzz/mcp/installation.md) - 安装步骤
- [远程 SSH 开发](../../docs/develop/zzz/mcp/remote-ssh.md) - Daemon 架构
- [架构设计](../../docs/develop/zzz/mcp/architecture.md) - 系统架构
- [故障排查](../../docs/develop/zzz/mcp/troubleshooting.md) - 常见问题
