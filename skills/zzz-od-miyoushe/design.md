# design: zzz-od-miyoushe

## 为什么做
gameplay-onboarding 要「米游社优先」查玩法,但 WebSearch 搜不到米游社内容(浏览器 MCP 解决了「能打开」,见记忆 `chrome-devtools-browser-mcp`)。本 skill 把「怎么靠浏览器 MCP 稳操作米游社」沉淀成可复用能力:登录 / 搜内容 / 取兑换码(签到实测 APP-only,不含)。用户逐步指引、边学边建;login / 搜索 / 前瞻兑换码均已实测验证。

## 定位与边界
- 管:经 chrome-devtools MCP 操作米游社的**方法论 + 确定性流程**。
- 不管:浏览器 MCP 本身的接法/启动(记忆 `chrome-devtools-browser-mcp`);游戏玩法内容本身(gameplay doc)。
- 增量构建:只把**已验证**的流程写进 SKILL.md;未学的标在下方 roadmap,不臆造。

## 关键决策
1. **命名 `zzz-od-miyoushe`(使用/能力类,非 `zzz-od-dev-`)**:`dev-` 是项目开发流程类;本 skill 是「教智能体操作米游社」的能力 skill → 用 `zzz-od-`(skill-guide 的使用类)。
2. **SKILL.md 写方法论,定位按角色**:遵循 skill-guide 硬规范 #4(skill = 方法不 = 具体例子)。流程以「按文本/role 动态定位 + 操作后验证」描述,不硬编码 uid/选择器(uid 每次会话变)。确定性事实(账号入口 id=undefined 表未登录)作为**判据**保留,不当作「某次坐标」。
3. **流程内联,暂不拆 doc**:login / 搜索 / 前瞻兑换码 三个流程内联够用;待流程再多、specifics 膨胀,再抽进 `docs/` doc(skill 指向它),符合 #4「具体 → doc」。

## 踩坑(决策论据)
- **扫码切换器是 `<img>` 图标,不是「扫码登录」文字 `generic`**:点文字报「did not become interactive」,改点同区 `<img>` 成功 → 抽象成总则「图标类点 img 不点文字 wrapper」。
- **未登录信号**:账号入口 `accountCenter/postList?id=undefined`(登录后变数字 uid)→ 登录态判据。
- **web 扫码无 stoken**:实走验证(2026-07-18),扫码登录拿到 `cookie_token`、uid=6687716,但 `stoken` 缺席。签到/兑换码若要 stoken,待后续实走确认(可能需 App 端授权另取)。
- **登录窗口在用户桌面会话才可见**:浏览器在用户 Session 3(见 `chrome-devtools-browser-mcp` 会话坑),QR 由用户扫,我看不到实体码也不解码。

## 米游社 API 结构(直发请求用,2026-07-18 观察)
- **API host**:`bbs-api.miyoushe.com`(动态 / 需登录)、`bbs-api-static.miyoushe.com`(静态 / 配置,少变)。
- **游戏标识**:`gids` 参数。绝区零 `gids=8`(从 `/zzz/` 页所有请求 `?gids=8` 确认);其他游戏 gids 待按需确认(可调 `getGameList`)。
- **认证**:cookie(登录后 `cookie_token` 等)。GET 取数直接带 cookie 即可;POST / 写操作可能还要 `DS` 签名(待签到 / 兑换码实走确认)。
- **观察到的端点**:`webHome?gids=8&page=1&page_size=20`(首页 feed)、`getOfficialRecommendedPosts`、`getDynamicData?gids=8&post_ids=<逗号>`(按 id 批量取帖子详情)、`getUserFullInfo`(当前用户)、`getGameList`(游戏 / gids 映射)。

## 风控与请求头(直发必读,2026-07-18 实测)
米哈游 API 风控严。浏览器每个请求(含 GET)都带:
- `ds: <时间戳>,<base64 盐>,<md5>` —— **按请求实时算**的签名(两条请求的盐 / md5 不同),手搓需复刻算法,成本高。
- `x-rpc-device_id`(=`_MHYUUID` cookie)/ `x-rpc-device_fp`(=`DEVICEFP` cookie)/ `x-rpc-client_type=4`(web)/ `x-rpc-app_version`(如 `2.102.0`)。
- UA、`referer:https://www.miyoushe.com/`、`origin:https://www.miyoushe.com`、全套登录 cookie(`cookie_token` / `account_id` / `ltoken` / `ltuid` 及 v2 版)。
- 风控信号:响应头暴露 `X-Rpc-Aigis`(人机挑战);retcode `-1101`(请求异常 / 限流)、`-100`(未登录)等。

结论(进 SKILL.md 总则):**读优先读浏览器已加载结果(0 新请求)**;必发才直发且复刻完整头(含 DS);**写操作走浏览器点击**(DS 难搓 + 风控敏感)。实测搜索接口 cookie-only 直发也能拿到数据(retcode 0),但不可作为常态——按上述策略规避。

> 方案 3(调浏览器自己的签名客户端替我签自定义请求)实测**不可行**(2026-07-18):`window` 全局只有 `miHoYoAccountSdk`(账号 / 护照)、`mihoyoCommunityInit`(社区)等 SDK,均不暴露带 DS 的 bbs 请求客户端;**该客户端在 webpack bundle 里、未挂 `window`**(只看到 `webpackJsonp`)。取出需枚举 webpack 模块,且模块 ID 每次构建变化 → 脆脆、ROI 低(社区签到脚本走这条,需持续维护)。故本 skill 写操作维持「浏览器点击」。真要无人值守批量签到,另起工程或用社区脚本,不纳入本 skill。

## 搜索端点(2026-07-18)
- 综合搜索:`GET bbs-api.miyoushe.com/apihub/wapi/search?gids=8&keyword=<urlenc>&size=20` → `data.{posts[],topics[],users[],directions[],wikis[]…}`(「随便观」实测 `posts` 空、有 users / wiki)。
- 帖子搜索:`GET bbs-api.miyoushe.com/painter/wapi/searchPosts?gids=8&keyword=<urlenc>&size=20` → `data.list[]`,每项 `post.{subject,post_id,content,text_summary}`、`stat.{view_num,like_num,reply_num,bookmark_num,forward_num}`、`user.nickname`、`forum.name`。
- `keyword` 须 URL 编码;搜索为内联(不跳页)。

## 前瞻兑换码(2026-07-18 实测)
- **入口**:米游社 ZZZ 首页右侧工具区「`<版本号>前瞻`」(实测 3.1 时为「3.1前瞻」,**版本号随版本变**,按 `\d+前瞻` 定位;`div.game-tool-info_max_text_title`,Vue 点击,非 `<a>`)→ 新标签开前瞻特别节目页。
- **页面**:`webstatic.mihoyo.com/bbs/event/live/index.html?act_id=ea202607151739059713&game_biz=nap`(`game_biz=nap`=ZZZ)。直播类页面,`mhy_presentation_style=fullscreen`。
- **取码**:DOM `innerText` 里「兑换码:<码> 复制」;实测当前码 `0729XUSHOU`(菲林×300 / 资深调查员记录×2 / 音擎能源模块×3 / 丁尼×30000)。前瞻通常 3 码,直播结束后「查看回顾」可能还有(另两个或已过期,未深挖)。
- **兑换**:国服 ZZZ **无 web 兑换**(搜索 + 官网无入口、user.mihoyo.com 要重登),码去**游戏内**兑(设置 → 更多 → 兑换码)。国际服才有 `zenless.hoyoverse.com/redemption` 网页兑换。
- **定位坑**:「3.1前瞻」是 Vue `div`,`addEventListener` 挂点击 → `cursor`/`onclick` 检测不到;按文本找叶子 div + `.click()`(已抽象进 SKILL.md 总则)。
- **公开活动 API(脚本化 / 无人值守优先,见 SKILL.md ①)**:直播间 H5 背后的 `event/miyolive/*` 是**公开活动接口**,匿名 + 仅需 `x-rpc-act_id` 头,**无 DS / 无 cookie / 不触发人机**——对照「风控与请求头」里要 DS 的社区业务接口,是两类东西(活动接口给直播间页面拉码用,本就匿名可访问;社区接口要签名 + 登录)。三段串起来取码(2026-07-18 从 `tools/ci/update_redemption_code.py` 提取,该脚本 + workflow `update-redemption-code.yml` 是现成实现,CI 每天 21 点跑):
  1. `GET bbs-api.miyoushe.com/apihub/api/home/new?gids=8&parts=1,3,4` → `data.navigator[]` 找名字含「前瞻」项,正则 `act_id=(.*?)&` 从其 `app_path` 抠出 `act_id`(等价于浏览器点「<版本>前瞻」入口)。
  2. `GET api-takumi.mihoyo.com/event/miyolive/index`(头 `x-rpc-act_id: <act_id>`)→ `data.live.{code_ver, title, is_end, start}`;过期时间 = `start` +1 天 23:59:59(北京时间);`code_ver` 缺则码未放出。
  3. `GET api-takumi-static.mihoyo.com/event/miyolive/refreshCode?version=<code_ver>&time=<unix秒>`(头 `x-rpc-act_id`)→ `data.code_list[].code`。
  实测 2026-07-18 抓到 `0729XUSHOU`(deadline `20260718`);CI 落盘前会 `clean_expired_sample_codes` 清过期再 `add_sample_code` 加新码。**要拉码复用该脚本,勿重造。**

## roadmap(待用户指引、验证后补进 SKILL.md)
- ✅ 搜索(已进 SKILL.md):搜索框内联触发 searchPosts;读浏览器已加载结果避风控。
- ❌ 米游社社区签到(2026-07-18 实测,三种验证):① 桌面访问 `act.mihoyo.com/bbs/event/signin/zzz/...` → 重定向到 `bbs.mihoyo.com/download.html?app=zzz_qd`(下载页);② `webstatic.mihoyo.com/bbs/event/signin-zzz/` → **404**(原神 `signin-ys` 那套不套用 ZZZ);③ 移动 UA + 签到页 → 渲染出「打开App」。三种均 **APP-only**,非「桌面不行移动行」。用户确认一直用手机 App 签到,web 不做 → 本 skill 不含签到(要做需 APP,或独立 stoken 脚本)。
- ✅ 前瞻兑换码(已进 SKILL.md):首页右侧「<版本>前瞻」→ 直播页读码(`0729XUSHOU` 实测);国服游戏内兑换,无 web 兑换。

## 落点
- `skills/zzz-od-miyoushe/`(SKILL.md + design.md),junction `.claude/skills/zzz-od-miyoushe`(同其它 zzz-od skill,junction 不提交,每人本地建)。
