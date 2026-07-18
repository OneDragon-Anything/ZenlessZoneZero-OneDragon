# 一条龙架构

> 相关文档：[初始化流程](initialization.md) | [应用插件系统](modules/application_plugin_system.md) | [操作模块](modules/operation.md) | [通知配置](modules/notify.md) | [CV 流水线架构](modules/cv_pipeline_architecture.md)
>
> 注意：本文档部分内容标注了"未实现/待改造"，最新实现以代码为准。应用相关架构详见 [应用插件系统](modules/application_plugin_system.md)。

## 核心组件

### OneDragonContext

一条龙运行上下文，负责职责包括：

- 资源管理
- 初始化
- 保存运行状态
- 运行环境相关管理 (OneDragonEnvContext)
- 提供事件总线 (ContextEventBus)

### OcrMatcher

OCR匹配器，负责职责包括：

- OCR模型加载
- 图片的文本识别

### OcrService

OCR服务，负责职责包括：

- 图片的OCR结果缓存
- OCR多线程支持 （未实现）

### TemplateLoader

模板加载器，负责职责包括：

- 加载和缓存用于匹配的模板

### TemplateMatcher

模板匹配器，负责职责包括：

- 模板匹配
- 特征匹配

需持有组件：

- TemplateLoader: 用于获取模板

### ControllerBase

控制器基类，负责职责包括：

- 进行游戏截图
- 发送游戏指令 （鼠标、键盘等）

需要根据平台使用具体子类，例如 PcControllerBase

### ScreenContext

画面上下文，负责职责包括：

- 画面配置、路由的加载
- 当前画面判断
- 前往画面方式判断

### ApplicationGroupConfigManager (未实现)

应用组配置管理器，负责职责包括：

- 应用组的增删改查

### ApplicationFactory

应用工厂，每个应用需要定义一个工厂类。负责职责包括：

- 创建Application实例
- 创建应用配置
- 创建运行记录

### ApplicationRunContext

应用运行上下文，负责职责包括：

- 应用注册
- 获取Application实例
- 获取和缓存应用配置、运行记录
- 管理应用运行、相关事件发送
- 产出统一的运行结束结果，区分正常完成、停止、失败和未启动等原因
- 通过 `last_run_result` 保存最近一次已经确定的 `ApplicationRunResult`，用于重复停止和并发收口时复用首次结果，避免重复派发 STOP 事件或覆盖结束原因

`ApplicationRunResult` 描述运行生命周期结果；应用自身 `execute()` 返回的 `OperationResult` 则保存在 `last_application_result`，供需要读取应用具体执行状态的调用方使用。两者分别回答“运行如何结束”和“应用执行返回了什么”。

需持有组件：

- ApplicationFactory

### 一条龙结束后动作

一条龙运行界面的“结束后”配置支持无操作、关闭游戏、关机等收尾动作。
GUI 使用 `after_done` 配置表达是否执行运行后操作及具体动作；CLI 则使用命令行参数描述动作。两者都由一条龙 GUI/CLI 入口在 `ApplicationRunContext.run_application()` 返回后调用同一 finalizer，根据 `ApplicationRunResult.finish_reason` 判定。
通用运行上下文只返回运行结果，不感知关闭游戏或关机；单项应用运行也不会触发一条龙的结束后动作。
`STOP` 仅表示运行状态已经停止，不等价于“自然完成”。

### SqliteDataSource (未实现)

数据源，负责职责包括：

- 管理 Sqlite 链接
- 迭代表变更

### ConfigRepository (未实现)

配置仓库，负责职责包括：

- 配置类的增删改查

需持有组件：

- SqliteDataSource

## 核心流程

### 初始化 (待改造)

1. 应用注册
2. 各服务创建和模型加载

### 运行应用 (待改造)

1. 检查当前应用运行情况
2. 如果当前已有运行，拒绝新的运行的请求
3. 如果当前空闲，则创建新的异步运行任务，并保存记录

### 迭代更新数据库 (待改造)

1. 检查并创建 `schema_version` 表，仅有 `version` 字段，用于记录当前已经执行的版本。
2. 遍历 `assets/db/schema/` 目录下的文件，按照文件名 (规范为 `yyyy-MM-dd.sql`) 排序，遍历执行 >= `version` 的文件，并更新 `version` 字段。
