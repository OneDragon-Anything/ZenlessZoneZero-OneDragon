# Git 服务与代码源回退

## 作用

`GitService` 负责本地代码仓库的初始化、代码源 fetch、候选代码源回退，以及 fetch 完成后的分支同步。代码源列表、主仓库和项目主分支由项目级 `repository.yml` 提供，框架不写死具体代码托管平台或主分支名称。

## 代码源选择与自动模式

设置界面的代码源下拉框包含“自动”和项目 `repository.yml` 声明的全部具体代码源。配置字段分工如下：

- `repositories.primary_branch`：声明同一逻辑仓库在所有镜像代码源上共享的项目主分支；该值必须存在于 `repositories.branches`，运行环境缺失 `git_branch` 时默认使用该值。
- `repositories.branches`：按 YAML 顺序声明代码版本下拉框的分支值、显示名称和说明；界面不再内置 `main`、`test` 等具体分支。
- `repository_url`：保存用户选择；值为 `auto` 时启用自动模式，具体 URL 时表示用户手动指定的首选源；旧配置缺失该字段时按自动模式处理。具体 URL 不再存在于 `repository.yml` 时，静默重置为 `auto`。
- `last_repository_url`：记录最近一次成功 fetch 使用的原始仓库 URL。

候选顺序为：

```text
自动模式：上次成功源 → 其余代码源按 YAML 顺序
手动模式：用户指定源 → 其余代码源按 YAML 顺序
```

候选源失败或超时后仍继续回退。只有候选源 fetch 成功后才更新 `last_repository_url`；记录的是 YAML 中的原始 URL，不是拼接 GitHub 代理后的临时请求 URL。自动模式的状态属于运行环境配置，具体代码源标题、URL、代理能力和 YAML 顺序仍由项目级 `repository.yml` 提供，框架不硬编码具体托管平台。

## fetch 线程隔离与作废式超时

Git 网络拉取不直接写正式仓库。每个候选代码源由一个 daemon 线程在独立 bare 仓库中执行 fetch，临时目录位于工作目录的 `.install/git_fetch_tmp/fetch_<进程ID>_*`。临时仓库会通过 `objects/info/alternates` 只读复用正式仓库对象，并继承正式仓库的完整 shallow 快照；需要增量协商时，还会建立已有目标分支或完整项目主分支的基线引用。项目主分支名称取自 `repository.yml` 的 `repositories.primary_branch`，不假定为 `main`。shallow 和引用设置完成后重新打开临时 `Repository`，再创建 remote。普通网络 fetch 和正式仓库从临时仓库导入时都设置 `tagopt=--no-tags`，并在写入配置后重新取得 Remote 句柄，避免自动跟随指向已取得对象的 tag；显式指定的内置 tag 仍由目标 tag refspec 获取。

已有目标本地分支更新前会遍历该分支历史：完整历史和合法 shallow 都建立目标分支基线并执行 `depth=0` 增量 fetch。项目主分支作为跨分支基线时若遍历遇到未被 shallow 声明的父提交缺口，把主分支缺口前的单个可达提交追加为 shallow 边界并提示开发者执行 `git fetch --unshallow` 补全历史，不再整仓重建；目标分支自身历史遇到缺口、或主分支修复后仍无法遍历时，停止候选源回退并备份重建本地 Git 仓库，不猜测 shallow 边界或降级拉取掩盖损坏。首次获取非项目主分支时，如果本地远程跟踪项目主分支（其次为同名本地分支）的历史可遍历（完整或合法 shallow），临时仓库会建立该引用，并在一次 `depth=0` fetch 中同时获取远端最新项目主分支与目标分支。项目主分支不存在、不可遍历、alternates 不可用，或该联合增量失败时，只对目标分支回退执行 `depth=1`。按内置版本 tag 初始化时不参与项目主分支增量，始终只获取指定 tag；首次获取项目主分支也继续使用 `depth=1`。

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

## 仓库级 shallow 状态同步

`$GIT_DIR/shallow` 是整个仓库的浅边界 OID 集合，不记录分支名。一个分支可能经过多个边界，多个分支也可能共享同一边界，因此不能把“本次分支临时仓库”的 shallow 文件直接覆盖正式仓库，也不能无条件对旧、新文件取并集：覆盖会删除其他分支仍需要的边界，并集则可能保留已经深化过的旧边界，使新取得的历史仍不可遍历。

每次 fetch 把正式仓库 shallow 的原始二进制内容同时作为输入和回滚快照：

1. 正式对象目录可用时，临时仓库通过 alternates 继承对象库，并复制完整 shallow 快照；与本次协商有关的目标分支或项目主分支引用也一并建立。
2. libgit2 在该整仓状态上执行 fetch，并更新临时仓库的整份 shallow 状态。项目主分支联合增量或普通增量需要回退 `depth=1` 时，先恢复 fetch 前的 shallow 快照，删除协商引用并重新打开临时仓库，不能沿用失败尝试留下的元数据。
3. 主线程导入对象和引用前保存正式 shallow 与受影响 refs。完整继承成功时，以临时仓库 fetch 后的 shallow 存在状态和原始字节为权威，精确镜像到正式仓库；正式仓库原先有边界但无法完整继承时，只执行经过 LF/OID 校验的保守并集，仅新增边界，不删除旧边界。
4. shallow 使用同目录临时文件和 `os.replace()` 原子写回；权威状态为空时删除正式 shallow。导入或写回失败时恢复原 shallow 与 refs，已经写入但未被引用的对象允许保留。
5. shallow 写回后释放旧 `Repository` 并重新打开，后续 tag peel、远程跟踪引用建立和历史遍历都使用刷新后的句柄，避免 libgit2 继续使用旧边界缓存。

目标分支历史有两种可继续使用的状态：

- **完整历史**：遍历成功且没有经过已声明浅边界，可作为自身增量基线；完整项目主分支还可作为首次获取其他分支的联合增量基线。
- **合法 shallow**：遍历在已声明边界停止，可作为该分支自身的增量基线；临时仓库继承整仓 shallow 后，浅项目主分支同样可作为其他分支跨分支增量 fetch 的协商基线，不需要主分支历史完整。

遍历遇到缺失父对象但没有对应 shallow 边界，属于本地仓库损坏，不是第三种可继续 fetch 的状态。项目主分支作为跨分支基线时遇到这类缺口，GitService 会沿第一父链取缺口前最后一个可达提交作为单一 shallow 边界，追加到整仓 shallow 后重新打开仓库并再次遍历；若主分支含合并历史，则取合并之后仍在主分支上的提交作为边界，不再为多条父链分别推导。追加只做增量，不覆盖已有边界；修复成功后日志提示开发者执行 `git fetch --unshallow <remote> <主分支>` 补全历史。修复后仍无法遍历、或缺口出现在目标分支自身历史时，才进入整仓重建，不猜测其他边界。

shallow 始终使用二进制和 LF 行尾。Windows 文本写入会把 LF 转为 CRLF，libgit2 下次打开仓库时报 `invalid parent OID at line 1`；已有 CRLF 或其他格式错误的 shallow 保持原字节作为备份现场，并触发整仓重建，不在旧 Git 目录中自动修复或重写。进程在正式对象导入已经返回、shallow 原子写回尚未执行之间被强制终止，仍可能留下短暂不一致；当前事务只保证同一进程内的异常回滚，不扩展为跨进程恢复日志。

## 本地 Git 仓库损坏自愈

以下情况统一表示旧 Git 仓库不可继续信任：

- shallow 文件格式不合法，导致快照校验失败或 `Repository` 无法打开；
- 遍历已有目标分支时遇到未被 shallow 声明的父对象缺口；
- 项目主分支作为跨分支基线时的缺口经单边界修复后仍无法遍历；
- 临时仓库网络 fetch 已成功，但导入正式仓库时直接抛出 `KeyError: object not found`。

确认任一情况后立即停止候选源回退，因为切换代码源不能修复本地元数据或对象库。项目主分支作为跨分支基线遇到缺口时，先尝试把缺口前的单个可达提交追加为 shallow 边界（见「仓库级 shallow 状态同步」），修复失败才落入下列整仓重建；其他分支的缺口不猜测边界，直接重建：

1. 使用 `discover_repository()` 定位实际 Git 目录，不要求旧 `Repository` 能成功打开；
2. 检查当前目录是否为 linked worktree、主 Git 目录是否仍管理其他 worktree；旧仓库能打开时检查额外 remote，打不开时不解析旧配置，直接进入备份；
3. 释放可用的 `Repository` 句柄，将实际 Git 目录重命名为 `.git.corrupted.<时间戳>`；
4. 复用现有 clone 流程，只对目标分支或指定内置 tag 执行显式 refspec 的 `depth=1` 拉取；
5. 重建失败时保留备份，不递归再次重建。

重建仍是浅克隆，不拉完整历史，也不自动跟随其他 tag。指定内置 tag 会原样传入重建流程；tag 不可用时不退化到配置分支。只有超时、认证或网络错误而没有上述本地损坏信号时，才继续候选源回退且不触发重建。当前目录是 linked worktree，或主 Git 目录仍管理其他 worktree 时，暂不执行自动备份重建。旧仓库能够打开且存在任何 `origin` 以外 remote 时也不重建，避免破坏开发仓库；旧仓库无法打开时不再解析 remote 配置，直接改名备份。这类保护失败统一返回 `LOCAL_UPDATE_FAILED`。

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
