# 迷失之地深度避障

寻路时用单目深度模型（Depth Anything V2 Small）估计每个方向「脚下能走多远」，目标方向近处被挡时提前偏开，脱困时往更空的一侧绕。代码在 `context/lost_void_depth_estimator.py`，接入在 `LostVoidMoveByDet`。

## 怎么开启

- 挑战配置字段 `depth_avoid`（默认关闭，界面上没有开关），需要同时开启 `smart_escape`（见 [无脑挂机刷菲林](afk_polychrome.md)）。预设「无脑挂机刷菲林」两项都已打开。
- 在资源管理页下载「迷失之地深度避障」模型（`config/repository.yml` 的 `lost_void_depth`，放在 `assets/models/lost_void_depth/depth-anything-v2-small/model.onnx`）。
- 只用 GPU（CUDA / DirectML）推理。没有 GPU、没有下载模型时自动关闭，日志写明原因，不回退 CPU（每帧都要推理，CPU 跑不动）。

## 原理

- 平地上模型输出的逆深度 d 随画面行 y 线性变化，越往上越远；墙、栏杆、箱子这类立着的东西，往上看 d 不再变小，竖直变化率明显小于地面。
- 用角色两侧画面下方的地面拟合 `d = a*y + b` 得到地面变化率（`fit_ground_slope`）；拟合结果不是正数说明画面被遮挡（如技能特效铺满），这一帧不判断。
- 把画面 x 160～1760 分成 16 列，每列从下往上扫（`scan_columns`），竖直变化率连续 6 行低于地面的 0.35 倍就算立着的东西，返回它所在的行，行越大越近。角色所在的列从头顶开始扫（看不到脚下），右下技能按钮那片从按钮上方开始扫。
- 两次推理间隔至少 0.3 秒，期间复用上次结果。推理通过 `OnnxModelLoader.run_session` 走 `gpu_executor`。

## 移动中避障

`LostVoidMoveByDet._get_avoid_aim_x`：目标所在的列近处（障碍行 ≥ 600）挡路时，在目标左右 6 列内挑代价最小的不挡路列作为瞄准点，代价 = 障碍行 + 偏离目标的列数 × 15（`choose_aim_column`）。上次选的列还不挡路、代价和最优列相差不超过 30 时继续用它，避免来回摆。目标图标已经很大（宽高都超过 50，说明很近）时不避障。避障偏转时每次最多转 40。

## 脱困选方向

`_get_escape_side`：本次寻路第一次脱困时，比较角色左右两侧各列障碍的平均行（`pick_escape_side_by_depth`），相差 ≥ 20 行就往更空的一侧绕；分不出来时按目标图标所在的一侧绕。例子：第一层第一间右边入口前的路障，图标偏右，但右侧是路障和铁皮墙之间的窄死角，左侧才是通路。

## 模型

- 来源：Depth Anything V2 Small（Apache-2.0），导出为 ONNX，输入 518×294。
- 发布：按其他模型的方式打包成 `depth-anything-v2-small.zip`（内含 `model.onnx`），发布到 OneDragon-YOLO 的 `zzz_model` release。

## 还没在本仓实机验证的地方

来自 zzz-lost-void（从本仓拆分出的迷失之地项目），在那边实机跑过；移植到本仓后还没实机验证，模型下载也要等发布后才能验证。阈值（障碍行 600、代价系数 15、两侧差 20 行）按那边的实测定的。
