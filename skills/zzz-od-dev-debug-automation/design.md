# zzz-od-dev-debug-automation — 设计记录

## 为什么做

排查"迷失之地通用选择卡死"(见下方案例)时,踩了几个**项目专属**的坑(两个进程日志、识别路径分歧、OCR 隐藏参数、run_status=3 歧义),通用 `superpowers:systematic-debugging` 不管。这些判据下次排查运行中自动化 bug 还会用到,沉淀成 skill。

## 定位与边界

- **管**:排查**运行中**自动化 bug 的项目专属判据(找对日志 / 定位节点 / 识别类专项 / 采集证据)。
- **不管**:通用 debugging Phase 1-4(→ `superpowers:systematic-debugging`);定位后**决定怎么修**(→ `zzz-od-dev-deciding-a-fix`);游戏功能知识(→ doc)。

## 关键决策 + 理由

- **放 skill 不放 doc**:这是排查**方法论**(怎么做),按 `doc_organization`「skill vs doc 分界」(排查思路 → skill,具体游戏事实 → doc)。
- **叠加在 superpowers:systematic-debugging 之上,不重复通用流程**:本项目 dev skill 的定位就是"叠加项目专属在 superpowers 之上"(见 harness/README「方向 A」)。
- **SKILL.md 不写具体(crop_first、940px rect、ppocrv6 迁移号)**:skill-guide 硬规范 4(SKILL.md 写方法论不写具体例子);具体是这次案例的偶然细节,套到新场景会以偏概全。它们留在这(design.md)作决策论据。
- **去掉「用独立实例采样本」**:原草案点 5「不动主账号」,用户判断必要性不大(独立实例采集是 nice-to-have,不是排查必须;主账号 run_record 多一两条记录通常可接受)。砍掉保持 skill 精简。
- **GREEN 验证状态**:本 skill 属方法论覆盖型(skill-guide 两类分法),RED(baseline)可省;GREEN 验证**待补** —— 下次排查真实运行 bug 时,确认用了本 skill 的决策比裸跑更系统。⚠️ 当前是"写完未 GREEN 验证",下次实战注意校准(若有判据不实用/遗漏,回来改)。

## 案例:迷失之地通用选择卡死(踩坑论据)

> 完整排查历程,作为上面 SKILL.md 判据的来源。具体函数名 / 坐标 / 版本号记这,不进 SKILL.md。

**症状**:用户反馈近期迷失之地运行全部失败。

**弯路 1 —— analyze 误导**:`analyze_screen` MCP 显示"通用选择匹配",但 bot 运行时认不出。根因:analyze 走 `crop_first=False`(全图 OCR 再过滤),bot 运行时 `check_and_update_current_screen` → `is_target_screen` → `find_area_in_screen` 走 `crop_first=True`(先裁 rect 再 OCR)。ppocrv6 迁移(PR #2415)后,对**宽 text rect**(通用选择「按钮-确定」原 rect `[466,758,1406,977]`,宽 940px)crop_first=True 检不出「确定」→ id_mark 缺一 → 不匹配 → 整局卡死。→ SKILL 判据 3(识别路径 = bot 路径)。

**弯路 2 —— 换 ppocrv5 又出新 bug**:切 ppocrv5 临时缓解漏检,但宽 rect + `lcs_percent=0.5` 把**大世界场景文字「以太稳定」**(与「确定」LCS=0.5)误配成「确定」+ TAB → 大世界被误判成通用选择 → LostVoidChooseCommon 标题为空 → 死循环(实跑 12 通关后卡在挚交会谈 NPC 玛琳前 ~2h,日志 2101 次 `fallback:none`)。→ SKILL 判据 3(OCR 离线验参数)+ 判据 2(数信号:fallback:none 爆炸 = 循环)。

**采集 + 复现**:在 handle_interact(路由节点)加 `is_debug` 门控的 `save_screenshot`,采到各选择画面真实帧 → 离线脚本遍历 crop_first / lcs / rect 锁定根因 → 收紧 rect 到 `[855,795,1165,975]` + lcs 0.7。→ SKILL 判据 4(识别时刻截图 + 离线复现)。

**进程 / 日志混淆**:初期只翻 MCP server 日志(`.debug/zzz_od_mcp/main_server.log`),没找到用户跑的痕迹 —— 用户是 GUI/一条龙跑的,日志在 `.log/log.txt`。→ SKILL 判据 1。

## 代码可排查性改进建议(给后续改框架的人,follow-up 清单)

这次排查暴露的可排查性短板(非本 skill 范围,记录备改):
1. **路由节点卡死看门狗 + 诊断截图**:`handle_interact` 这类 `round_retry` 节点,N 次重试无进展 → 自动存诊断截图 + 日志明确报"卡在 X 画面,期望 Y"(现在能无声循环几小时)。
2. **画面匹配记命中明细**:精准匹配时日志记"命中哪些 id_mark(名 + 实际 OCR 值 + 置信度)" —— 误匹配靠这个一眼能看出,现在只记"匹配到 X"看不出为啥。
3. **screen_info lint**:text id_mark 的 rect 过宽 + `lcs_percent` 过低 → 标"易误匹配"风险(宽 text rect + 松 lcs = 误匹配磁铁)。
4. **OCR 模型迁移带 fixture 回归**:ppocrv6 迁移时,用 `test_get_match_screen_name` 的 fixture 套件在两模型下各跑一遍,抓迁移引入的识别回归。
