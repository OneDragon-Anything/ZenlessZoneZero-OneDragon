# Git 服务与代码源回退

## 作用

`GitService` 负责本地代码仓库的初始化、代码源 fetch、候选代码源回退，以及 fetch 完成后的分支同步。代码源列表和主仓库由项目级 `repository.yml` 提供，框架不写死具体代码托管平台。

## fetch 进程隔离

Git 网络拉取不直接在正式仓库中执行。单个候选代码源的 fetch 由 `multiprocessing` 的 `spawn` worker 执行，worker 只打开独立临时目录中的 bare Git 仓库。临时仓库通过 Git `objects/info/alternates` 只读复用正式仓库已有对象，因此不需要先复制一遍本地历史：

```text
主进程
  └─ 启动 fetch worker
       └─ 临时 bare 仓库 ──网络──> 候选代码源

worker 正常退出
  └─ 主进程从临时 bare 仓库本地 fetch 到正式仓库

worker 超时
  └─ 主进程终止 worker，清理临时目录，尝试下一个候选源
```

这样即使 libgit2 在首次进度回调之前不返回，主进程也能按硬时限终止 worker；被终止的原生调用不会直接持有正式仓库或 linked worktree。主进程对单个候选源同时执行三层监控：worker 启动后 10 秒内必须收到首条消息；收到消息后连续 30 秒没有新消息则终止；无论消息是否持续产生，单个 worker 总运行时间最多 120 秒。只有 worker 正常完成并退出后，主进程才会把目标分支导入正式仓库。导入完成后，临时 remote 会被删除。

worker 内部的 `server_connect_timeout` 和 `server_timeout` 使用 30 秒，回调累计超时使用 120 秒。它们只是 libgit2 的尽力而为保护，不能替代主进程的进程级硬时限；进程级时限不是整个候选源链的总时限。超时后只清理临时仓库，不对正式仓库执行恢复、重置或删除操作；候选链结束时仍按既有逻辑恢复主仓库 remote。

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

Windows 的 `multiprocessing` 使用 `spawn` 启动子进程。子进程会重新启动当前 Python 程序，再由 multiprocessing 内部参数切换到 worker 逻辑。PyInstaller 冻结后的程序也必须能识别这种 worker 启动，而不能再次执行完整的 GUI 或启动器流程。

因此，公共启动器基类在进入参数解析前统一调用：

```python
class LauncherBase:
    def run(self) -> None:
        multiprocessing.freeze_support()
        self.setup_parser()
        self.main(self.args)
```

它的作用只是处理 PyInstaller/Windows multiprocessing 的 worker 启动兼容性：

- 不创建子进程；
- 不设置超时时间；
- 不负责终止 worker；
- 不负责代码源回退；
- 在普通源码运行中通常没有实际动作。

## 回退边界

当前硬时限只针对单个候选代码源的一次 fetch。一个源超时或失败后，主进程才能继续尝试下一个源；所有候选源的总耗时可能是多个单源时限之和。正常 fetch 的对象导入、分支更新和工作区同步仍在主进程的既有流程中完成。
