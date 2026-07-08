---
name: zzz-od-dev-screen-onboarding
description: 当拿到一张游戏截图、需要分析它并纳入游戏知识库(docs/game)+ screen_info(建档 + 建模其可交互元素)+ 归档代表截图时用。
---

# 画面入职(analyze → 建档 → 建模)

拿到截图后按「客观识别 → 主观理解 → 建档 → 缺口分析 → 主动建模」推进。每步给判据。

## 前置:工具用法(避免绕路)
- MCP 工具**直调**(`mcp__zzz_od__analyze_screen` / `upsert_screen_area` / `delete_screen_area`),别写 HTTP 客户端脚本绕路;连接 stale 让用户 `/mcp` 重连。
- screen_info 的 area 改动**一律走 CRUD 工具**(`upsert_screen_area`/`delete_screen_area`)—— 它们经 `save_screen` 同步独立 yml + `_od_merged.yml` 合并缓存 + reload。**禁止手编 screen_info yml 或手改模板目录**:手编不重算合并缓存,daemon 按旧缓存加载 → 找不到模板/area。

## 1. 客观识别:跑 `analyze_screen`
`analyze_screen(screenshot=<绝对路径 或 .debug/images 图名>)`,取三样:
- **匹配画面** `screens[].screen_name` + `is_precise`(精准 / 模糊 / 无匹配)。
- **匹配 area** `screens[].areas`(area_name / 类型 `text`|`template` / 文本或 `template_id` / conf / 位置)。
- **全量 OCR** `ocr_texts`(全部文字,含噪声/动态值)。area 维护的文字可能不全 → 全量 OCR 是权威文本源,与匹配 area 的文字**重叠属正常,勿去重**。

## 2. 主观理解:看图 + 预设提问
读图(Read / vision)。若用户给了**画面相关提示**,向 vision 提**偏向该类画面典型元素**的问题:
- 判据:提示指向某类画面 → 问该类的**典型可交互元素 + 状态文本**(而非泛泛「描述画面」);无提示 → 通用问布局 / 可交互元素 / 文字 / 图标 / 当前状态。
- 明确区分**可交互元素**(按钮 / 输入 / 图标)与**展示信息**。

## 3. 建档
先判:**独立画面**还是**已建档画面的子态**(模态/弹窗/状态,如对话框、loading/ready 子态)?
- **独立画面** → 新建 `docs/game/screens/<name>.md`(中文 `screen_name`;文件名英文 snake_case、不带冒号等特殊字符),登记进 `docs/game/screens/README.md` 索引(一行)。
- **子态** → 并进父画面 doc:「何时出现/状态流转」补该子态的**入口(从哪来)+ 出口(动作→下一态)**、「可交互元素」补该态元素、「识别快照」加该态子表;不另开文件、不登索引。

新画面 doc 结构:
- frontmatter:`screen_name` / `appears_in: [gameplay_name...]` / `last_updated`(核对日期)/ `source_image`(.debug/images 基线图名)。
- **何时出现 + 状态流转**:出现条件 + 前后邻居;**多子态画面必须记状态流转**(每子态:入口 = 从哪来[动作/条件]、出口 = 动作→下一态),用表格或链式表达。
- **识别特征(稳定锚点)**:稳定文字 / 模板图标 / 固定图标;标注易变值(版本号 / 进度 / 公告)勿当特征。
- **可交互元素**:按钮 / 输入 / 图标;图形按钮注明「需模板/CV」。
- **识别快照** = ① 匹配画面(screen_name + is_precise);② 匹配 area 表(area_name / 类型 / 文本或 template_id / conf / 位置);③ 全量 OCR 文本。**多子态画面**的每子态快照用 `#### N. 子态名(source_image)` 编号子标题(加粗在多子态里不够显眼)。
- **备注**:screen_info 现状(缺口 / 误匹配隐患)、变更检测方法、易变点。

## 4. 缺口分析
对照「匹配 area」与「可交互元素 / 识别特征」:
- 命中且 conf 高 → 已建模。
- 模糊误匹配(`is_precise=False` 且命中无关 area)→ 记隐患(screen_info 该收紧 / 加精准特征)。
- 无匹配(`screens=[]`)→ screen_info 缺口,画面未收录。
- 可交互元素无对应 area → 进第 5 步建模。

## 5. 主动建模:图形 / 图标按钮
文字按钮 OCR 多已覆盖,无需此步。**图形 / 图标按钮**(OCR 看不见)按下面流程。**状态指示图标**(radio 选中/未选中、下拉 ▽/△、勾选框)同属此类 —— OCR 读不准状态,用**每态一个模板**(如 ▽ 收起 / △ 展开)+ 适高阈值(如 0.9)区分状态。
1. **定位**:圆形 → `cv2.HoughCircles`(扫 param2 / 半径,取稳定命中数);其它形状 → 轮廓 + 圆度 `4πA/P² > 0.7` 或颜色阈值。两法互相印证。
2. **裁模板**:用项目 `TemplateInfo` 生成(结构对齐既有模板:`raw.png` + `mask.png` + `config.yml`,`template_shape: circle` / `auto_mask: true` / `point_list: [圆心, 边缘点]`)。⚠️ `screen_image` 必须用**原始截图**(PNG / 未压缩),不要用 webp 归档版(lossy → 小区域裁剪放大 artifacts → 模板 conf 降)。
3. **入 screen_info**:`upsert_screen_area(screen_name, area_name, pc_rect=[x1,y1,x2,y2], template_sub_dir, template_id, ...)`。area_name 用功能名(中文),template_id 用英文 snake_case;`pc_rect` = 模板 bbox **每边 +10px** 再**夹到画面边界**(`max(0,·)` / `min(1920,·)` / `min(1080,·)`,贴边时余量自动收窄;项目约定「稍微比模板大一点」,对齐 `devtools_screen_manage_interface` 导入逻辑),防匹配大小/位移偏差;且不重叠邻接按钮。
4. **回验**:再跑 `analyze_screen`,确认新 area 命中、conf 高。

## 6. 归档代表截图
onboarding 的画面都要归档一张代表截图(多子态画面每子态一张)到测试仓 `screens/<screen_name>/<state>.webp`,供后续测试 fixture + 文档溯源。

**格式**:webp q90(省空间且识别无损)/ 1080p 原生不缩放(同 screen_info 坐标)/ 文件名用可读 state 名(如 `ready.webp`)/ screen_name 含冒号用下划线(如 `警告_游戏前详阅`)/ **中文路径用 `cv2.imencode('.webp', img, [cv2.IMWRITE_WEBP_QUALITY, 90])` + `ndarray.tofile(path)`,别用 `cv2.imwrite`**(Windows 中文路径会挂)。

详见测试仓 `screens/README.md` 或项目中的画面截图存档方法论文档。

## 收尾判据
- 改动经工具(MCP 直调 > 脚本;CRUD > 手编 yml);稳定特征 > 易变值;图形按钮 CV/模板 > OCR。
- 模板改名 / 加 area 涉及多文件(目录、config、yml、合并缓存)→ 一律经工具或同步合并缓存,别只改一处。
