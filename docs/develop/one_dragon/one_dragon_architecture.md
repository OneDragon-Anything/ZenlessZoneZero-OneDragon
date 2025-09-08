# 一条龙架构

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

需持有组件：

- ApplicationFactory

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
