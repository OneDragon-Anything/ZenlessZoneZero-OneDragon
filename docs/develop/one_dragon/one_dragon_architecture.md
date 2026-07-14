# 一条龙架构

> 相关文档：[初始化流程](initialization.md) | [应用插件系统](modules/application_plugin_system.md) | [操作模块](modules/operation.md) | [通知配置](modules/notify.md) | [CV 流水线架构](modules/cv_pipeline_architecture.md)

本文说明一条龙框架当前的核心组件和运行流程。应用发现、设置界面和插件开发的细节以对应专项文档为准。

## 核心上下文

### OneDragonContext

`OneDragonContext` 是运行期的总上下文，负责组织以下能力：

- 环境配置、账号实例配置和事件总线
- OCR、模板匹配、画面配置与输入控制器
- 应用工厂发现、应用注册和应用组配置
- 应用运行状态、运行记录、通知与推送

项目上下文在此基础上补充游戏配置、控制器和业务服务。例如绝区零使用 `ZContext`。

## 识别与控制

### ScreenContext

`ScreenContext` 负责加载画面和区域配置、维护画面路由，以及按应用限制可用画面范围。内置画面从合并后的 YAML 加载，插件可以通过自己的 `screen_info` 目录追加画面。

### OCR

- `OcrMatcher`：执行文字识别和文本匹配。
- `OcrService`：封装 OCR 调用并缓存同一截图、区域和颜色范围的识别结果。

### 模板匹配

- `TemplateLoader`：加载并缓存模板资源。
- `TemplateMatcher`：执行普通模板匹配和特征匹配。

### ControllerBase

`ControllerBase` 定义截图和输入控制接口。具体项目根据平台提供控制器实现，例如 PC 控制器负责查找游戏窗口并发送键鼠或手柄输入。

## 应用系统

### ApplicationFactoryManager

`ApplicationFactoryManager` 扫描内置应用和第三方插件，加载应用工厂并记录插件信息。运行时刷新应用时也由它重新发现工厂和卸载旧模块。

### ApplicationFactory

每个应用通过 `ApplicationFactory` 提供以下内容：

- 应用实例
- 应用配置
- 运行记录

### ApplicationRunContext

`ApplicationRunContext` 负责：

- 注册应用工厂并按需创建应用、配置和运行记录
- 记录当前应用、实例、应用组和运行状态
- 同步运行应用，并保存最终 `OperationResult`
- 通过线程池提供异步运行入口

### ApplicationGroupManager

`ApplicationGroupManager` 根据 `instance_idx` 和 `group_id` 加载并缓存 `ApplicationGroupConfig`。默认一条龙应用组会与当前注册的默认应用列表同步。

### GroupApplication

`GroupApplication` 按配置顺序执行应用组：

1. 读取当前实例的应用组配置。
2. 跳过未启用或运行记录已完成的应用。
3. 设置当前应用和应用组上下文后执行应用。
4. 恢复上层上下文并继续下一个应用。

## 核心流程

### 初始化

1. 创建项目上下文并调用 `init()` 或 `init_async()`。
2. 首次初始化时发现并注册应用工厂，更新默认应用组。
3. 初始化 OCR，加载内置和插件画面配置。
4. 加载当前账号实例配置并创建控制器。
5. 执行项目级应用初始化。
6. 标记上下文可运行，并刷新当前实例的运行记录。

### 运行应用

`run_application()` 会等待上下文初始化完成，检查应用注册和运行状态，然后创建应用并同步执行。运行期间会维护当前应用、实例和应用组信息，结束后保存结果并清理运行状态。

`run_application_async()` 只负责把同一同步入口提交到线程池，避免阻塞调用线程。

### 一条龙运行

一条龙会按照“运行实例”的设置依次完成各账号任务，多账号运行时自动切换登录。每个账号的默认应用组配置和运行记录相互独立。

每个实例都可以在“账号管理 → 当前账户设置”中单独开启“强制重新登录”。开启后，流程进入 `EnterGame` 时会使用该实例的账号配置重新登录；已经进入大世界且不需要执行登录流程时不会主动登出。

### 刷新应用注册

`refresh_application_registration()` 会清空已有注册、重新发现应用工厂、重新加载插件画面、更新默认应用组并清除相关配置缓存。该流程用于运行时加载或更新插件，不需要重启上下文。
