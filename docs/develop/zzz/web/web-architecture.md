# 后端服务架构

## 核心组件

### ZzzWebContext

作为 web 服务的统一资源管理器，负责 ZzzContext 的初始化和其他web所需资源的初始化。

后续通过 Depends 注入到各接口中进行使用。

### WebLogBridge

日志桥接，将日志内容发送到 websocket 中。

### WebApplicationBridge

应用桥接，将应用运行状态发送到 websocket 中。

## 核心交互流程

### 后端启动

1. ZzzWebContext 初始化，包含
   1. ZzzContext 初始化
   2. WebLogBridge 初始化
   3. WebApplicationBridge 初始化

### 打开页面

1. 前端请求页面，后端返回打包压缩的页面。
2. 自动连接`日志事件`的websocket。后续后端将日志发送到前端显示。
3. 自动连接`运行状态事件`的websocket。创建连接时，后端发送当前运行状态。后续后端将运行状态事件发送到前端更新显示。

### 运行应用

1. 前端发起请求。
2. 后端到 ApplicationService 尝试启动应用。
3. 后端通过 `运行状态事件` 发送通知运行情况，包括不能启动的情况。

### 日志显示

1. 打开网页时，自动连接`日志事件`的websocket。
2. 后端启动时，加入 `LogHandler` ，将日志内容发送到 websocket 中。
