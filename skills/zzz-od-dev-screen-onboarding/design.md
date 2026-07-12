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
- ✅ **子态快照 #### 编号标题**(已补,2026-07-06):多子态画面的识别快照,每子态用 `#### N. 子态名(source_image)` 而非加粗(加粗在 6+ 子态里扫不出层次)。SKILL.md 第 3 步加了。
- ✅ **信息源三层并用**(方法确立,2026-07-11):onboard「大世界」时 doc 漏写左上角「按钮-菜单」(汉堡≡)—— `normal_world_basic.yml` 的 `area_list` 本有此 area,但它是纯坐标(无 text/template)不参与 analyze 匹配,只看截图就漏了;同期 onboard「邮件」靠读 `email.yml` area_list + email app 的 `@operation_node` 链快速理清跳转。→ 决策:建档信息源三层并用(截图 analyze/vision + screen_info area_list + application 代码);analyze 只返当前帧命中 area、screen_info 才是全集;doc 可交互元素/流转要与 area_list 逐条对齐。SKILL.md 加「信息源」段。
- ✅ **vision 必需,不只 MCP**(方法补强,2026-07-12):第 2 步「主观理解」原仅"读图(Read/vision)",太弱 —— OCR 看不见图形按钮/布局/状态图标(选中/已读/可领)/模态性/角色朝向。强化为「多模态 vision 必需,每张建档截图都要看;不只靠 MCP analyze;vision 失败(如 400)必重试不跳过」。实测反面:scratch_card 刮态 vision 400 没重试就跳过 → doc 漏刮层布局细节;误把「大世界-普通」当独立画面(实为报刊亭是大世界子态)。
- ✅ **截图获取:手动分解,不跑 app 中途**(方法确立,2026-07-12):跑 app 中途 capture 抓不到画面(app 快 + 子态时机 + 运行慢三重叠加)。实测 scratch_card / drive_disc_dismantle / engagement_reward / city_fund 跑完回大世界时 capture,目标子态(嗷呜对话/刮层/快速选择/领取弹窗)早已错过;scratch_card 更受每日一次时机限制。→ 决策:手动分解动作为单步(transport / move / interact / drag 各一步 + capture),逐步截图;跑 app 仅用于验证流程 / 到位。配套:**transport 朝向重置** —— 传送后角色朝向继承传送前(同地图),手动复现 app 的 `move_w`+`interact` 前需先传送别的地图再回目标,重置朝向到默认。SKILL.md 加「截图获取」段。
  - **后续补强(2026-07-12,scratch_card 实战)**:**操作后等动画再 capture**(底层 click/key_tap/drag 无内置等待,等待在 operation round 层 success_wait,MCP 不经;F 交互后立即 capture 截到旧画面);**move 后 sleep ~1s**(防 interact 失效,issue #2405,scratch_card 代码就是这么 sleep 1);**interact F 长按 press_time=0.2**(短按交互无效);**sleep 建议值**(click 1s / move 1s / interact 1-2s / esc 0.5s / drag 0.5s)—— MCP click_game/key_tap/drag 描述也加了提醒(不加 post_sleep 参数,底层无,描述提醒即可)。
- ⬜ **批量同屏改动**:多个 area 批量更新(如 5 个 pc_rect 修正)用 MCP 客户端**串行脚本**(1 turn)比 N 次**直调**(5 turn,同屏 save 写竞争需串行)高效;skill 的「直调 > 脚本」该对**批量**放宽说明 —— 待补。
- 各类画面(战斗 / 养成 / 日常)的典型元素清单(反哺第 2 步预设提问)。
- 更多形状的图形按钮(非圆形)的 CV 判据。
- screen_info 缺口的常见模式。
