# OCR 生命周期

绝区零侧不直接修改 `one_dragon` 基础 OCR 框架，而是在 `ZContext` 中替换为业务侧封装：

- `ManagedOnnxOcrMatcher` 位于 `src/zzz_od/context/managed_ocr_matcher.py`
- GUI 初始化阶段只配置 OCR 的 GPU 与代理参数，不创建 ONNX Runtime 会话
- 首次实际 OCR 调用时懒加载模型
- OCR 模型超过 30 分钟未使用时由后台线程自动释放
- 模型加载、OCR 推理、空闲释放共用生命周期锁，避免加载和释放并发冲突

调用侧继续使用 `ctx.ocr` 与 `ctx.ocr_service`，不需要感知生命周期管理细节。
