# 远程 SSH 开发指南

本文档介绍如何通过 SSH 远程连接到游戏电脑进行开发。

## 适用场景

**只在以下情况下需要阅读本文档**：

- ✅ 你通过 SSH 远程连接到游戏电脑
- ✅ 你需要在远程会话中控制游戏

**如果以下情况，不需要阅读本文档**：

- ❌ 你直接在游戏本机上使用 Claude Code
- ❌ 你只需要本地开发

请参考：[README.md](README.md) - 本地开发快速开始

## 问题：SSH 远程无法触发鼠标点击

### 原因分析

**1. Session 隔离**
- SSH 运行在 Session 0（服务会话）
- 游戏窗口运行在 Session 1（交互式桌面会话）

**2. PsExec 的限制**（已尝试的方案）
- ❌ PsExec 无法提权到管理员权限
- ❌ 即使使用 `-i 1` 参数切换到 Session 1，仍无法获取管理员权限
- ❌ `pyautogui`、`pydirectinput` 等鼠标点击库需要管理员权限
- ❌ 跨会话启动会导致权限上下文丢失

**3. 结论**
- SSH + PsExec 方案**不可行**，无法实现鼠标点击功能
- 必须在 Session 1 中直接以管理员权限启动进程

## 解决方案：Daemon 架构

通过在游戏本机运行一个长期运行的 Daemon（管理服务器），实现远程控制。

### 架构

```
┌─────────────────┐                    ┌──────────────────┐
│   SSH 会话       │                    │  Session 1       │
│  (Session 0)    │                    │                  │
│                 │  HTTP (MCP)         │  Daemon          │
│  Claude Code    │◄───────────────────│  (端口 23002)    │
│                 │                    │  长期运行，轻量    │
└─────────────────┘                    └──────────────────┘
                                              │
                                              │ 启停控制
                                              ▼
                                     ┌──────────────────┐
                                     │  MCP Server      │
                                     │  (端口 23001)    │
                                     │  按需启动         │
                                     │  游戏操作         │
                                     └──────────────────┘
```

**设计理念**：
- **Daemon**：轻量级 MCP，长期运行在 Session 1
- **MCP Server**：游戏操作 MCP，按需启动/停止

**优势**：
- ✅ Daemon 在 Session 1 运行，拥有管理员权限
- ✅ Daemon 启动的 MCP Server 继承管理员权限
- ✅ 可通过 HTTP 远程控制启停
- ✅ 资源占用小，可长期运行
- ✅ 支持开机自启

## 安装和配置

### 步骤 1：安装 Daemon（在游戏本机）

**重要**：Daemon 必须在游戏本机直接启动（Session 1），不能通过 SSH 启动。

```powershell
# 安装到 Claude Code（默认端口 23002）
.\tools\mcp\daemon\install_daemon.ps1

# 检查安装状态
.\tools\mcp\daemon\install_daemon.ps1 -Check

# 卸载
.\tools\mcp\daemon\install_daemon.ps1 -Uninstall
```

### 步骤 2：启动 Daemon（在游戏本机）

**在游戏本机上操作**（不能通过 SSH）：

```powershell
# 使用默认端口（23002）
.\tools\mcp\daemon\start_daemon.ps1

# 指定端口
.\tools\mcp\daemon\start_daemon.ps1 -Port 9001
```

### 步骤 3：设置开机自启（推荐）

```powershell
# 创建开机自启快捷方式
.\tools\mcp\daemon\create_startup_shortcut.ps1
```

快捷方式将创建到启动文件夹，开机时自动启动 Daemon（后台运行，隐藏窗口）。

### 步骤 4：通过 SSH 远程使用

现在你可以通过 SSH 远程连接，在 Claude Code 中使用：

```
请启动 zzz_od 服务器
请检查游戏窗口状态
请打开并进入游戏
```

## Daemon 工具

| 工具名称 | 说明 |
|---------|------|
| `start_zzz_od_server` | 启动 MCP Server（端口 23001）|
| `stop_zzz_od_server` | 停止 MCP Server |
| `restart_zzz_od_server` | 重启 MCP Server |
| `get_zzz_od_server_status` | 查看服务器状态（PID、内存、CPU 等）|

## 使用流程

### 典型工作流程

1. **游戏本机**：Daemon 已启动（开机自启）
2. **SSH 远程**：连接到游戏电脑
3. **启动服务器**：
   ```
   请启动 zzz_od 服务器
   ```
4. **使用工具**：
   ```
   请检查游戏窗口状态
   请打开并进入游戏
   ```
5. **操作完成后**（可选）：
   ```
   请停止 zzz_od 服务器
   ```

### 查看服务器状态

```
请调用 get_zzz_od_server_status 查看服务器状态
```

返回示例：
```
[STATUS] ZZZ OD MCP Server 运行中
PID: 12345
启动时间: Wed Feb 11 08:00:22 2026
CPU 使用: 0.5%
内存使用: 45.32 MB
子进程数: 2
端口: 23001
```

## 停止 Daemon

### 方法 1：通过端口查找并停止

```powershell
# 通过端口 23002 找到进程ID并停止
$pid = (netstat -ano | Select-String ":23002.*LISTENING").ToString().Split()[-1]
Stop-Process -Id $pid -Force
```

### 方法 2：Ctrl+C

如果 Daemon 在前台运行，直接按 `Ctrl+C` 停止。

## 故障排查

### Daemon 无法连接

确保：
1. Daemon 已在游戏本机启动（不能通过 SSH）
2. 检查端口 23002 是否监听：`netstat -ano | findstr :23002`
3. Claude Code 配置文件包含 Daemon 配置

### MCP Server 点击无效

**关键**：MCP Server 必须由 Daemon 在游戏本机启动，不能通过 SSH + PsExec 启动。

### MCP Server 启动失败

检查：
1. 项目路径是否正确
2. 环境变量文件 `.env` 是否存在
3. 端口 23001 是否被占用

## 与本地开发的区别

| 特性 | 本地开发 | 远程 SSH 开发 |
|------|----------|--------------|
| 启动方式 | 直接启动 MCP Server | 通过 Daemon 管理 |
| 工作位置 | 游戏本机 | SSH 远程 |
| 鼠标点击 | ✅ 正常工作 | ✅ 通过 Daemon 正常工作 |
| 远程管理 | ❌ 不支持 | ✅ 支持 |
| 开机自启 | 不需要 | 推荐 |
| 复杂度 | 简单 | 较复杂 |

## 总结

- **本地开发**：直接启动 MCP Server，不需要 Daemon
- **远程 SSH 开发**：需要使用 Daemon 架构

如果你不需要远程 SSH 开发，请忽略本文档，参考 [README.md](README.md) 进行本地开发即可。
