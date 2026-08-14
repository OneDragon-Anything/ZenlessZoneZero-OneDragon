# zzz-od-dev-pr-finishing 设计说明

## 为什么做这个 skill

「把 PR 跑到完善可合并」是高频且步骤固定的工作,但散落多处知识:done criteria、CodeRabbit 行为、resolve 工具操作、命令清单。不固化每次都要重新摸索(实操踩过 replies 漏 pull_number、line 字段为 null、comment_id 与 thread id 体系不同等坑)。

**为什么是 skill 而非 docs**:skill 在触发时由智能体自动注入执行上下文(主动),docs 要人或智能体记得去翻(被动);这类「每次收尾 PR 都要按它走」的流程,skill 的主动注入比 docs 的被动参考更可靠。

## 定位(边界)

| skill | 管什么 |
|---|---|
| superpowers:receiving-code-review | 单条 review 评论怎么 verify / 回复 / push back(通用方法论) |
| superpowers:finishing-a-development-branch | 实现完成后选 merge / PR / keep / discard |
| **zzz-od-dev-pr-finishing(本 skill)** | PR 已开后,把它跑到「完善可合并」(checks + review + resolve + 迭代) |

横向引用,不重复:单条评论处理 → superpowers:receiving-code-review;merge 决策 → superpowers:finishing-a-development-branch。与 receiving-code-review 重叠约 1/3(单条处理),不冲突,互补(它横向单条,本 skill 纵向整 PR)。

## 关键决策

1. **resolve 走 GraphQL**:GitHub REST 无 resolve endpoint,只能 `resolveReviewThread` mutation;gh CLI 无内置命令,用 `gh api graphql`。
2. **comment_id 用 REST 数字**(从 `pulls/<pr>/comments` 拉),**不是** GraphQL 的 `PRRT_` thread id —— replies 端点 id 体系不同,混用 404;端点必须带 pull_number。
3. **条件触发类 check 的 skipping ≠ fail**:打包/签名/发布类 check 在 PR 上常不触发(skipping),只看 required 是否绿;别把 skipping 当失败。
4. **CodeRabbit 写死(非抽象)**:CodeRabbit 是团队各项目统一采用的 review bot(非偶然选择),故 skill 直接以其为前提。若团队改用其它 review bot,「review 完成态」「auto-resolve 行为」等表述需同步调整。
5. **resolve 时机(区分有无 push)**:回复本身不立即触发 auto-resolve。有 push → 等下一轮 CodeRabbit review 完成 + 它对这条没提新建议 + 没新回复;没 push → 等 10 分钟没新回复。确保 CodeRabbit「说完话」再 resolve,不抢判断也不干等(实战验证:纯回复不 push 时等不到 auto-resolve)。
6. **迭代性**:每次 push 触发重审 + CI 重跑,可能新提 comment;重复 triage 直到稳定,连续不收敛则停下问人。
7. **每条都 resolve(不设暂缓类)**:不改的也 push back 说明理由 + resolve;done criteria「无 unresolved」严格满足,不在 PR 上留 unresolved 的暂缓项(要后续追踪的另开 issue,不在本 skill 范围)。
8. **push 后不自动触发 = 被 auto-pause(非偶发)**:CodeRabbit 有 `reviews.auto_review.auto_pause_after_reviewed_commits` 机制 —— PR 活跃开发 / 频繁 commit 时**自动暂停** review,之后**每次 push 都不自动触发**(不是偶尔)。检测:PR 有 `Reviews paused` comment(grep body 含 `Reviews paused` / `review paused`)。暂停下两命令语义不同:`@coderabbitai review` = **单次**触发(保持暂停,下次 push 仍不自动);`@coderabbitai resume` = **恢复**自动(之后 push 自动触发,ack `Reviews resumed.`)。ack 里那句「此命令仅在自动 review 暂停时适用」就是在提示当前处于暂停态。预防:调 `.coderabbit.yaml` 的 `auto_pause_after_reviewed_commits` 阈值 / 关闭。实战:PR 2419 从 7-01 起被 auto-pause,故每轮 push 都要手动补 —— 曾误判为「偶尔不触发」,实际是**始终暂停**。
9. **增量 review 无建议时 API 无痕**:增量 review 没新建议时,CodeRabbit 不建 check run、不留 review 记录,只回复一条 issue comment(`✅ Action performed` / `Review finished`)。故「review 完成」的可靠判据是这条 ack comment 的 body,不是 check run / reviews(实战:PR 2419 增量 review 完成但 API reviews 停在上一天、该 commit 无 CodeRabbit check run)。**手动 @ 后 ack 的演变**:ack comment 先回 `Review triggered`(review 进行中),真正完成后 CodeRabbit **编辑同一条** comment 为 `Review finished`(不另发新 comment)。`triggered` 是中间态 —— 判完成必须看到 `finished`,别把 `triggered` 当结果(实战:PR 2419 bf2ebfea 手动 @ 后 06:38Z 回 triggered,review 完成后同条被编辑成 finished)。
10. **时区**:GitHub API 时间是 UTC(`Z` 后缀),显示给用户前转本地(维护者 UTC+8);避免时间串造成困惑。
11. **关联 PR 用 git 验证,不只查 open PR**:`gh pr list --repo OneDragon-Anything/zzz-od-test --head <分支>` 查 open PR 为空 ≠ 无配套 —— 测试仓改动可能挂在同分支但没开 PR(有改动但没开 PR)。收尾主仓前必须 `git -C zzz-od-test fetch origin && git -C zzz-od-test log origin/main..origin/<同名分支>` 验证无未合改动。**为什么不用 open PR 判**:PR #2608 收尾时查测试仓同分支 open PR 为空就判"无配套"、直接合了主仓,事后才发现测试仓分支有 11 个未合 commit(有改动、没开 PR)→ 补救才开测试仓 #35。根因:open PR 是「是否已开 PR」的判据,不是「是否有配套改动」的判据;后者要看 git 分支。该方法进 SKILL.md §6;配套的预防约束(开发阶段就同开关联 PR)进 AGENTS.md「提交流程与协作边界」+ development_workflow.md §4(泛化到非游戏流程改动)。

12. **作者开 PR 写 desc 作 commit body,合并者 review(issue #2615)**:仓库 squash + merge commit 取整段 PR description 作 commit message(`*_title=PR_TITLE`、`*_message=PR_BODY`)。**方法论:作者开 PR 时写好 desc(why + 改动要点 + 关联)作 commit body;合并者 merge 前 review,好就 merge,不好微调**。写 desc 的规范在 AGENTS.md(作者,读者广),本 skill(收尾)只 review 不写。
    - **实测(本 PR verify-squash-body 验证)**:squash `PR_BODY` **取整段 PR desc**(含 `##` 标题、CodeRabbit summary),不截断到第一个 `##`。之前「## 截断」假设错。
    - **CodeRabbit summary 配置**:`.coderabbit.yaml` 设 `high_level_summary_in_walkthrough: true` 让 summary 放 comment(不进 PR desc/commit body);`high_level_summary_instructions` 用 Keep a Changelog 分类(Added/Changed/Deprecated/Removed/Fixed/Security)只写 what。why 由作者写(CR 读 diff 给不了 why)。
    - **本项目设置**:squash + merge commit 都 `*_title=PR_TITLE`、`*_message=PR_BODY`;查询 `gh api repos/<owner>/<repo> --jq '{squash_merge_commit_title, merge_commit_title, squash_merge_commit_message, merge_commit_message}'`(admin 可在 GitHub Settings 看,普通 contributor 看不到)。
    - **规范分层(决策 7)**:单个迭代 commit 宽松 / 需要 commit message 的 merge 严格 Conventional Commits(作者开 PR 写 desc),两层规范在 AGENTS.md;本 skill 收尾只 review。
    - **为什么不把写 desc 方法论写进本 skill**:写 desc 读者是所有开 PR 的 AI(不止收尾),规范进 AGENTS.md(单一源);本 skill 只放收尾 review 动作。
    - **不主动 merge**(用户明确要求时才执行):以 review / 提示为主(与 AGENTS.md「提交流程」一致)。

## 落点

- `skills/zzz-od-dev-pr-finishing/`(项目根,跨工具源 —— 即「多工具共享级」,多个 skills 感知工具都能用)。
- `zzz-od-dev-` 前缀:项目开发流程类 skill。
- junction 到 `.claude/skills/zzz-od-dev-pr-finishing`:Claude Code 扫 `.claude/skills/` 发现;Windows 用 junction(`mklink /J`)免管理员。

## skill vs 文档

skill 做流程骨架 + 触发;checklist / 命令清单直接内联在 SKILL.md(少跳转)。design.md 记设计决策。暂不单独开规范文档 —— skill 本身即规范,避免双源。

## 当前状态
团队已统一采用 superpowers,本 skill 已 unignore 并提交(目录名 `zzz-od-dev-pr-finishing`)。CodeRabbit 限定不阻塞(团队各项目统一采用 CodeRabbit)。
