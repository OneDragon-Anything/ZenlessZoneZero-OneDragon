# pygit2 fetch 可观测数据

本文说明 OneDragon 当前使用的 pygit2/libgit2 在执行 `Remote.fetch()` 时，能够向调用方提供哪些数据，以及这些数据分别代表 fetch 的哪个阶段。

## 适用版本

本文基于项目当前运行环境：

- pygit2 1.19.0
- libgit2 1.9.1

版本升级后需要重新核对回调绑定和字段语义。

## 结论

一次 fetch 可观察到的数据分为五类：

1. 远端文本：`sideband_progress(string)`；
2. 下载与索引统计：`transfer_progress(stats)`；
3. 本地引用更新：`update_tips(refname, old, new)`；
4. 按需发生的认证与证书检查；
5. `Remote.fetch()` 成功返回后的最终 `TransferProgress`。

其中：

- `Enumerating objects`、`Counting objects`、`Compressing objects` 和 `Total` 是远端发送的文本；
- Git 命令行中的 `Receiving objects` 不是远端文本，而是客户端根据传输统计生成的显示；
- pygit2 不提供独立的 `Receiving objects` 文本，也不提供布尔类型的 `done` 字段；
- `received_objects == total_objects` 只表示 pack 对象接收完成，不表示整个 fetch 完成；
- 判断整个 fetch 成功完成的可靠边界是 `Remote.fetch()` 正常返回。

## fetch 的可观察顺序

典型顺序如下：

```text
连接远端
  ↓
认证 / 证书检查（按需）
  ↓
远端准备 pack
  ├─ sideband: Enumerating objects
  ├─ sideband: Counting objects
  └─ sideband: Compressing objects
  ↓
下载并索引 pack
  └─ transfer_progress: TransferProgress
  ↓
远端可发送 Total 文本
  ↓
本地继续校验 pack、修复 thin pack、解析 delta、写索引
  └─ transfer_progress: TransferProgress
  ↓
更新本地引用
  └─ update_tips
  ↓
Remote.fetch() 返回最终 TransferProgress
```

各阶段不保证一一出现。例如仓库已经是最新时，可能没有新 pack、没有传输进度，也没有引用更新。

## `sideband_progress`：远端文本

签名：

```python
def sideband_progress(self, string: str) -> None:
    ...
```

它接收远端通过 Git progress side-band 发送的文本块。常见内容包括：

```text
Enumerating objects: 3843, done.
Counting objects: 50% (1922/3843)\r
Counting objects: 100% (3843/3843), done.\n
Compressing objects: 50% (1652/3279)\r
Compressing objects: 100% (3279/3279), done.\n
Total 3843 (delta 794), reused 3078 (delta 517), pack-reused 0 (from 0)\n
```

这些文本描述的是远端准备和发送 pack 的过程：

| 远端文本 | 含义 |
|---|---|
| `Enumerating objects` | 远端枚举本次可能需要发送的对象。 |
| `Counting objects` | 远端统计要放入 pack 的对象。 |
| `Compressing objects` | 远端压缩准备发送的对象。 |
| `Total ...` | 远端报告本次 pack 的汇总信息。 |

### 文本边界

`string` 是文本块，不应当被当作稳定的状态事件：

- 可能以 `\r` 结尾，表示同一行刷新；
- 可能以 `\n` 结尾，表示一行结束；
- 也可能没有行尾字符；
- 接口不承诺每次回调一定对应完整的一行，调用方需要允许拆分或拼接。

CNB 实测中大部分进度恰好是一条回调对应一行，但这只是本次服务端和传输实现的表现，不是接口保证。

### `done` 的边界

sideband 中的 `done` 是远端文本的一部分，不是 pygit2 提供的结构化字段。例如：

```text
Compressing objects: 100% (...), done.
```

只说明远端压缩阶段结束，不能证明：

- pack 已全部下载；
- delta 已全部解析；
- 本地索引已写完；
- 引用已更新；
- `Remote.fetch()` 已返回。

因此不能用 sideband 中是否出现 `done` 判断整个 fetch 是否成功完成。

## `transfer_progress`：下载与索引统计

签名：

```python
def transfer_progress(self, stats: TransferProgress) -> None:
    ...
```

pygit2 1.19.0 的 `TransferProgress` 提供七个字段：

| 字段 | 含义 | 使用注意 |
|---|---|---|
| `total_objects` | 当前 pack 中的对象总数。 | 读取 pack 信息后才能确定；无新 pack 时可能为 0。 |
| `received_objects` | 已从远端接收的对象数。 | 可用于生成客户端的“拉取对象/Receiving objects”进度。 |
| `indexed_objects` | 已完成哈希和索引处理的对象数。 | 可能落后于 `received_objects`，尤其是在解析 delta 时。 |
| `local_objects` | 为修复 thin pack 而注入的本地对象数。 | 这些对象不是本次从远端下载的。 |
| `total_deltas` | pack 中 delta 对象总数。 | 传输早期可能仍为 0，完成接收后才确定。 |
| `indexed_deltas` | 已完成索引的 delta 数。 | 可用于观察接收完成后的 delta 解析进度。 |
| `received_bytes` | 当前已接收的 pack 字节数。 | 不应当视为远端仓库总大小。 |

### 可以推导的阶段

接收对象阶段：

```python
stats.total_objects > 0
and stats.received_objects >= stats.total_objects
```

这表示所有 pack 对象已经收到，可以用于显示客户端阶段完成，例如模仿 Git CLI：

```text
Receiving objects: 100% (...), done.
```

但这里的 `done` 是客户端根据计数推导出来的“接收阶段完成”，不是远端传来的字段，也不是整个 fetch 完成。

索引阶段：

```python
stats.total_objects > 0
and stats.indexed_objects >= stats.total_objects
```

如果同时满足：

```python
stats.indexed_deltas >= stats.total_deltas
```

可以认为本次 pack 的对象和 delta 已完成索引。之后仍可能发生引用更新，因此仍不能代替 `Remote.fetch()` 的成功返回。

### 为什么不能只看 `received_objects`

实测中出现过以下状态：

```text
received_objects = 3843 / 3843
indexed_objects  = 3049 / 3843
total_deltas     = 0
indexed_deltas   = 0
```

此时网络接收已经达到 100%，但本地仍有 794 个 delta 尚未完成解析和索引。之后统计才变为：

```text
received_objects = 3843 / 3843
indexed_objects  = 3843 / 3843
total_deltas     = 794
indexed_deltas   = 794
```

所以“拉取对象 100%”只能表示接收完成，不能表示 fetch 完成。

## `update_tips`：本地引用更新

签名：

```python
def update_tips(self, refname: str, old: Oid, new: Oid) -> None:
    ...
```

参数含义：

| 参数 | 含义 |
|---|---|
| `refname` | 被更新的本地引用名称。 |
| `old` | 更新前的 OID。 |
| `new` | 更新后的 OID。 |

常见情况：

| 操作 | `old` | `new` |
|---|---|---|
| 创建引用 | 全零 OID | 新目标 OID |
| 更新引用 | 旧目标 OID | 新目标 OID |
| prune 删除引用 | 旧目标 OID | 全零 OID |

引用没有变化时通常不会触发回调，因此不能把 `update_tips` 当作每次 fetch 都会出现的结束事件。

OneDragon 的临时 bare fetch 实测会依次看到：

```text
refs/heads/main
refs/remotes/origin/main
```

具体引用取决于 remote 配置和 refspec，不能写死为这两个名称。

## 认证与证书数据

pygit2 1.19.0 在 fetch 选项中还绑定了以下回调。

### `credentials`

```python
def credentials(
    self,
    url: str,
    username_from_url: str | None,
    allowed_types: CredentialType,
):
    ...
```

只在远端要求认证时调用，提供：

- 当前认证 URL；
- URL 中的用户名；
- libgit2 当前允许的凭据类型位掩码。

公开 CNB HTTPS 仓库实测没有触发该回调。

### `certificate_check`

```python
def certificate_check(
    self,
    certificate: None,
    valid: bool,
    host: bytes,
) -> bool:
    ...
```

提供：

- `certificate`：pygit2 1.19.0 中固定为 `None`；
- `valid`：底层 TLS/SSH 验证结果；
- `host`：目标主机名，类型为 `bytes`。

同一次 fetch 可能多次触发证书检查。CNB 实测中对 `cnb.cool` 触发了三次，均为有效证书；次数不是稳定契约。

## `Remote.fetch()` 返回值

签名：

```python
result = remote.fetch(...)
```

成功时返回最终 `TransferProgress`。pygit2 的实现是在 `git_remote_fetch()` 成功结束后读取 `git_remote_stats()`：

```text
git_remote_fetch 正常返回
  ↓
读取 git_remote_stats
  ↓
构造并返回 TransferProgress
```

因此：

```text
Remote.fetch() 正常返回
```

是调用方能够观察到的、证明本次 fetch 已完成的可靠边界。它包含下载、pack 索引和引用更新；如果启用了 prune，也包含对应处理。

失败时 `Remote.fetch()` 抛出异常，不返回最终统计对象。

## 回调异常与中止

pygit2 回调不能直接跨 C 边界抛出异常。其处理方式是：

1. 保存 Python 回调抛出的异常；
2. 向 libgit2 返回 `GIT_EUSER`；
3. libgit2 调用退出后，由 pygit2 重新抛出原始 Python 异常。

因此项目在 `transfer_progress`、`sideband_progress` 或 `update_tips` 中抛出 `TimeoutError` 时，外层 `Remote.fetch()` 最终会重新抛出该 `TimeoutError`。

这只能在 libgit2 实际进入回调时生效。如果原生调用阻塞且长期没有触发任何回调，回调中的超时检查也不会执行。

## pygit2 没有提供的数据

当前版本组合没有向 Python 暴露以下 fetch 数据：

- 独立的 `Receiving objects` 原始文本；
- 结构化 `done` 字段；
- 稳定的整体百分比；
- 每个 fetch 必定触发的完成回调；
- fetch 总剩余时间；
- 当前网络瞬时速度；
- 远端仓库完整大小；
- 服务端 Counting/Compressing 与本地 Receiving/Indexing 之间的统一阶段编号。

libgit2 的回调结构虽然存在 `completion` 字段，但 1.9.1 头文件明确标记为“currently unused”，pygit2 1.19.0 也没有把它绑定到 Python 回调。

## CNB depth=1 实测

测试地址：

```text
https://cnb.cool/OneDragon-Anything/ZenlessZoneZero-OneDragon
```

测试条件：

- 分支：`main`；
- 深度：`depth=1`；
- 独立 bare 仓库：`.install/git_fetch_tmp/fetch_probe_*`；
- 不经过 OneDragon 的拆行、汉化和限流逻辑，直接记录 pygit2 原始回调；
- 测试结束后清理临时仓库。

连续三次采样中，远端对象数量相同，但 sideband 回调数量和文本块边界并不相同：

| 数据 | 结果 |
|---|---:|
| sideband 回调 | 148～204 次 |
| 以 `\r` 结尾 | 125～199 次 |
| 以 `\n` 结尾 | 4 次 |
| 无行尾字符 | 1～19 次 |
| transfer 回调 | 4781 次 |
| `total_objects` | 3843 |
| `total_deltas` | 794 |
| `received_bytes` | 约 18.65 MB |
| `local_objects` | 0 |
| 引用更新 | 2 次 |
| 凭据回调 | 0 次 |
| 证书检查 | 3 次 |

同一仓库、同一分支和同一 depth 下，sideband 文本块数量仍会变化，这进一步说明不能依赖回调次数或单次回调边界解析状态。

关键时序如下，时间只用于说明先后关系，不代表固定性能：

| 相对时间 | 事件 |
|---:|---|
| 0.343 秒 | 远端发送 `Compressing objects: 100%, done.` |
| 0.640 秒 | 远端发送 `Total ...`；本地 `received_objects` 达到 3843，但 `indexed_objects` 只有 3049。 |
| 0.640 秒后 | `total_deltas` 确定为 794，本地继续解析和索引 delta。 |
| 0.656 秒 | `indexed_objects=3843`、`indexed_deltas=794`。 |
| 0.656 秒 | 更新 `refs/heads/main`。 |
| 0.672 秒 | 更新 `refs/remotes/origin/main`。 |
| 0.672 秒 | `Remote.fetch()` 返回最终统计。 |

这次实测直接证明：

- `Compressing ... done` 早于对象接收完成；
- 远端 `Total` 不表示本地索引完成；
- `received_objects == total_objects` 后仍可能继续解析大量 delta；
- `update_tips` 发生在索引完成后、`Remote.fetch()` 返回前；
- 整个 fetch 完成应以 `Remote.fetch()` 正常返回为准。

## OneDragon 展示方案

按数据来源分别处理，避免混用语义：

| 展示内容 | 数据来源 | 实现规则 |
|---|---|---|
| 枚举对象 | `sideband_progress` 的 `Enumerating objects` | 只替换文本前缀，保留远端数量和 `done`。 |
| 统计对象 | `sideband_progress` 的 `Counting objects` | 只替换文本前缀，保留远端百分比、数量和 `done`。 |
| 压缩对象 | `sideband_progress` 的 `Compressing objects` | 只替换文本前缀，保留远端百分比、数量和 `done`。 |
| 拉取对象 | `received_objects / total_objects` | 客户端生成进度；达到 100% 时追加 `done`，只表示对象接收完成。 |
| 处理增量 | `indexed_deltas / total_deltas` | 仅在 `total_deltas > 0` 且对象已接收完成时显示；达到 100% 时追加 `done`。 |
| 更新引用 | `update_tips` | 原样显示实际引用名称。 |
| fetch 完成 | `Remote.fetch()` 正常返回 | 作为整个 fetch 成功完成的唯一边界，不使用前述阶段的 `done` 代替。 |

`sideband_progress` 按文本流处理：跨回调缓存残片，遇到 `\r` 或 `\n` 才输出完整消息。`Remote.fetch()` 正常返回后冲刷剩余文本；异常时放弃未完成残片。`update_tips` 在输出引用更新前冲刷缓冲区，以保持远程尾消息在引用更新前。终端入口保持既有规则：消息含 `%` 且不含 `done` 时使用 `\r` 刷新；同时含 `%` 和 `done` 时正常换行。

“拉取对象”和“处理增量”的 `done` 都由客户端根据计数生成，不是远端提供。它们分别只表示对象接收阶段和 delta 处理阶段完成，不能据此判断引用更新或整个 fetch 已成功。

## 资料来源

- [pygit2 1.19.0 `Remote.fetch` 与 `TransferProgress`](https://github.com/libgit2/pygit2/blob/v1.19.0/pygit2/remotes.py)
- [pygit2 1.19.0 `RemoteCallbacks` 与 fetch 回调绑定](https://github.com/libgit2/pygit2/blob/v1.19.0/pygit2/callbacks.py)
- [libgit2 1.9.1 `git_indexer_progress`](https://github.com/libgit2/libgit2/blob/v1.9.1/include/git2/indexer.h)
- [libgit2 1.9.1 remote 回调定义](https://github.com/libgit2/libgit2/blob/v1.9.1/include/git2/remote.h)
- [pygit2 clone progress 示例](https://github.com/libgit2/pygit2/blob/v1.19.0/docs/recipes/git-clone-progress.md)
