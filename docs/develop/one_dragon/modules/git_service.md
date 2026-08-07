# Git 服务与代码源回退

## 作用

`GitService` 负责本地代码仓库的初始化、代码源 fetch、候选代码源回退，以及 fetch 完成后的分支同步。代码源列表和主仓库由项目级 `repository.yml` 提供，框架不写死具体代码托管平台。

## 代码源选择与自动模式

设置界面的代码源下拉框包含“自动”和项目 `repository.yml` 声明的全部具体代码源。配置字段分工如下：

- `repository_url`：保存用户选择；值为 `auto` 时启用自动模式，具体 URL 时表示用户手动指定的首选源；旧配置缺失该字段时按自动模式处理。具体 URL 不再存在于 `repository.yml` 时，静默重置为 `auto`。
- `last_repository_url`：记录最近一次成功 fetch 使用的原始仓库 URL。

候选顺序为：

```text
自动模式：上次成功源 → 其余代码源按 YAML 顺序
手动模式：用户指定源 → 其余代码源按 YAML 顺序
```

候选源失败或超时后仍继续回退。只有候选源 fetch 成功后才更新 `last_repository_url`；记录的是 YAML 中的原始 URL，不是拼接 GitHub 代理后的临时请求 URL。自动模式的状态属于运行环境配置，具体代码源标题、URL、代理能力和 YAML 顺序仍由项目级 `repository.yml` 提供，框架不硬编码具体托管平台。

## fetch 线程隔离与作废式超时

Git 网络拉取不直接写正式仓库。每个候选代码源由一个 daemon 线程在独立 bare 仓库中执行 fetch，临时目录位于工作目录的 `.install/git_fetch_tmp/fetch_<进程ID>_*`。已有仓库更新时，临时仓库通过 `objects/info/alternates` 只读复用正式仓库对象；首次克隆使用 `depth=1`。

Windows 下，libgit2 从带 pack 的临时仓库导入后，可能在当前进程内继续持有源 pack 句柄。此时立即删除临时目录会得到 `WinError 5/32`，修改只读属性或短暂重试无法释放句柄。GitService 会保留该目录，不输出清理异常栈；下次进程首次 fetch 前，删除已确认所属进程退出的新格式目录和无法解析进程归属的旧格式 `fetch_*`，仅保留所属进程仍在运行的新格式目录。

```text
主线程
  └─ 启动 fetch 线程
       └─ .install/git_fetch_tmp/fetch_* ──网络──> 候选代码源

线程成功并退出
  └─ 主线程从临时 bare 仓库导入正式仓库

线程超时
  └─ 标记本次尝试作废，立即尝试下一个候选源
       └─ 原线程之后只清理自己的临时目录，不再导入
```

线程模型不能强制终止正在执行的 libgit2 原生调用。主线程超时后不等待、不 `join`，只设置作废标记并继续下一个候选源；作废线程以后即使 fetch 成功，也不得导入正式仓库或更新 `last_repository_url`。残留线程数的自然上界是候选代码源数量。

单个候选源仍执行三层应用超时：

- 启动后 10 秒内没有首条消息：作废；
- 已收到消息后连续 30 秒没有新消息：作废；
- 无论是否持续产生消息，总运行时间超过 120 秒：作废。

pygit2 的 `server_connect_timeout` 和 `server_timeout` 固定设置为 30 秒，只在进程内设置一次，不在线程间反复保存和恢复。`server_timeout` 是单次远程读写超时；持续有数据但速度很慢时通常不会触发，因此应用层 120 秒总时限仍负责兜底。

服务端通过 `sideband_progress` 返回 `Enumerating objects`、`Counting objects` 和 `Compressing objects`。这些回调是文本流分块，不保证一次回调就是完整一行；GitService 会跨回调缓存残片，遇到 `\r` 或 `\n` 后逐条输出。`Remote.fetch()` 正常返回后才冲刷最后残片；发生异常时放弃它。`update_tips` 会在输出引用更新前冲刷缓冲区，保证远程尾消息仍排在引用更新前。三种已知前缀分别显示为“枚举对象”“统计对象”“压缩对象”，后面的数量、百分比和远端原有 `done` 不变。客户端根据 `received_objects/total_objects` 显示“拉取对象”，根据 `indexed_deltas/total_deltas` 显示“处理增量”；两个阶段达到 100% 时追加 `done`，但整个 fetch 是否成功仍只以 `Remote.fetch()` 正常返回为准。终端入口继续按 `%` 和 `done` 决定回车刷新或换行。各回调字段、完成边界和 CNB 实测时序见 [pygit2 fetch 可观测数据](git_fetch_progress.md)。

首次浅拉取完成后，临时仓库的 `shallow` 文件必须按原始字节复制到正式仓库，不能使用 Windows 文本写入，否则 LF 会被转换为 CRLF，libgit2 下次打开仓库会报 `invalid parent OID at line 1`。该处理只防止新写入产生 CRLF，不自动修改已经存在的 `shallow` 文件。

## 本地对象库损坏自愈

如果临时仓库网络 fetch 已成功，但导入正式仓库时直接抛出 `KeyError: object not found`，则已确认正式仓库对象库缺失；worker 内的 fetch 异常会先包装成 `RuntimeError`，不会进入这个判定。所有候选源最终都失败时，只要至少一个可访问源在导入阶段确认对象缺失，就执行自愈；其他候选源同时发生超时、认证或网络错误，不会否决已经确认的本地对象缺失：

1. 释放当前 `Repository`；
2. 将实际 Git 目录重命名为 `.git.corrupted.<时间戳>`；
3. 用现有 clone 流程重新初始化和拉取；
4. 重建失败时保留备份，不递归再次重建。

只有超时、认证或网络错误而没有导入阶段的直接 `KeyError` 时，不触发重建。恢复旧仓库 `origin` 地址失败不会否决已经确认的对象缺失，因为重建会替换旧 Git 目录；没有对象缺失时，远程地址恢复失败返回 `LOCAL_UPDATE_FAILED`。linked worktree 或存在任何 `origin` 以外 remote 的仓库暂不执行自动备份重建，避免丢失开发仓库的额外远程配置；这类重建保护同样返回 `LOCAL_UPDATE_FAILED`。该自愈与 shallow 边界错误、模块清单不兼容是三类独立故障，不能互相替代修复。

## fetch、兼容性检查与 checkout 顺序

fetch worker 完成后，主进程导入的是远程跟踪引用，目标形态为：

```text
refs/remotes/<git_remote>/<git_branch>
```

导入过程不会自动创建或切换本地分支，也不会改变 `HEAD`。本地分支和工作区由后续 `_checkout_branch()` 负责：

1. 若 `refs/heads/<git_branch>` 不存在，则从远程跟踪引用创建本地分支；
2. 强制 checkout 该本地分支；
3. 将 `HEAD` 设置为该本地分支；
4. 再执行工作区与远程分支同步。

已有仓库的更新顺序是：

```text
fetch 远程跟踪引用
  ↓
检查目标 commit 的模块清单是否兼容当前 RuntimeLauncher
  ↓ 兼容
检查工作区状态
  ↓
checkout 目标本地分支
  ↓
同步工作区
```

模块清单不兼容时会在 checkout 前返回 `GitSyncStatus.RUNTIME_INCOMPATIBLE`，以避免旧版 RuntimeLauncher 切换到无法加载的新代码。此时 fetch 可能已经成功，`refs/remotes/<git_remote>/<git_branch>` 也可能已经存在，但当前工作区和 `HEAD` 不会被切换。该状态不表示 Git 仓库损坏，不会触发仓库重建。

首次初始化仓库时，集成启动器会把内置正式版本号作为 tag 传入，例如 `v2.4.6`。GitService 只拉取对应的 `refs/tags/v2.4.6`，将 lightweight 或 annotated tag peel 到 commit，再用该 commit 建立 `refs/remotes/<git_remote>/<git_branch>`；后续仍按普通本地分支 checkout，因此不会进入 detached HEAD。tag 对应构建当前 `.runtime` 时的源码提交，不再重复执行模块清单检查。

如果所有代码源都无法取得内置 tag，不退化为最新分支，以免首次 checkout 到不兼容代码。只有 `_fetch_remote()` 返回 `REMOTE_UNAVAILABLE` 时，首次初始化才转换为 `BUILTIN_TAG_UNAVAILABLE`；本地对象重建、远程地址恢复或仓库应用失败继续返回 `LOCAL_UPDATE_FAILED`，不能伪装成 tag 不可用。纯远程失败时保留新建的 `.git` 和安装包内置源码；目标本地分支仍不存在，所以下次启动仍按同一内置 tag 重试。即使导入 tag 时确认本地对象缺失并触发仓库重建，重建流程也继续使用该 tag，不改拉配置分支。非正式版本（`v0.0.0`、`dev+...`、`pr...`）不指定 tag，仍使用分支 fetch 和模块清单检查。

没有指定内置 tag 的首次初始化，以及已有仓库更新，都会在 checkout 前执行模块清单检查。不兼容时保留已拉取对象和远程跟踪引用，但不创建或切换本地分支；集成启动器继续运行安装包内或当前工作区中与 `.runtime` 匹配的源码。升级集成启动器后，下次同步可继续完成 checkout。

`fetch_latest_code()` 使用结构化状态，不让调用方比较错误文案：

- `SUCCESS`：首次准备、提交更新或分支切换已经完成，磁盘代码发生了有效变化；
- `UP_TO_DATE`：同步前后分支相同，且本地、远程提交相同，不需要重启；
- `RUNTIME_INCOMPATIBLE`：目标代码需要更新启动器后才能使用，checkout 前已停止；
- `BUILTIN_TAG_UNAVAILABLE`：首次正式版本无法完成内置 tag 的远程获取，不拉取最新分支；
- `REMOTE_UNAVAILABLE`：所有候选代码源都没有完成远程获取或导入，本地应用阶段尚未开始；
- `LOCAL_CHANGES`：程序文件改动或无法快进阻止了非强制更新，已有代码保持不变；
- `LOCAL_UPDATE_FAILED`：初始化、状态读取、checkout、reset、远程地址恢复或对象重建等本地步骤失败，磁盘代码完整性无法保证；
- `FAILED`：未预期异常的防御性兜底，正常已知路径不应返回它。

分支发生切换时，即使切换前后的提交 ID 相同，也返回 `SUCCESS`；只有分支和提交都没有变化时才返回 `UP_TO_DATE`。具体代码源、分支、引用、提交 ID、异常和重建结果只写日志。`GitSyncStatus` 的枚举值本身就是面向用户的中性结果文案，只说明发生了什么；`GitService` 根据最终状态返回该枚举值对应的文案，代码卡和启动器分别追加重启、强制更新、继续运行或停止等场景建议。调用方不从中文错误消息反推状态，也不把所有失败都解释为网络问题。

因此，排查日志时要区分以下状态：

- `远程代码拉取成功`：只表示候选源 fetch 和临时仓库导入成功；
- `成功切换到分支 <git_branch>`：才表示本地分支和 `HEAD` 已完成 checkout；
- `RUNTIME_INCOMPATIBLE`：表示流程在 checkout 前被模块清单检查拦截；
- `LOCAL_UPDATE_FAILED`：表示本地更新步骤没有完整完成，调用方不得假定磁盘代码可安全加载。

旧仓库如果遗留 `HEAD -> refs/heads/master`，而本地 `master` 引用已经不存在，后续依赖 `repo.head.target` 的提交历史读取会报 `reference 'refs/heads/master' not found`。这类错误不表示远程 fetch 失败，应先检查同次日志中的 checkout 和模块清单检查结果，以及本地 `HEAD` 实际指向。

## Windows 与 PyInstaller 入口

fetch 已改为线程模型，不再创建 `multiprocessing.spawn` 子进程，因此公共启动器不再调用 `multiprocessing.freeze_support()`。这减少了 PyInstaller 冻结程序重新进入启动入口和额外收集 multiprocessing worker 依赖的风险。

该变化不表示线程能够可靠终止 libgit2：超时语义是“主流程作废并继续”，不是“终止原生 fetch”。

## 回退边界

应用超时只针对单个候选代码源的一次 fetch。一个源被作废或失败后，主线程继续尝试下一个源；所有候选源的总耗时可能是多个单源时限之和。被作废线程可能在后台继续占用 socket 和线程，直到 libgit2 返回。正常 fetch 的对象导入、分支更新和工作区同步仍只由当前有效尝试在主线程完成。
