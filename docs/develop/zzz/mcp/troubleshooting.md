# 故障排查

本文档介绍常见问题及其解决方法。

## 问题 1：无法连接 MCP 服务器

### 症状

在 Claude Code 中调用工具时提示连接失败

### 可能原因

1. MCP 服务器未启动
2. 端口配置不一致
3. 防火墙阻止连接

### 解决方法

#### 1. 确认 MCP Server 已启动

```powershell
# 检查端口 23001 是否监听
netstat -ano | findstr :23001
```

如果没有输出，MCP Server 未启动：

```powershell
uv run python src\zzz_mcp\zzz_mcp_server.py
```

#### 2. 测试 HTTP 连接

```powershell
# 测试 MCP Server 连接
curl http://127.0.0.1:23001/mcp
```

#### 3. 检查 Claude Code 配置

```bash
claude mcp list
```

确认 `zzz_od` 在列表中，且端口配置正确。

---

## 问题 2：端口已被占用

### 症状

启动时出现错误：`Address already in use` 或 `端口已被占用`

### 解决方法

#### 1. 查找占用端口的进程

```powershell
# 查找端口 23001
netstat -ano | findstr :23001
```

输出示例：
```
TCP    127.0.0.1:23001    0.0.0.0:0    LISTENING    12345
```

最后一列是进程 ID (PID)。

#### 2. 停止占用端口的进程

```powershell
# 停止进程
Stop-Process -Id 12345 -Force
```

#### 3. 使用其他端口

如果不想停止进程，可以修改端口配置：

```powershell
# 安装到其他端口
.\tools\mcp\install.ps1 -Port 9001

# 启动时指定端口
uv run python src\zzz_mcp\zzz_mcp_server.py --port 9001
```

---

## 问题 3：模块导入失败

### 症状

错误：`ModuleNotFoundError: No module named 'zzz_mcp'`

### 原因

1. 不在项目根目录下运行
2. Python 依赖未安装

### 解决方法

```bash
# 1. 确保在项目根目录
cd D:\code\workspace\ZenlessZoneZero-OneDragon

# 2. 安装依赖
uv sync --group dev
```

---

## 问题 4：配置未生效

### 症状

修改配置后没有生效

### 解决方法

#### 1. 重启 Claude Code

配置修改后必须重启 Claude Code。

#### 2. 检查配置

```bash
# 查看配置
claude mcp list
```

#### 3. 重新安装

```powershell
# 卸载
.\tools\mcp\install.ps1 -Uninstall

# 重新安装
.\tools\mcp\install.ps1
```

---

## 问题 5：游戏窗口检测失败

### 症状

调用 `check_game_window` 返回窗口无效

### 原因

1. 游戏未启动
2. 游戏窗口标题不匹配
3. 游戏窗口最小化

### 解决方法

#### 1. 确认游戏已启动

手动启动游戏，检查窗口标题是否为"绝区零"。

#### 2. 检查窗口状态

```powershell
# 查找游戏窗口
Get-Process | Where-Object {$_.MainWindowTitle -like "*绝区零*"}
```

#### 3. 使用自动启动

使用自动启动工具：
```
请打开并进入游戏
```

---

## 问题 6：权限问题

### 症状

操作失败，提示权限不足

### 解决方法

#### 1. 以管理员身份运行

右键 PowerShell -> 以管理员身份运行

#### 2. 检查 UAC 设置

确保 UAC 不会阻止操作

#### 3. 检查文件权限

确保项目目录有读写权限

---

## 问题 7：找不到 claude 命令

### 症状

运行安装脚本时提示找不到 claude 命令

### 解决方法

#### 1. 检查 Claude Code CLI 是否安装

```bash
claude --version
```

#### 2. 重新安装 Claude Code CLI

参考 Claude Code 官方文档进行安装。

---

## 问题 8：SSH 远程开发问题

### 症状

通过 SSH 连接后，MCP Server 无法触发鼠标点击

### 说明

这是 Session 隔离问题，SSH 运行在 Session 0，游戏运行在 Session 1。

### 解决方法

需要使用 Daemon 架构。

详见：[远程 SSH 开发指南](remote-ssh.md)

---

## 获取帮助

如果以上方法都无法解决问题：

1. 查看详细的错误信息和堆栈跟踪
2. 检查日志文件
3. 搜索或提交 GitHub Issues
4. 提供详细的复现步骤和环境信息
