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

Git 网络拉取不直接写正式仓库。每个候选代码源由一个 daemon 线程在独立 bare 仓库中执行 fetch，临时目录位于工作目录的 `.install/git_fetch_tmp/fetch_*`。已有仓库更新时，临时仓库通过 `objects/info/alternates` 只读复用正式仓库对象；首次克隆使用 `depth=1`。

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

如果临时仓库网络 fetch 已成功，但导入正式仓库时抛出 `KeyError: object not found`，该候选源记为“本地对象缺失”。只有所有候选源都以这一原因失败，才判定正式仓库对象库损坏：

1. 释放当前 `Repository`；
2. 将实际 Git 目录重命名为 `.git.corrupted.<时间戳>`；
3. 用现有 clone 流程重新初始化和拉取；
4. 重建失败时保留备份，不递归再次重建。

超时、网络错误和对象缺失混合出现时不触发重建。linked worktree 暂不执行自动备份重建。该自愈与 shallow 边界错误、模块清单不兼容是三类独立故障，不能互相替代修复。

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

模块清单不兼容时会在 checkout 前返回失败，以避免旧版 RuntimeLauncher 切换到无法加载的新代码。此时 fetch 可能已经成功，`refs/remotes/<git_remote>/<git_branch>` 也可能已经存在，但当前工作区和 `HEAD` 不会被切换。

因此，排查日志时要区分以下状态：

- `远程代码拉取成功`：只表示候选源 fetch 和临时仓库导入成功；
- `成功切换到分支 <git_branch>`：才表示本地分支和 `HEAD` 已完成 checkout；
- `代码更新失败: 目标版本的运行环境与当前不兼容`：表示流程在 checkout 前被模块清单检查拦截。

旧仓库如果遗留 `HEAD -> refs/heads/master`，而本地 `master` 引用已经不存在，后续依赖 `repo.head.target` 的提交历史读取会报 `reference 'refs/heads/master' not found`。这类错误不表示远程 fetch 失败，应先检查同次日志中的 checkout 和模块清单检查结果，以及本地 `HEAD` 实际指向。

## Windows 与 PyInstaller 入口

fetch 已改为线程模型，不再创建 `multiprocessing.spawn` 子进程，因此公共启动器不再调用 `multiprocessing.freeze_support()`。这减少了 PyInstaller 冻结程序重新进入启动入口和额外收集 multiprocessing worker 依赖的风险。

该变化不表示线程能够可靠终止 libgit2：超时语义是“主流程作废并继续”，不是“终止原生 fetch”。

## 回退边界

应用超时只针对单个候选代码源的一次 fetch。一个源被作废或失败后，主线程继续尝试下一个源；所有候选源的总耗时可能是多个单源时限之和。被作废线程可能在后台继续占用 socket 和线程，直到 libgit2 返回。正常 fetch 的对象导入、分支更新和工作区同步仍只由当前有效尝试在主线程完成。
