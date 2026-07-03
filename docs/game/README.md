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

## 演化路径

自由积累 → 统一分析 → 反哺/重构 `screen_info` 模型(沿用 CLAUDE.local.md「增量 → 合并回主 spec」)。
