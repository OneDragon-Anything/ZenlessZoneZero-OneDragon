# 画面区域配置精简与类型化改造

## 背景

当前 `screen_info/*.yml` 中每个区域都会写出 OCR、模板、颜色识别相关字段，即使这些字段为空或只是默认值。例如纯点击区域也会包含 `text: ''`、`template_id: ''`、`color_range: null` 等字段。

这种全字段展开格式有两个问题：

1. YAML 可读性差，人为维护时需要跳过大量空字段。
2. 画面管理表格需要并排展示三类区域字段，横向空间占用过大。

本改造目标是引入显式区域类型，并让保存格式只写必要字段，降低配置噪音，同时保持旧配置兼容。

## 目标

1. 为区域增加 `area_type` 字段，明确当前区域的识别或交互类型。
2. 旧 YAML 不要求一次性迁移；缺少 `area_type` 时按现有字段自动推断。
3. 保存 YAML 时只写公共字段、当前类型需要的字段，以及非默认字段。
4. 画面管理界面按 `area_type` 展示类型相关参数，避免三类字段并排堆在表格中。
5. 不改变现有 `round_by_find_area`、`round_by_find_and_click_area` 等调用方语义。

## 区域类型

建议初始支持四种类型：

| 类型 | 含义 | 主要字段 |
| --- | --- | --- |
| `click` | 纯点击区域，不参与识别 | `pc_rect` |
| `ocr` | OCR 文本区域 | `text`、`lcs_percent`、`color_range` |
| `template` | 模板匹配区域 | `template_sub_dir`、`template_id`、`template_match_threshold` |
| `color` | 纯颜色区域 | `color_range`、`color_match_threshold` |

默认类型建议为 `click`。

## YAML 示例

### 纯点击区域

```yaml
- area_name: 按钮-退出
  area_type: click
  pc_rect: [1730, 206, 1794, 266]
  goto_list: []
```

### OCR 区域

```yaml
- area_name: 标题
  area_type: ocr
  pc_rect: [100, 100, 300, 150]
  text: 快捷手册
  lcs_percent: 0.8
  color_range:
  - [230, 230, 230]
  - [255, 255, 255]
```

### 模板区域

```yaml
- area_name: 返回
  area_type: template
  pc_rect: [20, 20, 80, 80]
  template_sub_dir: menu
  template_id: back
  template_match_threshold: 0.75
```

### 颜色区域

```yaml
- area_name: 活跃度已满
  area_type: color
  pc_rect: [1330, 255, 1362, 282]
  color_range:
  - [0, 120, 0]
  - [80, 240, 60]
  color_match_threshold: 0.1
```

## 读取兼容策略

`ScreenArea` 读取时按以下顺序确定类型：

1. 如果 YAML 中存在 `area_type`，优先使用该字段。
2. 如果不存在 `area_type`，按旧字段推断：
   - `text` 非空：`ocr`
   - `template_id` 非空：`template`
   - `color_range` 非空且有上下限：`color`
   - 其它情况：`click`

旧字段默认值继续保留，避免影响已有调用和历史配置。

## 保存精简策略

`ScreenArea.to_dict()` 建议只写出以下内容：

公共字段：

- `area_name`
- `area_type`
- `id_mark`，仅为 `true` 时写出
- `pc_rect`
- `goto_list`，仅非空时写出
- `gamepad_key`，仅非空时写出

类型字段：

- `ocr`：写 `text`；`lcs_percent != 0.5` 时写 `lcs_percent`；`color_range` 非空时写 `color_range`
- `template`：写 `template_sub_dir`、`template_id`；`template_match_threshold != 0.7` 时写 `template_match_threshold`
- `color`：写 `color_range`；`color_match_threshold != 0.1` 时写 `color_match_threshold`
- `click`：不写 OCR、模板、颜色字段

为了减少一次性 diff，首次实现可先只对画面管理保存行为生效，不强制批量重写全部 YAML。

## 识别逻辑调整

`ScreenArea` 判断属性建议改为显式类型优先：

```python
is_text_area -> area_type == 'ocr'
is_template_area -> area_type == 'template'
is_color_area -> area_type == 'color'
```

缺少 `area_type` 的老配置在初始化时完成推断，因此识别逻辑不需要到处写兼容分支。

`find_area_in_screen_binary` 不处理 `color` 类型。二值化识别仅用于 OCR 和模板匹配，颜色区域继续走普通 `find_area_in_screen`。

## 前端改造建议

画面管理表格建议只保留高频公共字段：

- 操作
- 标识
- 类型
- 区域名称
- 位置
- 前往画面
- 手柄键

类型参数不要继续横向铺开，改为在表格下方或右侧展示“区域参数”编辑区：

- `ocr`：OCR 文本、OCR 阈值、颜色范围
- `template`：模板目录、模板 ID、模板阈值
- `color`：颜色范围、颜色阈值
- `click`：不显示类型参数

切换类型时，界面只展示当前类型的参数。内存中可以暂时保留其它类型字段，方便误切后切回；最终保存时只写当前 `area_type` 需要的字段，其它类型字段会被丢弃。

## 实施步骤

1. 在 `ScreenArea` 中新增 `area_type` 字段和推断逻辑。
2. 调整 `is_text_area`、`is_template_area`、`is_color_area` 使用 `area_type`。
3. 调整 `to_dict()`，实现按类型精简写出。
4. 调整 `ScreenInfo` 读取 `area_type`。
5. 改造画面管理表格，新增“类型”列，移除横向 OCR/模板/颜色参数列。
6. 增加类型参数编辑区，并在切换类型时同步清理无关字段。
7. 选取少量典型 YAML 手动保存验证格式：
   - 纯点击区域
   - OCR 区域
   - 模板区域
   - 颜色区域
8. 运行改动文件的 `ruff check`，并用画面管理界面保存一次确认不丢字段。

## 验证清单

- 老 YAML 未配置 `area_type` 时可正常加载。
- `round_by_find_area` 对 OCR、模板、颜色区域行为不变。
- `round_by_find_and_click_area` 对纯点击区域仍点击中心点。
- `find_area_in_screen_binary` 不会对颜色区域做 RGB 判断。
- 画面管理保存后，空字段和默认字段不会重新膨胀。
- `_od_merged.yml` 重新生成后能被默认加载路径读取。

## 风险与边界

- 如果保存逻辑一次性精简全部 YAML，会产生较大 diff。建议先通过画面管理对变更文件逐步保存，或者单独做一次格式迁移提交。
- 旧代码若直接根据 `text`、`template_id` 判断区域类型，应改用 `is_text_area`、`is_template_area`、`is_color_area`。
- `color_match_threshold` 只对 `color` 类型有意义，不应影响 OCR 的 `color_range` 过滤。
