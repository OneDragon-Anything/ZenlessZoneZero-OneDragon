---
name: zzz-od-dev-pr-finishing
description: 当用户要把已开的 PR 推到「完善可合并」、处理 PR/CodeRabbit review、清 unresolved thread、问 PR 能不能 merge / checks 状态时用。英文:finish/get a PR mergeable、address review comments、PR not merging、CI red、unresolved threads。仅 PR 已开后的收尾;单条评论处理用 superpowers:receiving-code-review。
---

# PR 收尾(跑到完善可合并)

把一个**已开的 PR** 推到「完善、可合并」状态。

## done criteria(全满足才算收尾)

1. **CI checks**:required 全 pass;**条件触发类 check 的 `skipping` 不算失败**(如打包/签名/发布类 check,PR 上不触发属正常)—— 只看 required 是否绿。
2. **自动化 review 完成且无新建议**:CodeRabbit 这轮 review 跑完。⚠️ **增量 review 无新建议时,它不建 check run、也不留 review 记录** —— 完成态靠它回复的 issue comment(对 `@coderabbitai review` / 自动 review 的 ack,body `<details>` 里 `✅ Action performed` → `Review finished`)确认,结合 0 unresolved。别因 `reviews` 没新记录 / 没 check run 就以为没 review(见流程 1)。
3. **讨论区无 unresolved thread**:每条都处理过(每条最终都要 resolve,不留 —— 见流程 2)。
4. **关联 PR(跨仓)也都 done**:跨仓同分支的关联 PR(如测试仓 PR)也按本 skill 收尾全清;**都 done 才合**(见流程 6)。

## 流程

### 1. 摸现状
- checks:`gh pr checks <PR>`(或 `gh api repos/<owner>/<repo>/commits/<sha>/check-runs --jq '.check_runs[]|{name,status,conclusion}'`)
- unresolved thread(GraphQL,owner/repo/PR 号替换为实际值;`databaseId` 是回复用的 REST id):
  ```
  gh api graphql -f query='query{repository(owner:"O",name:"R"){pullRequest(number:N){reviewThreads(first:50){nodes{id isResolved path line comments(first:1){nodes{databaseId body}}}}}}}' \
    --jq '.data.repository.pullRequest.reviewThreads.nodes[]|select(.isResolved==false)'
  ```
- 合并:`gh pr view <PR> --json mergeable,mergeStateStatus`
- **CodeRabbit review 已触发?**:push 后不自动触发的**真因**常是 PR 被 **auto-pause**(活跃开发 / 频繁 commit 触发 `auto_pause`,暂停后每次 push 都不自动)。先查暂停:`gh pr view <PR> --json comments --jq '.comments[]|select(.body|test("Reviews paused"))'`(命中 = 已暂停)。暂停下两命令语义不同:
  - `@coderabbitai review` = **单次**触发(保持暂停,下次 push 仍不自动):`gh pr comment <PR> --body "@coderabbitai review"`。
  - `@coderabbitai resume` = **恢复**自动(之后 push 自动触发);不想每轮手动补就用这个。
  - 全量重审整个 PR:`@coderabbitai full review`。
  若**未暂停**却没自动触发(罕见,如 check run 未建、或 `gh pr checks` 里那条 `Review completed` 是**旧 commit** 的),才走手动 `review` 兜底。**确保有 review**:done criteria 要求 review 完成,别空等。
- **review 完成了吗?**(增量无建议时 API 无痕):查 CodeRabbit 最近的 ack issue comment —— `gh pr view <PR> --json comments --jq '.comments | map(select(.author.login=="coderabbitai")) | last | .body'`,body 含 `Review finished`(在 `✅ Action performed` 的 `<details>` 里)即这轮完成。⚠️ 若 body 是 `Review triggered` —— review 还在进行,**别当完成**:CodeRabbit 完成后会**编辑同一条** comment 为 `Review finished`(不另发新 comment),等几分钟再查。
- ⚠️ **outside-diff comment(GitHub 平台限制)**:GitHub 不允许在 diff 外的行 post inline review comment,CodeRabbit 把这类 comment 放在 **review body 的「Outside diff range comments」折叠 `<details>`** 里 —— **不在 reviewThreads、不计入 unresolved**,易漏。摸现状时也要展开 review body 折叠区看,逐条处理(走流程 2,但它无法 reply 到行,用 issue comment 回复)。
- ⚠️ **rate limit(per-developer 配额)**:push 不自动 review 且 issue comment 含「Review limit reached」+「Next review available in <时长>」—— 配额达,这轮**不 review**(只 post warning)。查:`gh pr view <PR> --json comments --jq '.comments[]|select(.body|test("Review limit reached"))'`。等指定时长后 `@coderabbitai review` 重试;频繁触发考虑开 usage-based 或暂停增量 auto-review。**和 auto-pause 区别**:rate limit 是**组织级 per-developer 配额**(等时间恢复);auto-pause 是**频繁 commit 暂停**(`resume` 恢复)。

> ⏰ **时区**:GitHub API 返回的时间是 UTC(`Z` 后缀),显示给用户前转本地(维护者 UTC+8 → +8 小时,如 `03:46Z` → `11:46`),别直接甩 UTC 串让人困惑。

### 2. 清 unresolved(逐条,每条最终都要 resolve)
对每条 thread,**按 superpowers:receiving-code-review 的方法**(verify → 评估 → 决定);本 skill 不重复单条方法论。两条出路,**都回复 + 都 resolve,不留 unresolved**:
- **接受** → 改码 → 回复 `Fixed in <hash>`
- **不改**(不同意 / 不该改 / 暂不在这轮)→ **push back**,回复说明理由(如「不改,因为 X」「暂不动,后续 Y」)
- 回复走原 thread:`gh api repos/<owner>/<repo>/pulls/<pr>/comments/<comment_id>/replies`
  - **comment_id 用第 1 步 query 取到的 `databaseId`(REST 数字)**,**不是** GraphQL 的 `PRRT_` thread id,别混(混了 404)。端点必须带 `pull_number`:`pulls/<pr>/comments/<id>/replies`。

### 3. resolve(时机判据)
resolve 前确保 CodeRabbit 对这条「说完话了」,不抢它的判断、也不干等(**回复本身不会立即触发 auto-resolve**):
- **本次有 push**(改码 push 了):等**下一轮 CodeRabbit review 完成** + 它对这条**没提新建议** + **没新回复** → 才能 resolve。
- **本次没 push**(只回复):等 **10 分钟** + **没新回复** → 才能 resolve。

满足后手动 resolve(GraphQL,REST 没有、gh 无内置):
  ```
  gh api graphql -f query='mutation{resolveReviewThread(input:{threadId:"PRRT_xxx"}){thread{isResolved}}}'
  ```
  thread id(`PRRT_xxx`)从第 1 步 reviewThreads query 拿;反操作 `unresolveReviewThread`。

### 4. push → 迭代
每次 push 触发 review 重审 + CI 重跑,**可能新提 comment**。重复 1-3,直到「review 完成 + 无 unresolved + checks 绿」稳定。若连续 2 轮仍冒新 comment 或无法收敛 → 停下来问人,别死循环。

### 5. 合并前
`mergeable` 要 `MERGEABLE`、非 `DIRTY`;dirty → rebase 到目标分支。是否 merge / 合并方式不在本 skill 范围(见 superpowers:finishing-a-development-branch)。

**合并后清理(提示,不主动)**:PR 合并后,可**提示**用户删除该 PR 的本地 + remote 分支(`git branch -d <branch>` + `git push origin --delete <branch>`)。只提示,**不主动执行**——分支可能还在用(回看 / cherry-pick)、或用户想保留,由用户确认时机。`gh pr merge --delete-branch` 会同时删 remote + 本地,但只删当前 PR 的;之前遗留的分支要手动清。

### 6. 关联 PR(跨仓)协同
本项目跨仓:主仓 PR 常带配套**测试仓 PR**(同分支名,主仓描述带测试仓 PR 链接)。
- **一起收尾**:关联 PR 都按本 skill 走(CI/review/unresolved 全清),不只当前 PR。
- **合并顺序:测试仓先 → 主仓后**。主仓合到 main 后,main 的 `test-check` clone 测试仓 **main**;测试仓先合确保测试改动进测试仓 main,主仓 main CI 才稳(主仓先合 → 主仓 main CI clone 测试仓 main 无新改动 → 测试缺失/失败)。
- **都 done 才合**:关联 PR 全 green + review pass + 无 unresolved 后,按顺序合(测试仓 → 主仓)。

## 边界(不做什么)
- 单条 review 怎么 verify/回复/push back → superpowers:receiving-code-review
- 实现完成后要不要 merge/开 PR/discard → superpowers:finishing-a-development-branch
- 本 skill 只管「PR 已开后 → 完善可合并」
