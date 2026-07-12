---
name: zzz-od-dev-cv-method
description: 绝区零一条龙新增 CV 流水线步骤与目标状态解读方式指南
version: 1.0.0
author: OneDragon-Anything
tags: [zzz, one-dragon, cv, image-analysis, development]
---

# 新增 CV 方法指南

本项目有两层容易混淆：

| 需求 | 修改位置 | 说明 |
|---|---|---|
| 新增图像处理步骤 | `src/one_dragon/base/cv_process/steps/` + `CvService.available_steps` | 例如颜色过滤、形态学、轮廓过滤、模板匹配 |
| 新增状态解读方式 | `src/zzz_od/game_data/target_state.py` + `TargetStateChecker` | 例如把轮廓宽度转成百分比、OCR 文本转数值 |

如果只是搭一条新识别流程，优先用现有步骤在图像分析工具里配置 `assets/image_analysis_pipelines/*.yml`，不要先写代码。

## 1. CV 流水线基本结构

核心类：

- `CvStep`：原子步骤基类
- `CvPipeline`：按顺序执行步骤
- `CvPipelineContext`：步骤之间传递数据
- `CvService`：加载、保存、运行 pipeline，并维护可用步骤注册表

关键文件：

```text
src/one_dragon/base/cv_process/
├── cv_step.py
├── cv_pipeline.py
├── cv_service.py
└── steps/
    ├── __init__.py
    ├── step_filter_by_rgb.py
    ├── step_find_contours.py
    └── ...
```

流水线配置保存到：

```text
assets/image_analysis_pipelines/<pipeline_name>.yml
```

业务调用方式：

```python
cv_result = self.ctx.cv_service.run_pipeline(
    'pipeline_name',
    screen,
    debug_mode=False,
    timeout=1.0,
)
```

## 2. `CvPipelineContext` 常用字段

| 字段 | 用途 |
|---|---|
| `source_image` | 原始输入图像，只读 |
| `display_image` | 当前步骤处理/显示用图像，可修改 |
| `mask_image` | 二值掩码，供轮廓步骤或后续解读使用 |
| `contours` | 当前轮廓列表 |
| `match_result` | 模板匹配结果 |
| `ocr_result` | OCR 结果 |
| `crop_offset` | 当前裁剪图相对原图的左上角偏移 |
| `analysis_results` | 分析输出文本 |
| `error_str` / `success` | 流水线成败状态 |

坐标类结果要考虑 `crop_offset`。如果轮廓来自裁剪后的图，输出绝对坐标时使用 `context.get_absolute_rects()` 或手动加偏移。

## 3. 新增 `CvStep`

### 3.1 新增步骤文件

在 `src/one_dragon/base/cv_process/steps/` 下新增 `step_extract_red_channel.py`：

```python
import numpy as np

from one_dragon.base.cv_process.cv_step import CvPipelineContext, CvStep


class CvStepExtractRedChannel(CvStep):

    def __init__(self):
        CvStep.__init__(self, '提取红色通道')

    def get_params(self) -> dict:
        return {}

    def _execute(self, context: CvPipelineContext, **kwargs) -> None:
        red_channel = context.display_image[:, :, 0]
        height, width = red_channel.shape
        new_image = np.zeros((height, width, 3), dtype=np.uint8)
        new_image[:, :, 0] = red_channel
        context.display_image = new_image
        context.analysis_results.append('已提取红色通道')
```

项目约定传入流水线的是 RGB 图像，红色通道是索引 `0`。通过 `cv2.imread` 读取离线图片时，需要先 `cv2.cvtColor(img, cv2.COLOR_BGR2RGB)`。

### 3.2 暴露参数

`get_params()` 返回 UI 可配置参数定义。示例：

```python
def get_params(self) -> dict:
    return {
        'threshold': {
            'type': 'int',
            'default': 127,
            'label': '阈值',
            'tooltip': '保留大于该值的像素',
        },
        'draw_result': {
            'type': 'bool',
            'default': True,
            'label': '绘制结果',
        },
    }

def _execute(
    self,
    context: CvPipelineContext,
    threshold: int = 127,
    draw_result: bool = True,
    **kwargs,
) -> None:
    ...
```

已有参数类型可参考：

- `step_threshold.py`
- `step_filter_by_rgb.py`
- `step_find_contours.py`
- `step_template_matching.py`
- `step_ocr.py`

### 3.3 导出步骤类

修改 `src/one_dragon/base/cv_process/steps/__init__.py`：

```python
from .step_extract_red_channel import CvStepExtractRedChannel
```

### 3.4 注册到 `CvService`

修改 `src/one_dragon/base/cv_process/cv_service.py`：

```python
from one_dragon.base.cv_process.steps import (
    CvStepExtractRedChannel,
    ...
)

self.available_steps: Dict[str, Type[CvStep]] = {
    '提取红色通道': CvStepExtractRedChannel,
    ...
}
```

注册名要与 `CvStep.__init__` 里的名字一致，否则保存/加载 pipeline 时会找不到步骤。

## 4. 调试与集成流程

1. 启动 GUI。
2. 打开图像分析工具。
3. 载入目标截图。
4. 添加新步骤，调整参数。
5. 保存为 `assets/image_analysis_pipelines/<pipeline_name>.yml`。
6. 在业务代码中调用 `ctx.cv_service.run_pipeline('<pipeline_name>', image)`。
7. 用 `cv_result.is_success`、`cv_result.contours`、`cv_result.ocr_result` 等字段做业务判断。

自动战斗目标状态通常通过 `DetectionTask` 调度，不要在高频战斗循环里临时创建复杂 CV 对象。

## 5. 新增目标状态解读方式

当现有 pipeline 已经能输出轮廓、OCR 或模板结果，但缺少“怎么把结果变成状态”的规则时，新增 `TargetCheckWay`。

### 5.1 增加枚举

文件：`src/zzz_od/game_data/target_state.py`

```python
class TargetCheckWay(Enum):
    MY_NEW_CHECK = 'my_new_check'
```

### 5.2 在 `TargetStateChecker` 注册处理器

文件：`src/zzz_od/auto_battle/target_state/target_state_checker.py`

```python
self._check_way_handlers = {
    TargetCheckWay.MY_NEW_CHECK: self._check_my_new_check,
    ...
}
```

### 5.3 实现处理函数

```python
def _check_my_new_check(
    self,
    cv_result: CvPipelineContext,
    state_def: TargetStateDef,
    _start_time: float,
) -> tuple | bool | None:
    if cv_result.check_timeout():
        return None

    params = state_def.check_params
    # 命中且无数值：return True
    # 命中且有数值：return True, value
    # 未命中但要清状态：return None if state_def.clear_on_miss else False
```

返回约定：

| 返回值 | 含义 |
|---|---|
| `True` | 状态命中 |
| `(True, value)` | 状态命中，并记录数值 |
| `False` | 状态未命中 |
| `None` | 不更新状态，常用于超时或 `clear_on_miss=True` 的未命中 |

### 5.4 在 `DETECTION_TASKS` 中使用

```python
DetectionTask(
    task_id='my_task',
    pipeline_name='my_pipeline',
    interval=0,
    is_async=True,
    state_definitions=[
        TargetStateDef(
            '目标-我的状态',
            TargetCheckWay.MY_NEW_CHECK,
            {'min_count': 1},
            clear_on_miss=True,
        ),
    ],
)
```

## 6. 编写注意事项

- 统一按 RGB 图像处理，只有调用 OpenCV 特定 API 时再显式转换。
- 新步骤优先修改 `display_image`、`mask_image`、`contours` 这些标准字段，不要私自挂临时属性。
- 裁剪步骤必须维护 `crop_offset`，否则后续坐标会偏。
- 高频流程要注意 `timeout` 和性能，自动战斗里默认按 1 秒软超时处理。
- ONNX / GPU session 不要并发直调多个 session，需要走项目既有执行器机制。
- 能用现有 `CvStep` 组合解决时，不新增代码。

## 7. 验证清单

- [ ] 新 step 文件位于 `src/one_dragon/base/cv_process/steps/`。
- [ ] `steps/__init__.py` 已导出新类。
- [ ] `CvService.available_steps` 已注册，注册名与 step 名一致。
- [ ] 图像分析工具能看到新步骤。
- [ ] 保存后的 pipeline YAML 能被 `CvService.load_pipeline()` 重新加载。
- [ ] 如果新增 `TargetCheckWay`，`TargetStateChecker._check_way_handlers` 已注册。
- [ ] 对改动文件运行 `uv run --env-file .env ruff check <file>`。