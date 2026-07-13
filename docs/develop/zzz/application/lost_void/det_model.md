# 迷失之地检测模型

迷失之地玩法用于识别地图上各类交互入口(感叹号 / 距离 / 战斗 / 挑战 / 商店等)的 YOLO 目标检测模型。本文记录模型在主仓的**来源、消费链路与发布规范**;训练与精度评估的详细流程在训练仓 [OneDragon-YOLO](https://github.com/OneDragon-Anything/OneDragon-YOLO)(文档待补)。

## 1. 模型概述

| 项 | 值 |
|---|---|
| 默认模型 | `yolov26n-736-lost-void-det-20260630` |
| 备份模型 | `yolov8n-736-lost-void-det-20250921` |
| onnx 输入 | 736×736(正方形) |
| onnx 输出 | YOLOv8 风格 `[1, 4+nc, anchors]`,nc=16 |
| 类别 | 16 类:`0000-感叹号` … `0014-挑战-收割`、`0015-迷雾` |

类别定义见模型目录下 `labels.csv`,配置项 `ModelConfig.lost_void_det`。

## 2. 模型来源

- **训练仓**:[OneDragon-YOLO](https://github.com/OneDragon-Anything/OneDragon-YOLO),代码在 `src/one_dragon_yolo/zzz/lost_void_det/`(训练脚本 `lost_void_det_03_train.py`)。训练流程文档**待补充**。
- **数据集**:`ZZZ-LostVoidDet-Dataset`(ModelScope: `DoctorReid/ZZZ-LostVoidDet-Dataset`)。原图 1920×1080,训练时两两上下拼接成 2208×2208 正方形后喂模型。
- **发布**:`OneDragon-Anything/OneDragon-YOLO` 的 release tag `zzz_model`,资产 `<模型名>.zip`。

## 3. 主仓消费链路

配置 → 业务检测器 → 框架加载:

1. **配置**:`src/zzz_od/config/model_config.py` 的 `_DEFAULT_LOST_VOID_DET` / `_BACKUP_LOST_VOID_DET`。新模型无法下载时回退 backup。
2. **业务封装**:`LostVoidDetector`(`src/zzz_od/application/hollow_zero/lost_void/context/lost_void_detector.py`),继承 `Yolov8Detector`,提供"感叹号 / 距离 / 入口"等业务判断。`run()` 在推理前会把战斗画面 `头像-3-1/3-2/3-3` 区域涂黑,避免角色头像被误检为目标。
3. **框架加载与推理**:`Yolov8Detector`(`src/one_dragon/yolo/yolov8_onnx_det.py`):
   - 预处理 `onnx_utils.scale_input_image_u`:等比缩放、左上对齐的 letterbox,对 736×736 正方形自洽。
   - 后处理 `process_output`:`np.squeeze(output[0]).T` + 动态切片,不硬编码类别数,16 类开箱兼容。
   - **标签加载** `_load_detect_classes`:**只读 `labels.csv`**(`idx,label`);框架全线(`yolo_config_utils.is_model_existed` 等)都不认 `model_label.txt`。
4. **本地目录**:`assets/models/lost_void_det/<模型名>/`(gitignore),必须含 `labels.csv` + `model.onnx`。

## 4. 模型获取与发布规范

**下载与解压**:`OnnxModelLoader`(`src/one_dragon/yolo/onnx_model_loader.py`)从 `zzz_model` release 下载 `<模型名>.zip`,`extractall` 到 `assets/models/lost_void_det/<模型名>/`。

**zip 结构(发布规范)**:

```
<模型名>.zip
├── labels.csv      # idx,label 表头;框架只认这个,不认 model_label.txt
└── model.onnx
```

两个踩坑点:

- **必须平铺在 zip 根、无子目录**。`unzip_model` 用 `extractall` 到 `<模型名>/`,zip 内若再带一层 `<模型名>/`,实际路径变成 `<模型名>/<模型名>/model.onnx`,框架找不到。
- **标签必须是 `labels.csv`**(`idx,label` 表头)。训练侧导出的标签文件格式各异,框架只认 `labels.csv`,其它格式需转换。

**升级模型 checklist**:

1. 训练仓导出 `model.onnx`;把训练侧的标签文件转成 `labels.csv`(首行 `idx,label`,逐行 `<序号>,<类别名>`)。
2. 平铺打包 `<新模型名>.zip`(仅 `labels.csv` + `model.onnx`)。
3. 上传 release:`gh release upload zzz_model <新模型名>.zip -R OneDragon-Anything/OneDragon-YOLO --clobber`。
4. 主仓改 `src/zzz_od/config/model_config.py`:`_DEFAULT_LOST_VOID_DET` = 新模型名,旧默认降为 `_BACKUP_LOST_VOID_DET`。
5. 若新增类别,检查 `LostVoidDetector` 业务逻辑是否需要适配。

**发布顺序**:先上传 release,再合并改 `model_config` 的 PR。否则用户更新代码后下载不到新模型,会回退 backup。
