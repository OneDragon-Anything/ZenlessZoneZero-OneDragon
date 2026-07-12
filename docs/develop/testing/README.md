# 测试方法论

> `docs/develop/testing/` 的入口。测试代码在独立仓 `zzz-od-test`(主仓 `.gitignore` 忽略它,clone 到主仓根目录用)。本目录记录**怎么跑测试 + 测试基建 + 怎么写 op 测试**。

## 1. 测试在哪 / 怎么跑

- 测试代码在独立仓 [zzz-od-test](https://github.com/OneDragon-Anything/zzz-od-test);clone 到主仓根目录,IDE 里把 `zzz-od-test/` 设为 `Test Sources Root`。
- 主仓不保留测试(`tests/` 已废弃);新测试加到 `zzz-od-test/test/` 对应被测包路径下。
- 环境变量:把 `zzz-od-test/.env.sample` 复制到主仓根 → `.env`(部分测试需要;本地若只跑自己改的部分,可不配全)。
- 跑测试:
  ```shell
  uv run --env-file .env pytest zzz-od-test/
  ```

## 2. 测试基建(`zzz-od-test/test/conftest.py`)

- **`test_context` fixture**(session 级):跑 `ctx.init()` → 真 OCR + 真 screen_info;注入 `MockController`。所有要识别能力的测试都用它(只 init 一次,session 复用)。
- **mock 下一帧**:
  - `test_context.add_mock_screenshot(img)` —— 设任意图为 controller 下一帧。
  - `test_context.mock_screen(screen_name, state)` —— 从存档 `screens/<screen>/<state>.webp` 读一帧并设上(存档见 [截图存档](../zzz/screenshot_archive.md))。
- **`MockController`**:`screenshot()` 返 mock 帧;`click()` 返 in-bounds bool(不真点)。

## 3. 怎么写测试

### 简单 / 单节点测试(常用)
mock 一帧 + 直接调 op 的节点方法 + 断言。这是现有惯例(如 `test_ridu_weekly_app`、`test_hollow_battle`):
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
| `round_wait`(点 area / click 后等下一轮识别) | `False` | `assert result.status == '<匹配词>'` |
| `round_retry`(未识别重试) | `False` | `assert not result.is_success` 或 `status` |

不同 app 同类 node 返回类型可能不同(如某些 app 领取 node 命中返 `round_success`、另一些点 area 后返 `round_wait` 等下一轮),**别照搬别的 app 的断言**。

### 多帧流程测试(FixtureController)
跑 op 的完整 `execute()`(多帧、轮询、重试、恢复性 click),用 `FixtureController`(MockController 子类,"会反应的假游戏")。详见 [fixture_controller.md](fixture_controller.md)。
覆盖:op 的**流程逻辑**(节点图边、轮询、恢复分支)——单节点测试覆盖不到的部分。

## 4. 提交坑(重要)
测试文件在 `zzz-od-test` 独立仓。主仓 `git add zzz-od-test/...` 会被 `.gitignore` **静默跳过**。必须在测试仓内提交:
```shell
git -C zzz-od-test add test/... && git -C zzz-od-test commit -m "..."
```

## 5. 测试代码规范

- **文件路径**:测试文件放在被测文件的包路径 + 被测文件名的文件夹下。
  - 示例:被测 `one_dragon.base.operation.one_dragon_context.py` → `zzz-od-test/test/one_dragon/base/operation/one_dragon_context/`。
- **单方法文件**:每个测试文件专门测试单个方法的各种场景(如 `test_method_a.py` 测 `method_a`)。
- **测试类**:用 `Test` 前缀的类组织测试方法。
- **fixture**:用 `pytest.fixture` 管理依赖;注意指定 `scope`(如 session 级 `test_context` 只 init 一次)。
- **导入**:不用 `src`(`from one_dragon.base.operation import Operation` ✓;`from src.one_dragon...` ✗)。
- **异步超时**:异步测试方法必须加超时(如 `@pytest.mark.timeout(3)`),防止无限挂起。

## 6. 测试 fixture 图:尽量 webp q90

测试 fixture 的整屏截图**默认转 webp q90**(省 ~90%,整屏识别无损)。原则:**满足测试为准**——转后跑测试,过的留 webp;实测不过的保留 PNG。

- **能压**:整屏画面匹配 / 事件识别(`test_get_match_screen_name`、hollow_zero 事件等,容差大)。
- **保留 PNG**:精度敏感(小地图角度,如 `test_cal_angle` 文件名=期望角度)、含细文字 OCR(webp q90 致 OCR 空,如 `ridu_weekly_app/100`)。
- **转换**:`cv2.imencode('.webp', img, [cv2.IMWRITE_WEBP_QUALITY, 90])` + `ndarray.tofile(path)`(中文路径安全,非 `cv2.imwrite`);批量见 [onboard skill 的 `convert_to_webp.py`](../../../skills/zzz-od-dev-screen-onboarding/convert_to_webp.py)。原 PNG 保留,确认无引用且测试过后手动删。
- **改引用**:转后同步改测试代码 `.png`→`.webp`(保留 PNG 的不改)。
