# 游戏知识库

> 给智能体(本地 AI)理解游戏的领域知识,与 `docs/develop/`(开发文档)平级、性质不同。
> Part A 的 `analyze` **不读** 本目录(运行时解耦);本目录是离线知识,日后反哺/重构 `screen_info` 模型。

## 目录

- `screens/` — 画面描述(1 md ↔ 1 画面,对齐 `assets/game_data/screen_info/<name>.yml`)
- `gameplay/` — 玩法(跨画面机制/系统)

## 记录规范

1. **双向引用(必备)**:
   - `screens/*.md` frontmatter `appears_in`:本画面出现在哪些玩法(用 `gameplay_name`)。
   - `gameplay/*.md` frontmatter `involves_screens`:本玩法经过哪些画面(用 `screen_name`)。
2. **关联键**:一律用 `screen_info.screen_name`(中文,**非 `screen_id`**);`gameplay` 用 `gameplay_name`。
3. **正文自由**:不强制 schema —— 先自由记录,收集完再统一分析、反哺 `screen_info`。
4. **截图基线**:每篇画面 frontmatter 可带 `last_updated`(核对日期)+ `source_image`(当前基线来自哪张 `.debug/images/` 截图)。截图文件名是一次性捕获 ID、易失 —— **正文绝不写死具体 ID**,变更复核走方法(重新截图 → `analyze_screen` → 与 OCR 快照 diff → 更新 `last_updated`/`source_image`)。归档测试用 webp 版(可读名)见 [截图存档方法论](../develop/zzz/screenshot_archive.md)。
5. **识别快照**:每篇画面文档记一份 `analyze_screen` 快照 = ① **匹配画面**(`screen_name` + `is_precise`);② **匹配 area 表**(取自 `screens[].areas`:area_name / 类型 `text`|`template` / 文本或 `template_id` / conf / 位置);③ **全量 OCR 文本**(`ocr_texts`)。注:MCP 的 `ocr_texts` 保持全量(area 维护的文字可能不全),故文字 area 在②③两边都出现属正常。

## 演化路径

自由积累 → 统一分析 → 反哺/重构 `screen_info` 模型(沿用 CLAUDE.local.md「增量 → 合并回主 spec」)。
