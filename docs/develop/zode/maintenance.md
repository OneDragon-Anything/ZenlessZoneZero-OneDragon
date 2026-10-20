# ZODE 维护规则

ZODE（**Z**enless **O**ne **D**ragon **E**nhanced）是本 fork 的增强发行分支：集成社区精选 PR 与维护者增强功能，通过游戏内既有的代码更新机制分发给选择本通道的用户。

本文是 ZODE 的运行规则，维护会话（人工或 AI）必须遵守。对规则有异议，在本 fork 开 issue 讨论；规则的修改本身走本 fork 的 PR。

## 分支通道

| 分支 | 内容 | 同步方式 |
|---|---|---|
| `main` | 官方主分支（含 fork 自动化提交） | 合并官方 main |
| `mirror` | 官方最新镜像，零本地改动 | fast-forward 指向官方 main |
| `zode` | 增强：官方 main + 维护者增强 + 精选 PR 镜像 | 见下方「维护周期」 |

三个分支都通过设置页的「idk500 增强源」使用；`mirror` 与 `zode` 仅该源可用。

## 铁律

1. **只向本 fork 推送。** 不向上游仓库推送任何内容，不开 PR、不开 issue、不评论。
2. **merge-based，禁止改写历史。** 只做普通 merge 与普通 push，禁止 rebase、禁止 force push——用户的增量更新与更新去重都依赖「历史只增不改」。
3. **PR 以原始提交合入。** fetch 上游 `refs/pull/N/head` 后直接 merge，保留原作者姓名、邮箱与提交日期；禁止 squash、禁止 cherry-pick 改写身份。
4. **合并消息必须署名原作者**：`<PR原type>: 合入 PR #N <标题>（@<作者>）`。type 沿用 PR 自己的 conventional 前缀。
5. **每周期至多合入 1 个 PR**；校验不过不合入。

## 维护周期

1. fetch 官方 main，merge 进 zode（`--no-ff`，消息 `feat: 同步官方 main 至 <短id>`）；mirror 同步为官方 main 指针。
2. 从清单队列取队首 PR：fetch `refs/pull/N/head` 并把拿到的 SHA 记入清单（作者后续 force-push 不影响已 pin 的内容）；`git merge-tree --write-tree` 预检冲突，干净则合入；冲突记入 parked 并试队列下一个，连续 3 个冲突即停车。
3. 校验：本次触碰的 `.py` 过 py_compile / ruff，`.yml` 过 YAML 解析；不过则回退该 merge。
4. 推送 zode；更新清单并备份到 `zode-meta` 分支。

## 冲突分类

- **Class 1（自动推进）**：只有唯一合理答案的冲突——上游改名/搬移/删除后的功能重新挂载、import/语法修补、上游已有等价实现则弃我方。自动解决，记入清单 resolved 区。
- **Class 2（仲裁）**：多解冲突——两个 PR 用不同实现修同一问题、或与上游演进互斥且各有合理性。流程：
  1. 在**本 fork** 开 issue，标题「[仲裁] <主题>（PR #A vs #B/上游）」；
  2. 正文给出双方方案 diff 要点、影响面、中立分析与推荐及理由；
  3. @相关 PR 作者；候选方案各发一条评论，👍 计票，72 小时窗口；
  4. 多数票按票决；无票或平票则 fallback：先跟上游方向，其次采纳分析推荐；
  5. 结论在帖内说明后关闭，写入清单 arbited 区。

## 上游合并了已镜像的 PR 怎么办

无需处理。PR 的原始提交已在 zode 历史中；上游 squash 合并后，两边净变更一致，git merge 自动判干净——不冲突、不重复。只有上游用**别的改动**碰了同一代码段才是真实分歧，按上面的冲突分类处理。

## 贡献者须知

- 你的 PR 被合入 zode 时保留原始提交与完整作者信息，合并消息与首页「公告要闻」第一条都会标注你的 ID。
- 不希望自己的 PR 被本分支镜像？在本 fork 开 issue 说明，我们以 revert 对应合并提交的方式移除，不改写历史。
- 对某个仲裁结论有异议，直接在仲裁 issue 里参与讨论；新事实出现可重开。

## 清单与备份

`zode-manifest/manifest.yml`（仓库外维护，备份于 `zode-meta` 分支）记录：

- `baseline`：增强分支基线（来源与合入时间）
- `merged`：已镜像 PR（number / pin SHA / 标题 / 作者 / 日期）
- `queue`：候选队列
- `parked`：冲突挂起
- `excluded`：排除项及理由
- `resolved`：Class 1 自动解决记录
- `arbited`：Class 2 仲裁结论
