# Runner 日志分流设计

## 背景

`script_runner` 以独立命令行进程运行脚本链。这个进程里会同时出现两类日志：

- runner 主流程日志：脚本链状态、脚本 stdout、启动失败、监控超时、进程清理异常。
- OneDragon 框架日志：配置读取、上下文初始化、推送服务、HTTP 请求、通知渠道异常。

这两类日志关注点不同。runner 主日志面向脚本链运行排查，框架日志面向底层服务排查。它们如果写入同一个轮转文件，在 Windows 下还可能因为多个 `TimedRotatingFileHandler` 同时持有同一个文件句柄，导致归档时出现 `WinError 32`。

## 目标

- GUI 默认日志行为不变，继续使用框架默认 `log.txt`。
- runner 主流程日志写入 `script_chainer_runner.log`。
- runner 进程中触发的框架日志写入 `script_chainer_framework.log`。
- 不让两个 logger 共享同一个文件 handler 或同一个轮转文件。
- 日志分流能力由 OneDragon 框架提供，但默认不启用。
- 各项目根据自己的运行场景显式开启日志分流。

## 非目标

- 不重写所有框架模块的 logger 获取方式。
- 不把 OneDragon 全局 `log` 改成依赖注入。
- 不改变 GUI、配置编辑器等常规进程的默认日志文件。

## 框架层设计

`one_dragon.utils.log_utils` 提供通用日志配置能力。

默认 logger：

```text
OneDragon -> <work_dir>/.log/log.txt
```

显式分流入口：

```python
configure_project_runtime_logging(
    project_logger_name: str,
    project_log_file_path: str,
    framework_log_file_path: str,
    *,
    level: int = logging.INFO,
    project_add_console_handler: bool = False,
    framework_add_console_handler: bool = False,
    framework_logger_name: str = LOGGER_NAME,
) -> ProjectRuntimeLoggingContext
```

这个 API 会分别配置：

```text
project_logger_name -> project_log_file_path
framework_logger_name -> framework_log_file_path
```

返回值 `ProjectRuntimeLoggingContext` 包含：

- `project_logger`
- `framework_logger`
- `project_log_file_path`
- `framework_log_file_path`

该能力是 opt-in。项目不调用 `configure_project_runtime_logging(...)` 时，框架默认日志仍然写 `log.txt`。

## Handler 管理

框架创建的 handler 会带上 `_one_dragon_logger_owner` 标记。重新配置 logger 时，只移除同一 logger 上由框架托管的 handler，不移除外部手动挂载的 handler。

这样可以支持：

- 默认 logger 初始化。
- 运行态重新配置。
- 保留第三方或调用方额外挂载的 handler。

文件日志使用 `TimedRotatingFileHandler`：

```text
when = midnight
interval = 1
backupCount = 3
delay = True
```

`delay=True` 表示 handler 创建时不立即打开文件，第一次写日志时才打开。这样可以减少 import 阶段的文件句柄占用。

## ScriptChainer 适配层

`script_chainer.win_exe.runner_logging` 是 ScriptChainer runner 的日志适配层。它不重新实现日志系统，只定义 runner 场景下的项目配置：

```text
RUNNER_LOGGER_NAME = ScriptChainerRunner
RUNNER_LOG_FILE_NAME = script_chainer_runner.log
RUNNER_FRAMEWORK_LOG_FILE_NAME = script_chainer_framework.log
```

路径策略：

- 打包运行时：使用 `sys.executable` 所在目录下的 `.log/`
- 源码运行时：沿用框架默认工作目录 `.log/`

runner 适配层暴露：

```python
log = logging.getLogger(RUNNER_LOGGER_NAME)
configure_runner_runtime_logging()
```

`configure_runner_runtime_logging()` 内部调用框架的 `configure_project_runtime_logging(...)`。

## Runner 使用方式

`script_runner.py` 只导入 runner 适配层提供的 logger 和配置函数：

```python
from script_chainer.utils.runner_logging import (
    configure_runner_runtime_logging,
    log,
)
```

在 `run_chain()` 开始时调用：

```python
configure_runner_runtime_logging()
```

之后 `script_runner.py` 中的 `log.info(...)` / `log.error(...)` 都写入 `script_chainer_runner.log`。

runner 进程中框架模块直接使用的 `one_dragon.utils.log_utils.log` 会写入 `script_chainer_framework.log`。

## 日志文件布局

打包运行时：

```text
<exe_dir>/.log/script_chainer_runner.log
<exe_dir>/.log/script_chainer_framework.log
```

GUI 默认：

```text
<work_dir>/.log/log.txt
```

## 失败模式与规避

Windows 下同一个日志文件不能可靠地被多个 `TimedRotatingFileHandler` 同时轮转。当前设计通过分文件规避：

```text
ScriptChainerRunner -> script_chainer_runner.log
OneDragon -> script_chainer_framework.log
```

每个日志文件只有一套框架托管的 file handler，归档时不会互相占用同一个文件。

## 权衡

当前 OneDragon 代码中很多模块直接使用全局 `log`。完整改造成 logger 注入会带来较大改动。日志分流选择在进程启动时显式重定向框架 logger，可以用较小改动达成隔离目标。

这也保留了清晰边界：

- 框架提供可选分流能力。
- 项目决定何时启用。
- runner 只关心自己的 logger。
- GUI 默认行为不受影响。
