# 开发指引

本文档提供开发过程中的指引和参考文档。

## 快速链接

- [项目概述](project-overview.md) - 项目介绍和技术栈
- [开发规范](standards/coding-standards.md) - Python 代码规范和编码约定
- [开发环境](development-environments.md) - 开发环境配置说明
- [测试规范](standards/testing-standards.md) - 测试编写和执行规范
- [文档规范](standards/documentation-standards.md) - 文档编写规范和最佳实践
- [开发流程规范](standards/workflow-standard.md) - 开发流程和 Submodule 使用规范

## 架构文档

### one_dragon 框架
- [框架架构](one_dragon/one_dragon_architecture.md) - 基础框架架构
- [模块文档](one_dragon/modules/) - 各模块详细文档
  - [操作系统](one_dragon/modules/operation.md) - 基于节点的状态机
  - [屏幕系统](one_dragon/modules/screen_system.md) - 画面识别和导航
  - [应用层](one_dragon/modules/application.md) - 高层业务逻辑
  - [条件操作](one_dragon/modules/conditional_operation.md) - 条件操作
  - [推送系统](one_dragon/modules/push.md) - 推送通知
  - [数据库操作](one_dragon/modules/sqlite.md) - SQLite 数据库
- [应用插件系统](one_dragon/application_plugin_system.md) - 插件架构
- [CV 管道架构](one_dragon/cv_pipeline_architecture.md) - 计算机视觉处理
- [目标状态模块开发指南](one_dragon/target_state_module_developer_guide.md)
- [初始化流程](one_dragon/initialization.md) - 应用启动和初始化

### zzz 游戏
- [应用开发](zzz/application/) - ZZZ 游戏应用开发文档
- [MCP 服务器](zzz/mcp/) - MCP 服务器开发文档
- [Web 服务](zzz/web/) - Web 服务架构文档

## 开始开发

### 环境配置

详见 [项目概述](project-overview.md) 的快速开始部分。

**关键环境变量**：
- `PYTHONPATH=src` - 必须设置，指定 Python 源码路径
- 使用 `.env` 文件管理，运行时加 `--env-file .env`

### 运行测试

测试相关内容见 [测试规范](standards/testing-standards.md)。

### 开发流程

详见 [开发流程规范](standards/workflow-standard.md)。
