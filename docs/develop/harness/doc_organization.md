# 项目知识文档组织

> 游戏自动化功能的**知识**该沉淀到哪个 doc、各 doc 写什么、怎么互引。
> 依据:随便观建档实战(第一版 gameplay 写成代码视角 → 翻转)。

**一句话**:一个游戏功能的知识分**四个维度**写进四类 doc,各自专注、互相引用,不重复。

## 四文档维度

| 文档(目录) | 维度 | 回答 | 给谁 |
|---|---|---|---|
| `docs/game/gameplay/<名>.md` | **玩法机制**(目标性玩法) | 游戏里这玩法是什么、规则、资源、循环、目标(经营/战斗/登录) | 理解玩法的智能体(决策 / 判断状态) |
| `docs/game/mechanics/<名>.md` | **通用机制**(非玩法的游戏机制) | 跨 screen 的通用操作/机制(传送/对话/商店),无玩法目标循环 | 理解通用机制的智能体 |
| `docs/game/screens/<名>.md` | **画面识别** | 各画面长啥样、id_mark / area、怎么识别 / 操作 | 做画面识别 / 操作的智能体 |
| `docs/develop/zzz/application/<名>.md` | **自动化方案**(app 设计 / 使用) | 怎么自动化这玩法(脚本流程 / 配置 / 前置 / 设计决策) | 开发 / 使用这个 app 的人 |

同名跨目录(如三处都叫 `随便观.md`),靠**目录**区分维度,不靠文件名。

## 各写什么 / 不写什么

- **gameplay**:玩法机制(玩家视角) —— 这是什么 / 目标 / 资源 / 经济循环 / 核心机制 / 子玩法游戏含义。⚠️ **不写代码编排**(那是 develop application)。代码(`@operation_node`)是反推玩法的工具,编排降附录或引用 develop。
- **mechanics**:通用机制(非玩法) —— 跨 screen 的游戏机制 / 操作(传送两种地图 / 入口 / 传送点类型、对话、商店机制等),无玩法目标循环。引用相关 screen。
- **screen**:单画面细节 —— id_mark / area 全集 / 状态态 / 识别判据 / 踩坑。不写跨画面流程(那是 gameplay / mechanics)。
- **develop application**:自动化方案 —— 脚本流程(做什么 + 为什么)/ config 配置(对齐代码,标已实现·计划)/ 使用前置 / 设计决策。玩法机制引用 gameplay,不重复。

## 互引规则

- gameplay ↔ screen:`gameplay.involves_screens` + 各 `screen.appears_in(gameplay_name)`。
- mechanics ↔ screen:`mechanics.involves_screens` + 各 `screen.appears_in(mechanics_name)`。
- gameplay ↔ develop application:develop 引用 gameplay(玩法背景);gameplay 附录引用 develop(自动化实现)。
- 用完整相对路径,不靠文件名猜。

## 判据:何时建哪个

- 跨 ≥2 画面的**玩法**(目标循环 / 资源) → `gameplay/<名>.md`(参考型,写现状);方法论见 skill `zzz-od-dev-gameplay-onboarding`。
- **通用机制**(非玩法,跨 screen,如传送 / 对话 / 商店) → `mechanics/<名>.md`。
- **单画面**建档 → `screens/<名>.md`;方法论见 skill `zzz-od-dev-screen-onboarding`。
- app 实现(脚本 / 配置 / 前置) → `develop/zzz/application/<名>.md`。
- 一个功能按需建(玩法 + 机制 + 画面 + 自动化),互引;轻功能可只建需要的。

## 教训

随便观第一版 `gameplay/随便观.md` 写成「app 节点链 + config 开关」说明书(代码视角),用户指出「只是描述 app/op 编排,没写玩法本身」→ 翻转:gameplay 改玩法视角,代码编排归 develop application。**根因**:没分清"玩法机制"和"自动化实现"是两个维度。详见 skill `zzz-od-dev-gameplay-onboarding` 的 design.md。

## skill vs doc 分界

- **skill 记方法论**(怎么做):建档流程 / 通用判据(如 `>名字<` 可交互)/ 排查思路(transport 失败 → 查目标点解锁)。
- **doc 记具体知识**(是什么):键位 / 坐标 / 具体流程 / 游戏机制。
- 例:传送的 `M=3D / N=普通` / 传送点类型 / 入口 = **具体知识** → doc(`mechanics/传送.md`);transport 失败的**排查思路** = **方法论** → skill。别把具体游戏事实塞进 skill。
