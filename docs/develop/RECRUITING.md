# 绝区零一条龙 — 开源贡献者招募

## 我们是谁

**[绝区零一条龙](https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon)** 是绝区零社区最大的开源自动化工具，涵盖自动战斗、闪避辅助、日常一条龙、空洞零号、多账号管理等核心功能。项目在 GitHub 上拥有 **6k+ Star**，60+ 位贡献者参与，持续迭代。

## 你能接触到什么技术

这不是一个简单的脚本项目。你会接触到完整的产品级技术栈：

- **桌面应用开发**：PySide6 + pyside6-fluent-widgets（Fluent Design 风格），46+ 自定义组件
- **机器学习部署**：ONNX Runtime + DirectML GPU 推理、YOLO 目标检测、音频特征分析
- **OCR 引擎**：自研 onnxocr（PaddleOCR 移植），端到端优化
- **游戏自动化**：屏幕截图、键鼠/手柄模拟、多线程架构、OpenCV 模板匹配
- **工程化实践**：uv 包管理、PyInstaller 打包（集成运行时）、多仓库协作、遥测系统
- **架构设计**：插件化应用系统、条件操作框架、异步任务调度

## 社区贡献者的真实成长

以下是本项目中真实发生的成长故事。

### 从更新文档到全栈核心贡献者

> 2025 年 9 月，一位贡献者的第一个 PR 只是更新 README 和兑换码。但社区给了方向，项目给了场景——他很快开始独立负责锄大地路线开发，随后扩展到迷失之地、恶名狩猎、体力计划等几乎所有游戏功能模块。7 个月内提交了 **58 个 commit**，成为跨多个业务域的全栈贡献者。

### 从修 lock 文件到独立架构设计

> 另一位贡献者最初的提交只是修复 lock 文件和依赖管理。三个月后他开始承担 GUI 组件开发（代码编辑器、通知渠道卡片），到第七个月已经能独立设计通知系统的整体架构——从前端交互到后端推送渠道的完整链路。**92 个 commit**，从构建系统一路成长为架构决策者。

### 从单角色模板到战斗系统专家

> 还有一位贡献者加入时只做一个角色（席德）的战斗模板配置。随着不断深入，他逐步掌握了整个自动战斗模块的架构——从角色状态识别、闪避时机判定到多角色协作策略。持续 7 个月提交了 **73 个 commit**，成为战斗模块的核心维护者，覆盖 40+ 角色的战斗模板适配。

### 从功能开发到工程化质量守护

> 一位贡献者最初开发了游戏内商店功能（好物铺、邦巢购买），后来发现自己在代码质量和工程化方面更有热情——OCR GPU 修复、自动战斗时间戳 bug、代码清理、引入 Copilot 和 CodeRabbit 规则。从"写功能"成长为"守护项目质量"的角色。**15 个 commit**，方向比数量更重要。

## 参与方式

### 入门（适合刚学 Python 的同学）

- 修复带有 `good first issue` 标签的 issue
- 编写新角色的战斗模板配置（`config/auto_battle_state_handler/`）
- 开发锄大地路线（`config/world_patrol_route/`）

### 进阶（有 Python 基础，想做更多）

- 开发新的游戏自动化应用（参考 [应用开发指引](guides/application_plugin_guide.md)）
- 改进 GUI 组件和用户体验（`src/one_dragon_qt/widgets/`）
- 编写和补充测试用例

### 高级（想挑战架构和算法）

- ML 模型训练与部署（`src/one_dragon/yolo/`）
- OCR 引擎优化（`src/onnxocr/`）
- GUI 框架扩展（Fluent Design 组件库）
- 多线程架构优化（`gpu_executor` 异步推理）

## 快速开始

1. **Fork 并 Clone** 本仓库
2. 安装依赖：`uv sync --group dev`
3. 阅读统一入口：[AGENTS.md](../../AGENTS.md)
4. 阅读开发文档：[docs/develop/README.md](README.md)
5. 按需深入编码规范：[docs/develop/spec/agent_guidelines.md](spec/agent_guidelines.md)
6. 找一个感兴趣的 issue，开始你的第一个 PR

遇到问题？在 GitHub Discussions 或社区频道提问，我们很乐意帮助。

## 联系我们

- **GitHub**: [OneDragon-Anything/ZenlessZoneZero-OneDragon](https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon)
- **官网文档**: [one-dragon.com](https://one-dragon.com)
- **社区频道**: 见项目 README
