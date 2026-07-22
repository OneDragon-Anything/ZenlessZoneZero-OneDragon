# chrome-devtools-mcp（浏览器 MCP）

让 AI 经 Chrome DevTools Protocol (CDP) 驱动本机浏览器,读取/操作 **WebSearch 搜不到或抓不到的页面**(如米游社攻略、需登录的活动页)。服务于 [`zzz-od-miyoushe`](../../../skills/zzz-od-miyoushe/SKILL.md) skill 与 gameplay 调研。

## 接法选型:connect 模式(推荐)

chrome-devtools-mcp 有两种接法:

| 接法 | 谁起浏览器 | profile | 适合 |
|---|---|---|---|
| **launch**(`--isolated` 等) | MCP 自己拉一个 | 临时、用完即弃 | 一次性读公开页 |
| **connect**(`--browser-url`,本 doc) | **你自己**先开一个带调试端口的浏览器,MCP 连上去 | **持久**(登录态/cookie 留得住) | 需登录、签到、兑换码 |

推荐 **connect**:米游社登录、签到等要留存登录态;且浏览器窗口在你能看到的桌面会话里(见「会话坑」)。

## 前置

- **Node.js**(MCP server 经 `npx` 跑):`node --version` 验证。
- **Chromium 浏览器**:Chrome 或 Edge 都行(Edge 是 Windows 自带,无需另装)。

## ① 装 MCP(connect 模式、user scope)

```shell
claude mcp add chrome-devtools -s user -- npx -y chrome-devtools-mcp@latest --browser-url=http://127.0.0.1:19999 --no-usage-statistics
```

> `-s user`:装到你个人配置(`~/.claude.json`),不进项目仓库、不影响队友。端口 `19999` 可自定,与下方②一致即可。

## ② 开调试浏览器(你自己在桌面会话开)

> ⚠️ **必须你自己在桌面(交互会话)开,不要让 agent 的 Bash 去开** —— agent 跑在非交互会话(Session 0,无可见桌面),它开的浏览器窗口你**看不到**(见「会话坑」)。这条是本方案最常见的踩坑点。

PowerShell(从开始菜单正常打开,落在你的桌面会话):

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
    --remote-debugging-port=19999 `
    --user-data-dir="$env:USERPROFILE\.edge-debug-profile" `
    --no-first-run --no-default-browser-check about:blank
```

- `--user-data-dir`:**独立 profile**,不碰你日常 Edge(路径自选;复用已有调试 profile 也行)。
- 验证 CDP 起来:浏览器访问 `http://localhost:19999/json/version`,返回版本 JSON 即 ok。

## ③ 让 Claude Code 加载工具

新装的 MCP 当前会话不会自动加载 —— **`/mcp` 重连**(或重启 Claude Code)后,`chrome-devtools` 才出现在工具列表(`mcp__chrome-devtools__*`)。

## 验证全链路

```
navigate_page → https://www.miyoushe.com/zzz/
take_snapshot  → 能读到中文内容即通
```

文本密集页用 `take_snapshot`(a11y 树,省 token);判选中态/视觉布局/图标位置用 `take_screenshot`。

## 会话坑(重要)

Windows 上 Claude Code 的 Bash/agent 进程常跑在 **Session 0(services,无可见桌面)**,而你的可见桌面是 **console 会话(Session 3 等)**。会话隔离意味着:

- **agent 起的带窗口进程(浏览器、游戏)落在 Session 0 → 窗口你看不到**(不是 headless,是会话隔离)。
- 所以带界面、要你交互/扫码/登录的东西,**必须你自己在桌面会话启动**;agent 只负责经 localhost CDP(跨会话通)连进去驱动。
- 这跟「游戏/项目 MCP 必须进交互桌面会话」是同一个根因(本项目 backend MCP 经 daemon 拉起,也是为落在交互桌面)。

## 脚本化(可选)

若把②做成 `.ps1` 反复跑,注意:**存成 UTF-8 *with BOM***。Windows PowerShell 5.x(`powershell.exe`)默认按系统码页(中文环境为 GBK)读无 BOM 的脚本,会把中文注释解析错(`MissingEndCurlyBrace` 等)。用 PowerShell 7(`pwsh`,默认 UTF-8)跑无 BOM 脚本则无此问题。

## 相关

- [`zzz-od-miyoushe` skill](../../../skills/zzz-od-miyoushe/SKILL.md) — 本 MCP 的主要消费者(操作米游社)。
- [AI 编码助手接入](ai_coding.md) — 本项目 MCP 总览。
