# 测试方法论

> `docs/develop/testing/` 的入口。测试代码在独立仓 `zzz-od-test`(主仓 `.gitignore` 忽略它,clone 到主仓根目录用)。本目录记**怎么跑测试 + 测试基建 + 怎么判断写哪些 + 怎么写**。

## 1. 测试在哪 / 怎么跑

- 测试代码在独立仓 [zzz-od-test](https://github.com/OneDragon-Anything/zzz-od-test);clone 到主仓根目录,IDE 里把 `zzz-od-test/` 设为 `Test Sources Root`。
- 主仓不保留测试(`tests/` 已废弃);新测试加到 `zzz-od-test/test/` 对应被测包路径下。
- 环境变量:把 `zzz-od-test/.env.sample` 复制到主仓根 → `.env`(部分测试需要;本地若只跑自己改的部分,可不配全)。
- 跑测试:
  ```shell
  uv run --env-file .env pytest zzz-od-test/
  ```

## 2. 测试基建(`zzz-od-test/test/conftest.py`)

- **`test_context` fixture**(session 级):跑 `ctx.init()` → 真 OCR + 真 screen_info;注入 `MockController`。所有要识别能力的测试都用它(只 init 一次,session 复用)。用 `current_instance_idx=99` 隔离测试配置写盘。
- **mock 下一帧**:
  - `test_context.add_mock_screenshot(img)` —— 设任意图为 controller 下一帧。
  - `test_context.mock_screen(screen_name, state)` —— 从存档 `screens/<screen>/<state>.webp` 读一帧并设上(存档见 [截图存档](../zzz/screenshot_archive.md))。
- **`MockController`**:`screenshot()` 返 mock 帧;`click()` 返 in-bounds bool(不真点)。
- **流程测试**用 `FixtureController`(`MockController` 子类,"会反应的假游戏"),见 [fixture_controller.md](fixture_controller.md)。

## 3. 完整性方法论(核心:拿到 app/op → 怎么判断写哪些测试)

### 完整性判据(一句话)

一个 app/op 的测试**完整**,当且仅当:

1. **每个节点的每个分支**都有单测(动作一,**适用所有节点**);且
2. **返回 `round_wait` 或用 `until_*` 的节点**额外有流程测试(动作二);且
3. **status 契约**在写测试时人工对照下游 `@node_from`(动作一第 3 步)——**不写对账工具**(扫描不可靠,见 §3 末)。

> 拓扑合法性(节点/边/start 唯一)框架加载时校验(`operation.py:241-259`+`:312-313`+`:357`),**不计入测试职责**。

### 动作一:数全分支 + 完整覆盖 + 对照下游(适用所有节点)

对每个 `@operation_node` 节点,确定它的**分支**(= 可能返回的 status 集合)。节点有以下几种写法:

- **显式字面量**:body 里有 `round_success/wait/retry/fail(status='xxx')` → 这些 `xxx` 是分支。
- **薄包装**:`return self.round_by_X(...)`(body 无显式 status 字面量)→ 分支 = **helper 返回契约**。常见(查 `operation.py` 该方法确认):
  - `round_by_ocr_and_click_by_priority(targets)` → `round_success(status=匹配的 target)` / `round_retry('未匹配到目标文本')`
  - `round_by_find_and_click_area(screen, area)` → **无 until_**:点击成功 `round_success(area_name)` / 未找到·点击失败 `round_retry` / 区域未配置 `round_fail`;**带 until_**:点击成功先 `round_wait(area_name)`,下轮 until 满足 `round_success(area_name)`
  - `round_by_find_area(screen, area)` → `round_success(status=area_name)` / 未命中 `round_retry`
  - ⚠️ area 类 helper 另有 `round_fail('区域未配置 area')` 分支(配置错误,通常不测,但数分支时要知道)
  - (非完整列表;`round_by_ocr_and_click_with_action` 也能返 `round_wait`、`round_by_click_area`/`round_by_goto_screen` 等查 `operation.py` 确认)
- **混合(显式守卫 + 薄包装)**:先 `if 守卫: return round_X(status='显式字面量')` 再 `return self.round_by_Y(...)`(如 `click_squad_team`:`not self.claim`→`round_success('跳过收获')` + ocr_and_click)→ 分支 = **显式 statuses ∪ helper 契约**,别只数 helper 那部分。
- **委托子 op**:`round_by_op_result(op.execute())` → **0 自有分支**,进子 op 测;委托分支的路由正确性依赖子 op 测试(其下游 `@node_from(status=具体)` 边的 status 来自子 op 返回,对照时查子 op)。

**每个分支一个单测**:mock 该分支输入(先读节点/helper 检测什么——OCR 文本?area?config?status 名是线索)→ 调节点 → 断言返回 `status` + 动作。
- 断言类型按返回走(别照搬 `is_success`):`round_success`/`round_by_find_area` 命中 = True;`round_wait`/`round_retry` = False 看 status。
- 薄包装节点:mock 让 helper **命中 / 不命中**两种帧,断言两种返回。
- `until_find_all`/`until_not_find_all` 多帧:同一 op 实例连续调 2 次。

**完整覆盖 + 对照下游(契约兜底,关键)**:
- **完整覆盖**:上面数出的每个分支都要有单测断言 status,一个不漏。
- **对照下游**:grep 本节点的所有 `@node_from(from_name='本节点', ...)`,把「下游声明的 status」和「本节点返回的 status」对比。⚠️ **只比 `round_success`/`round_fail` 的 status**——`round_wait`/`round_retry` 是节点内自循环/重试(框架 WAIT/RETRY 直接 continue 同节点,不经 `@node_from`,不进下游边):
  - 下游 `status=X` 声明的 X,本节点 success/fail 会返回吗?没有 = **死边**(拼错,或漏测分支)。
  - 本节点 success/fail 返回的 X,有下游接吗?**没有 `status=X` 边不一定是死 status**——可能被 `ignore_status=True` 兜底边接收(框架无精确匹配时走兜底);都没有才是死 status(或 X 是终态——人工判)。
  - **失败路由边**:`@node_from(success=False)` 带**具体 status** 的(status 来自子 op 失败/超时),确认其在失败场景可达(流程测试 mock 子 op 失败覆盖);多数失败边用默认 `ignore_status`(status 无关,安全)。

> ⚠️ 动作一**适用所有节点**,包括动作二判为「要画面变化」的。它们的每个分支也能单帧 mock 测(mock 一帧→调节点→断言返回 `round_wait`/`success`)——单帧 mock 跑完整 `execute()` 会卡死,但**直接调节点方法**不会。

### 动作二:这个节点要不要额外流程测试?

**信号**:节点会返回 **`round_wait`**(= 下一轮重跑自身,期待画面演进),或用了 **`until_find_all`/`until_not_find_all`**。

- **有** → 额外用 `FixtureController`(「会换帧的假游戏」)跑 `execute()`,覆盖「点→等画面变→再识别」的推进/轮询(动作一单测覆盖不到的运行时推进)。五坑:运行态前置 / 看门狗 / 恢复 click `on_click_in` / OpenGame 排除 / 剪贴板规避(见 fixture_controller.md)。
- **没有**(看一眼就返回,或只 `round_retry` 同帧重试)→ 动作一的单测够。
- ⚠️ **`round_retry` 不是画面变化信号**(同帧重试,点击失败 / 未找到)。

> 流程测试是动作一的**补充,不是替代**:流程测试节点仍要动作一逐分支单测。

### 完整度自检 checklist

- [ ] 每节点每分支(含薄包装的 helper 契约分支)都有单测?
- [ ] 返回 `round_wait` / 用 `until_*` 的节点额外跑了流程测试?
- [ ] 每节点写测试时对照了下游 `@node_from`(死边 / 死 status)?

### status 契约:方法论约束(不写对账工具)

- **靠动作一「对照下游」**:写每个节点测试时 grep 其 `@node_from` 对照返回 status,死边/死 status 当场发现。
- **为什么不写对账工具**:静态猜 body 上游 status 不可靠(薄包装 status 来自 helper 的 `target_cn`/`area_name`、`round_by_op_result` 透传子 op status → 误报漏报);单测驱动版仍要约定断言写法 + 方法↔节点名映射 + 处理终态噪声,成本/可靠性比不好。advisory + code review 兜底足矣。
- **残余风险(诚实)**:无自动化持续保证,靠人/AI 写测试时对照 + review 二次兜;薄包装节点「数全分支」须查 helper 返回契约(动作一已述),否则对照失效。

### 示例:随便观(两动作走一遍)

| 节点 | 动作一:分支 | 动作二:返回 round_wait/until_*? | 写什么测试 |
|---|---|---|---|
| `check_initial_screen` | 2(显式:是入口 / 不在) | 否 | 2 单测 |
| `handle_auto_manage`/`yum_cha_sin`/`good_goods`/`boo_box`/`pawnshop` | 各 1(config 显式:'未开启…') | 否 | 各 1 单测 |
| `goto_suibian_temple` | ~5(wait(result.status)/success(current_screen)/success('开始托管')/wait('返回')/retry('未识别当前画面')) | **是**(ocr_and_click→手写 round_wait) | 5 单测 + 流程测试 |
| `goto_adventure`(子 op) | 薄包装(find_and_click_area + until_not_find_all) | **是** | 单测(until 连调 2 次)+ 流程测试 |
| `click_squad_team`(混合) | 3('跳过收获' + ocr 命中/未命中) | 否 | 3 单测 |
| `click_finish`/`click_claim`/`click_confirm`(纯薄包装) | 2(ocr 命中/未命中) | 否 | 各 2 单测 |
| `handle_adventure_squad`/`adventure_squad_2`/`craft`/`sales_stall`/`goto_category`/`back_at_last` | **纯委托**(0 自有分支) | — | 进子 op 测,不单列 |

结论:随便观该写 = 单测(app 层 config/入口/goto_suibian_temple 各分支 + 子 op 薄包装/混合节点分支)+ 流程测试(goto_suibian_temple / Transport / BackToNormalWorld / goto_adventure,要 FixtureController + 凑帧,**因实拍成本搁置**)。

## 4. 测什么:归属与判据(支撑 §3 的「为什么」)

| # | 测什么 | 归属 | 判据 | 载体 |
|---|---|---|---|---|
| 1 | 拓扑合法性 | 框架加载校验 | 不用 app 测 | 框架 |
| 2 | 单节点识别/决策(含薄包装 helper 契约分支) | 简单 mock 单测 | §3 动作一 | §5 |
| 3 | 流转/轮询/重试/恢复(返回 round_wait / until_*) | FixtureController | §3 动作二 | §6 |
| 4 | status 契约 | 单测断言(上游)+ 对照下游 `@node_from` | §3 动作一「对照下游」 | §3 |

判据原则:流转**不能全交给底层**(框架只管拓扑,不管 status 匹配与画面推进);**流程测试只给「返回 round_wait / until_*」的节点**,不是每个 app 端到端。

## 5. 怎么写:单节点测试

### 简单 / 单节点测试(常用)
mock 一帧 + 直接调 op 的节点方法 + 断言。范例:`test_suibian_temple_app.py::test_check_initial_screen_in_temple`:
```python
def test_xxx(test_context):
    test_context.mock_screen('打开游戏', 'ready')   # 设一帧
    op = SomeOp(test_context)
    op.screenshot()                                  # 取 mock 帧 → last_screenshot
    result = op.check_screen()                       # 直接调节点
    assert result.status == '打开游戏'
```
覆盖:识别 + 单节点决策/分支。

### 断言:看 node 返回类型(别照搬 is_success)

node 返回的 `OperationRoundResult` 类型决定 `is_success`,写断言前**先读 node 代码确认返回类型**:

| node 返回 | is_success | 断言用 |
|---|:---:|---|
| `round_success` / `round_by_find_area` 命中 / `round_by_ocr_and_click` 命中 | `True` | `assert result.is_success` |
| `round_wait`(点 area / click 后等下一轮) | `False` | `assert result.status == '<匹配词>'` |
| `round_retry`(未识别重试) | `False` | `assert not result.is_success` 或 `status` |

不同 app 同类 node 返回类型可能不同,**别照搬别的 app 的断言**。范例:`test_suibian_temple_app.py::test_goto_adventure`(round_wait 看 status)/ `test_goto_good_goods_in_menu`(命中看 is_success)。

### mock 哪帧:先读 node 逻辑 + status 名线索

测哪个 node、mock 哪帧,取决于**该 node 在哪帧检测什么**。读 node 代码确认 OCR/area 的检测目标画面 + 元素,别臆测:
- **status 名是线索**:如 `round_success(status='已在邻里街坊-进入好物铺')` 暗示检测的是**邻里街坊菜单**的「好物铺」选项(进好物铺前置),不是好物铺画面的标题 logo → mock 邻里街坊菜单。范例:`test_suibian_temple_app.py::test_goto_good_goods_in_menu`(好物铺画面标题 OCR 只识「铺」单字,app 靠菜单选项)。
- **OCR/area 检测目标**:node 的 `round_by_ocr('X')` / `round_by_find_and_click_area(screen, area)` 检测的是**哪种画面的什么元素** —— 决定 mock 哪帧。
- **失败别急着归因绕过**:测试失败先回 node 代码确认检测目标,别直接「OCR 不到 → 换图绕过」。⚠️ **注意 LCS 误匹配**:mock 帧里若含与 target 部分相似的文字(如入口「游历」tab vs target「游历小队」),LCS 会误命中——换个不含干扰文字的帧(范例:`test_click_squad_team_miss` 用「制造坊」而非「入口」)。

### 薄包装节点:mock 命中 / 不命中两帧

薄包装节点(`return self.round_by_X(...)`)按 helper 契约(§3 动作一)mock 两种帧:
- **命中**:mock 含 target/area 的帧 → `round_success(status=匹配词)`。范例:`test_suibian_temple_app.py::test_click_squad_team_hit` / `test_city_fund_app.py::test_click_task_claim`。
- **不命中**:mock 不含 target 的帧 → `round_retry('未匹配到目标文本')`。范例:`test_suibian_temple_app.py::test_click_squad_team_miss`。

混合节点(守卫 + 薄包装)额外测守卫分支。范例:`test_suibian_temple_app.py::test_click_squad_team_skip_claim`(claim=False→'跳过收获')。

### config 分支:monkeypatch 改 config(不写盘)

config 开关分支用 `monkeypatch.setattr(ConfigClass, '字段', 值)` 改 config(不写盘、自动还原、实例 99 隔离)。范例:`test_suibian_temple_app.py::test_handle_auto_manage_disabled` 等。⚠️ 这些 `'未开启'` / `'未开启自动托管'` status 串是下游 `@node_from` 的匹配词,断言它们 = 守 app 编排边契约。

### `until_find_all` / `until_not_find_all`:同一 op 实例连续调 2 次(多帧 mock)

`round_by_find_and_click_area(until_*=...)` 这类「click 后等画面变化」的 node,用 `last_screenshot` 验证 + `node_clicked` 标志,**需两轮**:
- 第 1 轮(`node_clicked=False`):mock click 前画面 → click → `round_wait`(status=area)。
- 第 2 轮(`node_clicked=True`):mock click 后画面 → `until` 验证 area 消失/出现 → `round_success`。

测试在同一 op 实例上**连续调 node 2 次**(不经 runner —— `_reset_status_for_new_node` 只在 runner 进新 node 时 reset `node_clicked`,手动连调保持标志)。范例:`test_suibian_temple_app.py::test_goto_adventure`:
```python
op = SomeOp(test_context)
test_context.mock_screen('随便观', '入口-手动态')   # 第 1 帧:click 前
op.screenshot()
r1 = op.goto_adventure()                            # click 按钮-游历 → round_wait
assert r1.status == '按钮-游历'
test_context.mock_screen('随便观', '游历')           # 第 2 帧:click 后
op.screenshot()
r2 = op.goto_adventure()                            # until 验证 → round_success
assert r2.is_success
```

## 6. 怎么写:流程测试(FixtureController)

**何时用**(§3 动作二):op 有**返回 `round_wait` 或用 `until_*`**的节点(流转/轮询/重试/恢复/多帧状态机),才需要跑完整 `execute()`。线性派发(每节点看一眼就返回)不用——动作一的单测够。

跑 op 的完整 `execute()`(多帧、轮询、重试、恢复性 click),用 `FixtureController`(`MockController` 子类,"会反应的假游戏")。详见 [fixture_controller.md](fixture_controller.md)。范例:`test_enter_game_flow.py`(EnterGame 自动登录全流程)。

覆盖:op 的**流程逻辑**(节点图边、轮询、恢复分支)——单节点测试覆盖不到的部分。

## 7. 提交坑(重要)

测试文件在 `zzz-od-test` 独立仓。主仓 `git add zzz-od-test/...` 会被 `.gitignore` **静默跳过**(不报错但未加入)。必须在测试仓内提交(always-on 提示见 [AGENTS.md](../../../AGENTS.md)「提交流程与协作边界」):
```shell
git -C zzz-od-test add test/... && git -C zzz-od-test commit -m "..."
```

## 8. 代码规范 / fixture 格式

### 代码规范(项目特有,过自检筛)

- **文件路径**:测试文件放在被测文件的包路径 + 被测文件名的文件夹下(如被测 `one_dragon/base/operation/one_dragon_context.py` → `zzz-od-test/test/one_dragon/base/operation/one_dragon_context/`)。
- **单方法文件**:每个测试文件专门测试单个方法的各种场景。
- **fixture scope**:用 `pytest.fixture` 管理依赖;注意指定 `scope`(如 session 级 `test_context` 只 init 一次)。
- **导入**:不用 `src`(`from one_dragon.base.operation import Operation` ✓;`from src.one_dragon...` ✗)。
- **异步超时**:异步测试方法必须加超时(如 `@pytest.mark.timeout(3)`),防止无限挂起。

### 测试 fixture 图:尽量 webp q90

测试 fixture 的整屏截图**默认转 webp q90**(省 ~90%,整屏识别无损效)。原则:**满足测试为准**——转后跑测试,过的留 webp;实测不过的保留 PNG。

- **能压**:整屏画面匹配 / 事件识别(容差大)。
- **保留 PNG**:精度敏感(小地图角度)、含细文字 OCR(webp q90 致 OCR 空)、**模板裁剪源**(webp lossy → 裁剪放大 artifacts → 模板 conf 降)。
- **转换**:`cv2.imencode('.webp', img, [cv2.IMWRITE_WEBP_QUALITY, 90])` + `ndarray.tofile(path)`(中文路径安全,非 `cv2.imwrite`);批量见 [onboard skill 的 `convert_to_webp.py`](../../../.claude/skills/zzz-od-dev-screen-onboarding/convert_to_webp.py)。原 PNG 保留,确认无引用且测试过后手动删。
- **改引用**:转后同步改测试代码 `.png`→`.webp`(保留 PNG 的不改)。
