## 目标

`ScreenArea` 使用显式类型描述框架如何处理区域，保存时按类型输出对应字段，不再根据字段是否为空或是否等于当前默认值猜测哪些数据有用。

区域类型固定为：

| 类型 | 含义 | 类型字段 |
| --- | --- | --- |
| `none` | 没有框架内置识别方式，可用于点击、拖动、裁剪或自定义处理 | 无 |
| `text` | 文本区域，可作为固定文本匹配目标或动态 OCR 搜索范围 | `text`、`lcs_percent`、`color_range` |
| `template` | 模板匹配区域 | `template_sub_dir`、`template_id`、`template_match_threshold` |

公共字段包括：

- `area_name`
- `area_type`
- `pc_rect`
- `id_mark`
- `goto_list`
- `gamepad_key`

`color_range` 只表示文本识别前的颜色过滤，不提供独立的颜色区域识别。

## 类型与可匹配能力

区域属于某个类型，不代表它一定能自行匹配。代码使用 `can_match` 单独判断：

- `text`：`text` 非空时可自行匹配。
- `template`：`template_id` 非空时可自行匹配。
- `none`：不能自行匹配。

动态文本区域仍然是 `text`，但可以没有固定 `text`。这类区域用于限定 OCR 搜索范围或提供 OCR 颜色过滤，不能作为有效的 `id_mark`，也不会被画面匹配当成命中项。

## YAML 示例

### 无内置识别

```yaml
- area_name: 按钮-退出
  area_type: none
  pc_rect: [1730, 206, 1794, 266]
```

### 固定文本

```yaml
- area_name: 标题
  area_type: text
  id_mark: true
  pc_rect: [100, 100, 300, 150]
  text: 快捷手册
  lcs_percent: 0.5
  color_range:
  - [230, 230, 230]
  - [255, 255, 255]
```

### 动态文本范围

```yaml
- area_name: 列表范围
  area_type: text
  pc_rect: [1220, 35, 1770, 110]
  lcs_percent: 0.5
```

### 模板

```yaml
- area_name: 返回
  area_type: template
  id_mark: true
  pc_rect: [20, 20, 80, 80]
  template_sub_dir: menu
  template_id: back
  template_match_threshold: 0.7
```

## 旧配置读取规则

缺少 `area_type` 时按已有识别字段推断：

1. `text` 非空：`text`。
2. `template_id` 非空：`template`。
3. 其它情况：`none`。

旧名称 `click` 和 `ocr` 仅在读取时分别兼容为 `none` 和 `text`，保存时统一写新名称。

没有固定文本的旧区域无法仅靠数据判断它是动态 OCR 范围还是普通裁剪范围。确实需要动态 OCR 参数的区域，应在配置中显式写 `area_type: text`。

## 保存规则

`ScreenArea.to_dict()` 始终写出：

- `area_name`
- `area_type`
- `pc_rect`

按需写出公共字段：

- `id_mark`：仅为 `true` 时写出。运行时只把 `can_match` 为 `true` 的标识区域纳入精准匹配。
- `goto_list`：仅非空时写出。
- `gamepad_key`：仅非空时写出。

按类型写出识别字段：

- `none`：不写识别字段。
- `text`：`text` 非空时写出；始终写 `lcs_percent`；`color_range` 非空时写出。
- `template`：`template_sub_dir`、`template_id` 非空时写出；始终写 `template_match_threshold`。

数值参数即使等于当前默认值也必须保存，例如 `lcs_percent: 0.5` 和 `template_match_threshold: 0.7`。这些值是当前区域的有效配置，不能因为碰巧等于代码默认值就省略，否则配置行为会依赖未来默认值。

保存时会裁剪其它类型的字段。切换类型后，界面内存可以暂时保留旧字段，最终 YAML 只保留当前类型的数据。

## 匹配行为

- `find_area_in_screen`、`find_area_in_screen_binary` 和 `find_area_with_detail` 只处理具备完整匹配条件的 `text`、`template`。
- `find_and_click_area` 对可匹配的 `text`、`template` 先匹配再点击；配置不完整时不点击。`none` 保持直接点击区域中心的定位语义。
- `find_screen_matches` 只把 `id_mark` 且 `can_match` 的区域纳入精准匹配条件。
- `none` 和配置不完整的区域不会被当成匹配成功。

## 画面管理与后端

画面管理表格只展示公共字段，类型参数在独立编辑区显示：

- `text`：目标文本、文本阈值、OCR 颜色范围。
- `template`：模板目录、模板 ID、模板阈值。
- `none`：不显示识别参数。

后端和 MCP 的 `upsert_screen_area` 支持 `area_type`。为了兼容旧调用，`area_type=None` 时使用旧配置推断规则。

## 验证重点

- 三种类型和旧名称兼容读取正确。
- 动态文本区域不参与普通画面匹配和查找点击。
- 当前类型的默认数值参数仍被写出。
- `none` 不写文本、模板或颜色过滤参数。
- 显式 `null` 的文本和模板阈值回退到兼容默认值。
- 保存再加载不会丢失当前类型的有效字段。
