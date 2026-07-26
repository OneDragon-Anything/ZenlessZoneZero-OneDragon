---
name: zzz-od-miyoushe
description: 当要经浏览器 MCP(chrome-devtools)操作米游社时用——登录/扫码、搜游戏内容、签到、取前瞻直播兑换码。
---

# 操作米游社(chrome-devtools MCP 驱动)

经 chrome-devtools MCP 驱动用户桌面会话里的 Edge 操作米游社(默认绝区零板块)。前提:用户桌面已开调试 Edge(CDP 19999)、且 `/mcp` 已连 chrome-devtools(接法/会话坑见 [docs/develop/setup/chrome-devtools-mcp.md](../../docs/develop/setup/chrome-devtools-mcp.md))。

## 总则(适用每个操作)
- **先判登录态再操作**:右上角账号入口 `accountCenter/postList?id=` —— 空或 `undefined` = 未登录;数字 = 已登录(也可探测 `cookie_token` cookie)。未登录先走「登录」。
- **定位按角色/文本,不硬编码 uid**:页面 uid 每次会话变;按文本(如「扫码登录」)、`role=tab` 等动态定位,再取最新 snapshot 的 uid。
- **图标类点 `<img>`,不点外层文字 `generic`**:文字 wrapper 常报「did not become interactive」;改点同区 img/图标节点。
- **Vue/React 点击元素按文本定位,别靠 `cursor`/`onclick` 检测**:框架用 `addEventListener` 挂点击,不改 `cursor`、不写 `onclick` 属性 → `evaluate` 查 `cursor:pointer` / `.onclick` 会漏报「不可点」。定位:按文本找叶子元素(**版本号等会变的,按模式匹配而非写死**,如 `div` 文本匹配 `\d+前瞻` 而非「3.1前瞻」),`element.click()` 触发(冒泡到框架监听);或 `take_snapshot` 取 uid 再用 `click` 工具点。
- **读文本用 `take_snapshot`(a11y 树,省 token);判选中态/布局/图标位置用 `take_screenshot`**(图标 a11y 不友好,看图最稳)。
- **操作后验证**:点完/提交后 `take_snapshot` 或 `evaluate_script` 确认状态变了(如登录后账号 id 从 undefined→数字),别假设成功。
- **能扫码的让用户扫**:QR 登录等需手机 App 扫的,我显示码 + 等用户扫;**不自己解码 QR**。
- **取数优先读浏览器已加载结果,少发新请求(避风控)**:能从已渲染 DOM(`take_snapshot`)或已发 API 响应(`get_network_request` 存 body 再读)拿到的,**直接读**(0 新请求 = 0 新增风控)。仅当浏览器没加载 / 要翻页 / 要脚本化才直发,且**复刻浏览器原请求完整头**(`ds` / `x-rpc-device_id` / `x-rpc-device_fp` / `x-rpc-client_type=4` / `x-rpc-app_version` / UA / Referer / Origin + cookie)——浏览器连 GET 都带 `ds`(按请求实时签名),缺了累积 / 敏感接口会被静默降级或限流。**写操作优先浏览器点击**(站点自算 DS、自带风控;直发写请求要搓 DS、风控最严)。遇 retcode 异常(`-1101` / `-100`)、`X-Rpc-Aigis` 或人机挑战 → 停直发、回退浏览器、降频。

## 登录(扫码)
1. 任意米游社页,点右上角账号入口(未登录态)→ 弹登录模态(iframe `user.miyoushe.com/login-platform`,默认短信 tab)。
2. 切扫码:点模态里**二维码图标 `<img>`**(非「扫码登录」文字)→ 显示 QR「打开米游社/游戏/云游戏 App,扫一扫登录」。
3. 让用户用米游社 App 扫码,扫完模态自关。
4. 验证:账号入口 `id=` 变数字 + `cookie_token` cookie 存在 + 登录 iframe 消失,三者满足即成功。

> web 扫码登录拿到 `cookie_token` 但**通常不带 `stoken`**(后者多来自 App 端)。实测:签到 APP-only 做不了、兑换码是读页面(游戏内兑)——都不需 web 端 stoken。

## 游戏板块与导航
米游社按游戏分大板块,**URL 路径码即游戏**:`/zzz/`=绝区零、`/ys/`=原神、`/sr/`=星穹铁道、`/bh3/`=崩坏3。切游戏 = `navigate` 到对应路径码(页面无跨游戏链接,UI 切换器非主路径)。API 侧用 `gids` 标识游戏(绝区零 `gids=8`);取别游戏数据改 `gids` 即可。

## 搜索
顶部搜索框填关键词 + 回车 → **内联**出结果(不跳页),触发 `bbs-api.miyoushe.com/painter/wapi/searchPosts?gids=<gids>&keyword=<URL编码>&size=20`(帖子;综合 `apihub/wapi/search` 另含用户 / wiki / 话题,但其 `posts` 常空)。拿结果**优先读浏览器已发的该响应**(`get_network_request` 存 body)或已渲染列表(`take_snapshot`),别重发请求(避风控,见总则)。帖子标题 `data.list[].post.subject`、id `.post.post_id`、互动 `.stat.{view_num,like_num,reply_num}`、作者 `.user.nickname`。翻页 / 批量再考虑直发(带完整头)。

## 前瞻兑换码
取码有两条路,**脚本化 / 无人值守优先走公开活动 API,别开浏览器**(轻、稳、免登录):

- **① 公开活动 API(优先)**:直播间 H5 背后是 `event/miyolive/*` 系列公开接口,**截至 2026-07-18 实测:匿名、仅需 `x-rpc-act_id` 头、无 DS / 无 cookie / 不触发人机**(当下接口行为,非永久契约——米游社接口可能随时加风控/改协议;遇 retcode `-1101`/`-100`、`X-Rpc-Aigis` 人机挑战或限流 → 停直发、**回退 ② 浏览器读 DOM 路径**,避免无人值守流程因接口策略变化失效;区别于要 DS 签名的社区业务接口,见总则避风控)。三段调用即可取码,本项目 `tools/ci/update_redemption_code.py` 已是现成实现(CI 每天 21 点自动跑,落 `config/redemption_codes.sample.yml`),**要拉码直接复用 `tools/ci/update_redemption_code.py`(端点 / 参数 / 过期算法看该脚本源码),勿开浏览器、勿重造。**
- **② 浏览器读 DOM(仅交互式调试用)**:米游社 ZZZ 首页**右侧工具区**有「当前版本前瞻」入口(标签 = `<版本号>前瞻`,如 `3.1前瞻` / 下版本 `3.2前瞻`,**数字随版本变 → 按 `\d+前瞻` 文本定位,别写死版本号**),是个 Vue `div`、非 `<a>` —— 按文本定位 + `click`(见总则)→ 开「前瞻特别节目」页 `webstatic.mihoyo.com/bbs/event/live/index.html?act_id=<id>&game_biz=nap`。页内直接展示**兑换码 + 奖励 + 「复制」**;直播结束可「查看回顾」。**读 DOM `innerText` 即可取码**(找「兑换码:」上下文,码型大写字母+数字)。

> 国服 ZZZ **无 web 兑换**(码在游戏内兑:设置 → 更多 → 兑换码);上述两条路都只**取码**,兑换走游戏内。国际服才有 `zenless.hoyoverse.com/redemption` 网页兑换。
