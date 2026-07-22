# 远程 SSH daemon

> 让远程 SSH 会话也能用上 backend 主 server(23001)。daemon 常驻游戏本机 Session 1、**只管主 server 启停**;**操作游戏的是主 server**(game tool 在主 server)。远程 MCP 客户端挂 daemon 启停主 server、再连主 server 调 game tool。本地场景直接挂主 server([mcp.md](mcp.md)),不需要 daemon。

## 为什么需要 daemon

Windows **Session 隔离**:SSH 登录落在 Session 0(服务会话),游戏窗口在 Session 1(交互式桌面);`PsExec -i 1` 也拿不到管理员权限;而输入注入(`pyautogui` / `pydirectinput`)必须管理员 + 交互式桌面会话。结论:**SSH + PsExec 不可行**,必须在 Session 1 里直接以管理员启动进程。

daemon 就是那个**常驻 Session 1、握有管理员权限**的管理者——它拉起的主 server 继承权限,才能操作游戏。

## 拓扑

```
本地:    MCP 客户端 ──► 主 server(:23001) ──► 操作游戏

远程 SSH:  daemon(:23000,Session 1 常驻/管理员) ──启停──► 主 server(:23001) ──► 操作游戏
           └─ MCP 客户端挂 daemon 管 server 启停;主 server 起来后,客户端再连它(:23001)调 game tool。
```

## 安装与使用(均在游戏本机交互式桌面操作,不能经 SSH)

1. 装 dev 依赖:`uv sync --group dev`(装 `psutil`)。
2. 起 daemon:`.\tools\mcp\daemon\start_daemon.ps1`(默认 23000)。
3. 在你的 MCP 客户端注册 daemon(URL `http://127.0.0.1:23000/mcp`——客户端与 daemon 同机:SSH 登录游戏本机后在本机跑 Claude Code,loopback 跨 Session 也能连到 Session 1 的 daemon)。Claude Code 示例:

   ```shell
   claude mcp add --transport http zzz_od_daemon http://127.0.0.1:23000/mcp
   ```

4. 重启客户端,用 daemon 的 4 个 tool:`start_zzz_od_mcp_server` / `get_zzz_od_mcp_server_status` / `stop_zzz_od_mcp_server` / `restart_zzz_od_mcp_server`。

## 开机自启

`.\tools\mcp\daemon\create_startup_shortcut.ps1` —— 在 Startup 文件夹建快捷方式,登录后自动起 daemon。卸载即删该 `.lnk`。

## 排查

- 端口:daemon **23000**、主 server **23001**;用 `get_zzz_od_mcp_server_status` 看 server 状态,或 `netstat -ano | findstr :2300`。
- 主 server 起不来:看 `start_zzz_od_mcp_server` 返回里指向的日志(`.debug/zzz_od_mcp/main_server.log`)。
- daemon 自身要常驻;它重启不影响已起的主 server(psutil 按 cmdline 重新发现)。

## 相关文档

- [entry.md](entry.md) — 服务入口
- [architecture.md](architecture.md) — backend 架构与资源约束
