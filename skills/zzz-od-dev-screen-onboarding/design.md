# design: zzz-od-dev-screen-onboarding

## 为什么做
建游戏知识库(`docs/game/`)+ 维护 `screen_info` 时,每来一张新画面都要重复「分析 → 建档 → 建模」流程。这套流程在「打开游戏」画面(右下角 4 个图标按钮)实战跑通过,沉淀成 skill,保证后续画面:流程一致、不漏可交互元素、不踩「工具绕路 / 手编 yml」的坑。

## 定位与边界
- **管**:拿到截图后的离线分析 + 建档(`docs/game/screens/`)+ 建模可交互元素(模板 + screen_info area)。
- **不管**:运行时识别(框架 screen matching 自己跑);gameplay 跨画面流程文档(另成 `docs/game/gameplay/*.md`,本 skill 只管单画面);整 screen 级 CRUD(增删整个画面,本 skill 只 area 级)。

## 关键决策与理由
1. **五步流(客观 → 主观 → 建档 → 缺口 → 建模)**:先客观(analyze,识别器视角)再主观(vision,人视角),避免只看一方漏信息;缺口分析把「已知 / 未知」显式化;建模放最后(基于缺口,不盲目建)。
2. **预设提问(用户点 1)**:用户常带「这画面跟 X 相关」的提示。直接问 vision「描述画面」太泛、漏重点。判据:按提示类别问典型元素 → vision 聚焦、产出更准。
3. **主动建模图标按钮(用户点 2)**:文字按钮 OCR 覆盖;图形 / 图标按钮 OCR 看不见(实测「打开游戏」右下 4 圆圈按钮,OCR 只零碎识出一个 `C`)。判据:图形按钮 → 传统 CV(HoughCircles / 轮廓圆度)定位 → `TemplateInfo` 裁模板 → `upsert_screen_area` 入 screen_info → analyze 回验。把「OCR 盲区」也建上模型。
4. **MCP 直调、CRUD > 手编(踩坑固化)**:
   - 早期写过 `streamablehttp` 客户端脚本调 server,其实 `mcp__zzz_od__*` 工具一开始就在工具列表里 → 固化「先直调」。
   - 改名模板时手编了 `enter_game.yml` + 重命名目录,漏了 `_od_merged.yml` 合并缓存 → daemon 按旧缓存加载报「未找到模板」。根因:只有 `save_screen` 同步合并缓存。→ 固化「area 改动走 CRUD 工具」。
5. **识别快照三段式(匹配画面 + 匹配 area + 全量 OCR)**:匹配 area 看识别器认出啥(含 template_id);全量 OCR 是权威文本源(area 维护的文字可能不全 —— 实测「同意隐私政策」area 文字残缺)→ 两边都留,重叠正常,不去重。

## 落点
- `skills/zzz-od-dev-screen-onboarding/`(`SKILL.md` + `design.md`),junction 到 `.claude/skills/`(每人本地建,不提交)。
- 开发类前缀 `zzz-od-dev-`(项目开发流程),与 `zzz-od-dev-deciding-a-fix` 等同列。

## 后续(实战完善)
初版基于「打开游戏」一例。后续 onboard 更多画面时,按实战补:
- ✅ **子态处理**(已补,2026-07-06):onboard「退出登录弹窗」时发现它是「打开游戏」的子态(模态),应并进父 doc 而非另开。SKILL.md 第 3 步加了判据(独立 vs 子态)。
- ✅ **状态流转记录**(已补,2026-07-06):onboard「账号确认态」时发现多子态画面要记"动作→下一态"的流转(loading→ready→弹窗→账号确认),光记"何时出现"不够。SKILL.md 第 3 步「何时出现」扩成「何时出现 + 状态流转」(入口/出口)。
- ✅ **状态指示图标 → 每态一模板**(方法确立,2026-07-06):下拉 ▽/△(收起/展开)用每态一个模板 + 阈值 0.9 区分,实测各配自家 1.0、互不串。radio 选中态同理(建模待补,方法已明)。SKILL.md 第 5 步加了说明。
- ✅ **pc_rect +10 约定**(已补,2026-07-06):template area 的 pc_rect = 模板 bbox 每边 +10px(项目编辑器约定,`devtools_screen_manage_interface` L640「稍微比模板大一点」,防匹配大小/位移偏差)。SKILL.md 第 5 步加了。初版圆形用了 7px、三角不对称,已全部校到 +10。
- ✅ **子态快照编号标题**(已补,2026-07-06;2026-07-14 改 `###`):多子态画面的识别快照,每子态用 `### N. 子态名(source_image)`(`## 识别快照` 下一级,符合 markdownlint MD001;原用 `####` 跳级触发 MD001)而非加粗(加粗在 6+ 子态里扫不出层次)。SKILL.md 第 3 步。
- ✅ **信息源三层并用**(方法确立,2026-07-11):onboard「大世界」时 doc 漏写左上角「按钮-菜单」(汉堡≡)—— `normal_world_basic.yml` 的 `area_list` 本有此 area,但它是纯坐标(无 text/template)不参与 analyze 匹配,只看截图就漏了;同期 onboard「邮件」靠读 `email.yml` area_list + email app 的 `@operation_node` 链快速理清跳转。→ 决策:建档信息源三层并用(截图 analyze/vision + screen_info area_list + application 代码);analyze 只返当前帧命中 area、screen_info 才是全集;doc 可交互元素/流转要与 area_list 逐条对齐。SKILL.md 加「信息源」段。
- ✅ **vision 必需,不只 MCP**(方法补强,2026-07-12):第 2 步「主观理解」原仅"读图(Read/vision)",太弱 —— OCR 看不见图形按钮/布局/状态图标(选中/已读/可领)/模态性/角色朝向。强化为「多模态 vision 必需,每张建档截图都要看;不只靠 MCP analyze;vision 失败(如 400)必重试不跳过」。实测反面:scratch_card 刮态 vision 400 没重试就跳过 → doc 漏刮层布局细节;误把「大世界-普通」当独立画面(实为报刊亭是大世界子态)。
- ✅ **截图获取:手动分解,不跑 app 中途**(方法确立,2026-07-12):跑 app 中途 capture 抓不到画面(app 快 + 子态时机 + 运行慢三重叠加)。实测 scratch_card / drive_disc_dismantle / engagement_reward / city_fund 跑完回大世界时 capture,目标子态(嗷呜对话/刮层/快速选择/领取弹窗)早已错过;scratch_card 更受每日一次时机限制。→ 决策:手动分解动作为单步(transport / move / interact / drag 各一步 + capture),逐步截图;跑 app 仅用于验证流程 / 到位。配套:**transport 朝向重置** —— 传送后角色朝向继承传送前(同地图),手动复现 app 的 `move_w`+`interact` 前需先传送别的地图再回目标,重置朝向到默认。SKILL.md 加「截图获取」段。
  - **后续补强(2026-07-12,scratch_card 实战)**:**操作后等动画再 capture**(底层 click/key_tap/drag 无内置等待,等待在 operation round 层 success_wait,MCP 不经;F 交互后立即 capture 截到旧画面);**move 后 sleep ~1s**(防 interact 失效,issue #2405,scratch_card 代码就是这么 sleep 1);**interact F 长按 press_time=0.2**(短按交互无效);**sleep 建议值**(click 1s / move 1s / interact 1-2s / esc 0.5s / drag 0.5s)—— MCP click_game/key_tap/drag 描述也加了提醒(不加 post_sleep 参数,底层无,描述提醒即可)。
- ✅ **Transport 失败 = 地图未探索**(方法确立,2026-07-12):onboard `hou_hou_bakery`(吼吼饼铺,3.0 玩法,布亚斯特城区)时 `run_operation Transport(布亚斯特城区, 吼吼饼铺)` 两次失败 —— `get_run_status` 显「执行传送」节点、~88s 超时;server 日志看清:Transport 打开地图后 88s 一直 OCR 地图区域视图(布亚斯特城区 / 六分街 / 澄辉坪…)、选不中吼吼饼铺传送点。根因:用户**未探索布亚斯特城区**,吼吼饼铺传送点未解锁(3.0 新地图需先跑图)。→ **优先排查:传送点没出现 / Transport 选不中 多为该地图未探索**(新版本玩法 / 新城区尤甚);但 OCR 识别 / 地图加载 / 目标名称不匹配 / 超时也会同状 —— 结合地图截图 + server 日志 + 超时节点确认后再下结论(勿唯一归因)。SKILL.md「截图获取」加排查判据;建档选 app 优先已探索解锁的。
- ✅ **mock 测试断言要看 node 返回类型(round_wait vs round_success)**(踩坑固化,2026-07-12):trigrams_collection 测试照搬 scratch_card 的 `assert result.is_success` 失败 —— `get_trigram` 主界面态返 `round_wait(status='卦象集录')`(点 area 后等下一轮,is_success=False),而 scratch node 返 `round_success`(is_success=True)。诊断证实 **OCR 全链路正常**:webp q90 离线 OCR 完美识别「卦象集录」(印证 design「q90 无损」)+ crop 下半屏 OCR 也识别 + `match_word_list_by_priority` 匹配 word='卦象集录';失败纯因 `is_success` 判 `round_wait`。→ **不是 webp / OCR 不稳**;判据:mock 测试断言要看 node 返回的 `OperationRoundResult` 类型 —— `round_success` / `round_by_find_area` 命中用 `is_success`;`round_wait` / `round_retry` 用 `status`(匹配词);**先读 node 代码确认返回类型再写断言,别照搬别的 app**。通用断言判据已沉淀到 `docs/develop/testing/README.md` 第 3 节「断言:看 node 返回类型」。
- ✅ **vision 第 3 人称视角盲区**(踩坑固化,2026-07-12):suibian_temple 入口建档时 vision 判「角色背对随便观入口」,实际是**第 3 人称追尾视角** —— 摄像机在主角身后,看到主角背部 = 主角**正对前方**(狮耶/入口),vision 不懂第 3 人称语义误判「背对」,差点误导走「跨地图朝向重置」弯路(用户纠正)。→ 判据:**本游戏追尾视角下,看到角色背部 = 正对前方**(仅适用追尾摄像机 + 当前场景,勿泛化所有第三人称画面);vision 对朝向 / 视角的判断要谨慎,以 OCR(交互提示如「前往 XX」)+ 实际交互结果为最终判据,别轻信 vision 的「朝向」推断。
- ✅ **兜底画面方法论(loading / 对话)**(方法确立,2026-07-12):suibian_temple 入口建档时 interact 狮耶触发 NPC 对话,analyze `screens=[]`(无精准匹配)—— 这类**无固定文字特征的通用画面**(NPC 名不固定 / 旁白无 / loading 黑屏 + lore tip)analyze 必无匹配,但**结构固定**(对话下方对话框 + `好感度标题` area;loading 黑屏 + 进度 / tip)。→ 决策:缺口分析(第 4 步)无匹配时,**先想兜底画面**(loading / 对话),按结构 + 位置 area 判定 + 建档(不必精准 screen 匹配)。建档「对话」(`docs/game/screens/对话.md`)+ 加载画面同属兜底。SKILL.md 第 4 步加判据。
- ✅ **建档截图考虑测试可用性**(方法确立,2026-07-13):归档的 webp 就是 mock 测试 fixture(测试仓 `screens/<name>/<state>.webp`,见 [testing/](docs/develop/testing/)),截图不只为文档溯源,更要让测试稳定用 —— **稳定态**(非过渡帧,操作后 sleep 等动画完)、**覆盖关键 area**(测试断言依赖的 id_mark / 文字 area 在帧内 + 命中)、**多子态每态一张**(测不同分支)、**文件名 = 可读 state**(fixture 引用)。→ SKILL.md 第 6 步加「测试可用性」段;判据:**截完 `analyze_screen` 命中目标 area 才归档**,过渡帧 / 漏 area 的重截(别凑合)。
- ✅ **手动复现 move 距离要和 app/operation 一致,入口交互对象从代码确认**(踩坑固化,2026-07-13):suibian_temple 入口实拍时 `key_tap w` 走 2.5s 错过交互点 —— `SuibianTempleApp.goto_suibian_temple` **无 move**(Transport 后直接 OCR「前往随便观」,传送点就在狮耶 / 随便观入口交互范围内),我却盲走 2.5s 过了交互点;同期误以为入口是「OCR 点文字」,实际是 **Transport 后传送点旁 interact 狮耶**(NPC)→ 出「前往随便观」。→ 判据:**手动分解 move 前,先看 app/operation 的 `move_w` `press_time`**(如 `coffee`/`random_play` POINT_1 是 `turn_to_angle` + `move_w 1s`;`suibian_temple` 无 move 就**不走**,传送点已在交互范围);走多了错过交互点(角色过头,交互提示消失)。入口交互对象(狮耶 / 建筑入口)从 app 代码 / OCR 确认,别盲走;走之前先 `capture` 看 F 提示文本(交互对象名)。
- ✅ **可交互 NPC 判据:`>` 名字 `<` 三角形 + 补档先看 app/operation**(踩坑固化,2026-07-13):suibian_temple 入口实拍时 vision 误判「需走 1-2 步才到狮耶交互范围」,实际 Transport 后传送点旁狮耶**已可交互** —— 绝区零走近 NPC 交互范围时,NPC 名字左右出现 `>` `<` 三角形标记(如 `> 狮耶 <`);OCR 只识出「狮耶」漏了三角符号,vision 不懂这约定 → 双双误判「没到,还要走」(我盲走 0.5~2.5s 反而过头)。→ 判据:**可交互 NPC = 名字左右 `>` `<` 三角形**(出现即已在交互范围,`interact F` 即可,不需再走);OCR 漏符号时看 NPC 名是否在画面稳定 + 对照 app 假设的位置;**vision 提示词要明确「可交互 NPC 名字左右有 `>` `<` 三角形,出现即已可交互,不要再走」**。补档实拍**先读 app/operation 代码**(move/interact 距离 + 交互对象 + 画面跳转)再动手,别只靠 vision 推朝向/距离。
- ✅ **run_operation 跑单个 op 也消费中间画面 + goto_suibian_temple 无 interact**(踩坑固化,2026-07-15):抓 Transport 传送后「自动进入随便观」确认弹窗,用 `run_operation Transport` + sleep + capture —— op 已自动点掉弹窗、落地入口,抓不到弹窗。核实 app 代码:`goto_suibian_temple` **无 `controller.interact` / `key_tap('f')`**,只 OCR 点「确认」「领取收益」+ `check_and_update_current_screen`;上面「interact 狮耶→出前往随便观」是**手动实拍操作**,非 app 逻辑,搞混了。→ 判据:`run_operation` 跑单个 op 和 `run_standalone_app` 一样**自动消费中间画面**(op 按 `@operation_node` 自己点各弹窗),sleep 间隔 capture 只看结果;抓中间态按 op 节点逻辑手动 click+capture(弹窗处停下不点)。核实 app 流程**读代码**,别把手实拍当 app 逻辑。SKILL「截图获取」已含 `run_operation`。
- ✅ **vision 状态推理不可信,只信客观描述**(踩坑固化,2026-07-15):实拍随便观游历,反复用 OCR 盲点副本切换没切中(副本选中态 = `>`名字`<` 三角形,OCR 看不见);转用 vision 后,vision 看「剩余20时00分」猜「制造区2 已派遣」,实际是 `choose_period` 选的时间**预览**(未派遣态),那时间不是进行中倒计时 —— 真已派遣显示「提前收获」按钮(`choose_period` 检测它 → `already_dispatch`)。→ 判据:**vision「描述画面有什么」(元素/文字/位置/标记/颜色)可信,「判断状态/作用」不可信**(不懂游戏会瞎猜);prompt 要客观(描述内容 + 位置),别问状态;**状态结合代码自己推**。副本选中 = 名字左右 `>` `<` 三角形(vision 看)。SKILL 第2步已加「重点描述画面内容」+ memory `vision-required-for-state`。
- ⬜ **批量同屏改动**:多个 area 批量更新(如 5 个 pc_rect 修正)用 MCP 客户端**串行脚本**(1 turn)比 N 次**直调**(5 turn,同屏 save 写竞争需串行)高效;skill 的「直调 > 脚本」该对**批量**放宽说明 —— 待补。
- 各类画面(战斗 / 养成 / 日常)的典型元素清单(反哺第 2 步预设提问)。
- 更多形状的图形按钮(非圆形)的 CV 判据。
- screen_info 缺口的常见模式。
