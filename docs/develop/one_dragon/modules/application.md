# Application

应用，在一条龙框架中，通常是一系列 Operation 的组合，用于完成一个具体的任务。

> 相关文档：[Operation 操作模块](operation.md) | [应用插件系统架构](application_plugin_system.md) | [应用开发指引](../../guides/application_plugin_guide.md) | [应用设置开发指引](../../guides/application_setting_guide.md)

`Application`继承于[Operation](operation.md)，拥有`Operation`的相同的编排能力，并添加应用配置和运行记录等功能。

## 应用工厂

每个自定义应用，需要继承实现 `ApplicationFactory` 类，用于定义应用唯一标识和提供应用相关内容的创建方式。

## 自定义应用

需继承 `Application` 类，进行任务的操作编排。

(待补充更多说明)

## 应用配置

需继承 `ApplicationConfig` 类，用于定义应用所需配置。

应用配置的维度是 `app_id` + `instance_idx` + `group_id`，即应用(app_id)在不同的账号(instance_idx)和不同的应用组(group_id)中，可以有不同的配置。

```
config/
├── 01/                             # 实例01
│   ├── one_dragon/                 # 默认应用组 (group_id=one_dragon)
│   │   ├── _group.yml               # 应用组配置
│   │   ├── coffee.yml              # 咖啡应用配置 (如果在use_group_config中)
│   │   └── email.yml               # 邮件应用配置 (如果在use_group_config中)
│   ├── daily_tasks/                # 日常应用组
│   │   ├── _group.yml               # 应用组配置
│   │   ├── coffee.yml              # 咖啡应用在日常应用组中的配置
│   │   └── email.yml               # 邮件应用在日常应用组中的配置
│   └── farming/                    # 体力消耗应用组
│       ├── group.yml               # 应用组配置
│       └── coffee.yml              # 咖啡应用在体力消耗组中的配置
└── 02/                             # 实例02
    └── ...
```

## 运行记录

需继承 `ApplicationRunRecord` 类，用于定义应用的运行记录。

一个任务的运行记录应该是账号下唯一的，即不管分配到哪些应用组中，要完成的内容是固定的。

所以运行记录的维度是 `app_id` + `instance_idx`，即应用(app_id)在不同的账号(instance_idx)中，有不同的运行记录。

(待补充更多说明)


## 运行上下文

`ApplicationRunContext` 提供以下功能：

- 应用注册 - 所有需要运行的应用都将 `ApplicationFactory` 注册进来，后续用于获取应用相关内容。
- 提供应用运行记录的统一刷新接口。
- 返回 `ApplicationRunResult` 作为统一结束语义，`STOP` 只表示状态停止，具体结果通过 `RunFinishReason` 区分为正常完成、停止、失败和未启动。
- 通过 `last_run_result` 固化最近一次已经确定的运行终态，保证重复停止和并发收口复用首次结果，不重复派发 STOP 事件或覆盖结束原因。
- `last_application_result` 保存应用 `execute()` 返回的 `OperationResult`，用于读取应用自身的成功状态和状态文本；它与 `ApplicationRunResult` 分别表示应用执行结果和运行生命周期结果。
- GUI 的 `after_done` 配置和 CLI 的收尾参数只在一条龙入口使用：CLI 在 `run_application()` 返回后执行 finalizer；GUI 在 `AppRunner.finished` 回调中读取当时的 `after_done` 并执行 finalizer。
- 一条龙 GUI 使用 `after_done` 配置表达是否执行运行后操作及具体动作；通用 `ApplicationRunContext.run_application()` 只负责运行应用并返回 `ApplicationRunResult`，不负责关闭游戏或关机。

通用 GUI 的 `AppRunner` 只保存本次异步调用返回的 `ApplicationRunResult`。一条龙界面在线程 `finished` 后读取当前 `after_done`，再决定是否调用一条龙专属 finalizer；普通应用和 `run_app_by_item()` 不执行结束后动作。

可以自由组合不同的应用成为一个应用组，每个应用组会有一个唯一标识 `group_id`。

默认会有一个 `gourp_id='one_dragon'` 的应用组。

### 应用组配置

使用 `ApplicationGroupConfig`，存放位置 `config/{instance_idx}/{group_id}/_group.yml`。

主要包含：

- 一个应用列表，说明了应用的运行顺序和是否启用。
- 完成后是否推送消息。

### 应用组管理

使用 `ApplicationGroupManager` 获取具体的应用组配置。

默认应用组(one_dragon)会在初始化的注册应用后，添加到应用组管理器中。配置中从未出现过的新应用会按当前默认顺序显示在列表头部，初始为禁用状态，但不会立即写入用户保存的应用顺序；用户第一次启用、拖拽排序或点击运行后才会保存，拖拽排序会保存当前显示的完整顺序，点击运行会保存被运行应用的当前位置。已有应用的顺序和启用状态保持不变。

### 应用组运行

通过 `GroupApplication` 执行一个应用组，该类提供：

- 按顺序执行应用
- 完成后推送消息
