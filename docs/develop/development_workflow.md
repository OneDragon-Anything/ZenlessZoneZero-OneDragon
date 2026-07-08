# 开发流程

> 一个功能从立项到交付的端到端链路。AGENTS.md 有 always-on 骨架;本页给详细判据、实例与配套更新规则。
>
> 当前只覆盖**游戏自动化功能**(已验证场景:OpenAndEnterGame)。bug 修复 / 性能 / UI / 模型等其他类型见文末「其他类型」,后续补。

## 主干

流程主干采用团队共识的 [superpowers](https://github.com/anthropics/superpowers)(brainstorming → writing-plans → TDD → review → finishing-a-branch);本页只讲**本项目在各阶段要插入的项目特定动作**。

## 游戏自动化功能

以 **OpenAndEnterGame(打开并登录游戏)** 为实例。

### 1. 画面建档(涉及新画面 / 交互时)

**触发**:新增或改变游戏画面、可交互元素时(纯逻辑 / 算法 / 配置改动不用)。按 `zzz-od-dev-screen-onboarding` skill:

- 截图 → `analyze_screen` 客观识别(匹配画面 / area / 全量 OCR)。
- 主观理解 → 建画面文档 `docs/game/screens/<screen>.md`(子态 / 特征 / 可交互元素 / 识别快照)。
- 缺口分析 → 主动建模图形 / 图标按钮(模板 / CV),经 CRUD 工具入 screen_info。
- 归档代表截图到测试仓 `screens/<screen>/<state>.webp`(测试 fixture + 文档溯源)。

> OpenAndEnterGame 实例:登录各子态(ready / 登录服务器中 / 登录成功 / 加载画面 / 大世界)逐一建档 + 建模(含图形按钮如登录页 ◀ 后退)+ 归档 webp。

### 2. 开发

做成 `Application`(放 `src/zzz_od/application/`,经 `ApplicationFactory` 接入)+ `Operation` 节点编排 flow;复用现有配置体系(YAML / `YamlConfig`)与界面(setting card / `YamlConfigAdapter`)。架构细则见 AGENTS.md「功能开发优先路径」。

> OpenAndEnterGame 实例:`OpenAndEnterGame` 是一个编排 `OpenGame` + `EnterGame` 的 **Operation**(被 app 调用进入游戏);`OpenGame` 负责启动游戏进程(及相关系统设置),`EnterGame` 负责屏幕驱动,详见 [zzz/enter_game.md](zzz/enter_game.md)。

### 3. 测试

用留档截图在测试仓补**流程测试**(多帧 / 轮询 / 重试 / 恢复分支)用 `FixtureController`(`MockController` 子类);单节点识别用简单 mock。规范见 [testing/](testing/README.md)。

> OpenAndEnterGame 实例:`test_enter_game_flow.py` 用 `FixtureController` 跑 `EnterGame` 自动登录全流程(ready → 点进入 → 登录服务器中 → 登录成功 → 加载 → 大世界)。

### 4. 提 PR

跨仓 PR 顺序:**先建测试仓 PR,再建主仓 PR**:

1. 测试仓改动先提交、推送、开 PR(`git -C zzz-od-test`),拿到测试仓 PR 链接。
2. 主仓开 PR,**描述里带上测试仓 PR 链接**(reviewer 可跳转看测试改动);主仓与测试仓用**同分支名**(CI 按分支名 clone 测试仓)。
3. assign **DoctorReid / ShadowLemoon**,按 `zzz-od-dev-pr-finishing` skill 走 review(逐条回复 / 修正、清 unresolved thread、处理 CodeRabbit);**关联 PR 一起收尾、合并顺序(测试仓先)见该 skill §6**。

### 5. 配套产出(按需)

| 产出 | 何时做 | 在哪 |
|---|---|---|
| 开发文档 | 代码 / 架构变化 → **总要** | `docs/develop/` |
| 游戏知识库 | 画面 / 玩法变化 | `docs/game/`(画面建档时同步) |
| 模型 | 涉及 YOLO 检测 | yolo 训练仓 + dataset(见 [相关仓库](setup/repositories.md)) |
| **使用说明(blog)** | **用户可见的功能 / 操作变化**(新功能、改用法、GUI 变化) | blog 仓;纯内部重构 / 性能 / 无感 bug → 不用 |

## 其他类型(后续补充)

尚无足够实例,流程待补;不提前臆造。已知方向:

- **bug 修复**:`systematic-debugging`(定位)→ `zzz-od-dev-deciding-a-fix`(定修法)→ 改 → 回归测试 → PR。
- **性能优化**:定位瓶颈 → 改 → benchmark 验证 → PR。(待实例)
- **UI / GUI**:复用 Fluent widgets / setting card → 视觉 / 交互验证 → PR。(待实例)
- **模型 / 识别**:跨 yolo / dataset 仓训练 → release → 主仓消费。(待实例)
