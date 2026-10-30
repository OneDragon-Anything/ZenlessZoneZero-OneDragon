# settings.json 的团队级 vs 个人级归口

> 本文档回答一个具体问题:**`.claude/settings.json` 里哪些 key 该放团队级(commit、共享),哪些该放个人级(`.local.json` / `~/.claude/`)?**
>
> 调研日期:2026-06-30。依据:Anthropic 官方 [settings](https://code.claude.com/docs/en/settings) / [permissions](https://code.claude.com/docs/en/permissions) / [best-practices](https://code.claude.com/docs/en/best-practices)(原 `/engineering/claude-code-best-practices` 已合并至此)三份一手文档。
>
> 本文讲 **settings 文件归口**(一个 key 进哪个文件)。另一条正交轴——**上下文进哪一档**(always-on / 条件触发 / hook / permissions)——见 [context_layering.md](context_layering.md)。

## 一句话结论

**判据不是"喜欢放哪",而是三条自检**:① 这个 key 在 project/local scope **是否会被官方刻意忽略**(安全设计);② 是否含 **secret / 机器特定路径**;③ 是否**全员都该一致**。Claude Code 本身就按 scope 设计了团队/个人分档,顺着它走即可。

## 1. 官方四档 scope + 优先级

| Scope | 位置 | 影响谁 | 团队共享 |
|---|---|---|---|
| Managed | `managed-settings.json` / MDM / 服务端 | 全组织 / 全机 | ✅ IT 下发,**不可被覆盖** |
| User | `~/.claude/` | 你,跨所有项目 | ❌ |
| **Project** | `.claude/settings.json`(repo 内) | 所有协作者 | ✅ commit 进 git |
| **Local** | `.claude/settings.local.json` | 你,仅此 repo | ❌ 自动 gitignore(Claude 自建时;手建需自行加 gitignore) |

优先级(高→低):**Managed > CLI 参数 > Local > Project > User**。

> ⚠️ **`permissions` 规则是 merge,不是 override**:任一层 `deny` 即阻断,**没有任何层的 `allow` 能翻盘**——连 managed deny 也压不过 CLI。所以"团队 deny"会被个人继承且无法绕开;反之 user deny 也能 block project allow。

## 2. 各 key 归口表

| key | 团队级 `.claude/settings.json` | 个人级(local / `~/.claude`) | 说明 |
|---|---|---|---|
| `permissions.allow` / `deny` | ✅ 团队公用工具(`Bash(uv *)`、项目 MCP tool) | 个人临时允许 → local | 跨层 merge,deny 优先 |
| `permissions.defaultMode` | ⚠️ **`auto` 在 project/local 被忽略**(v2.1.142+) | `auto` 放 `~/.claude/` | repo 不能给自己开 auto |
| `hooks` | ✅ 团队统一流程(ruff、commit trailer) | 实验中 → local | 生命周期确定性脚本 |
| `env` | ✅ 全员都要的(`ENABLE_LSP_TOOL`)— **禁放明文 secret**,用 `${VAR}` | 含 secret / 个人 → local | |
| `enabledPlugins` | ✅ 团队应装的(context7、uv-pyright) | 偏好 → local/user | 仅"建议启用",实际安装仍需每个用户 trust marketplace |
| `extraKnownMarketplaces` | ✅ 团队私有 marketplace | | clone 后自动提示装 |
| **MCP servers(定义)** | ❌ **不进 settings.json** → 项目级进 `.mcp.json`(commit) | 含 secret / 本机端口 → `claude mcp add --scope local`(`~/.claude.json`) | 见 §3 坑 1 |
| `lspServers` | ✅ 团队统一 LSP 配置 | | |
| `additionalDirectories` | 🟡 路径全员一致才 commit | 多为机器特定 → local | 只授文件访问,**不**加载配置 |
| `enableArtifact` | ❌ project/local **被忽略**(v2.1.196+) | user / managed | |
| `skipDangerousModePermissionPrompt` | ❌ project 被忽略 | user / managed | 防 untrusted repo 自动绕过确认 |
| `autoMode` / `useAutoModeDuringPlan` | ❌ 不从 shared project settings 读 | user | |
| `footerLinksRegexes` / `sshConfigs` | ❌ 仅 user/managed 读 | user | |
| 主题 / `editorMode` / `outputStyle` 等偏好 | ❌ | ✅ user(`~/.claude/`) | 个人偏好 |
| 各类 `strict*` / `allow*Only` / `claudeMd` / `forceRemoteSettingsRefresh` | ❌ **managed-only** | managed settings 天花板 | project 写了静默无效 |

## 3. 四个坑

1. **MCP server 定义 ≠ MCP 权限**:`.mcp.json` 放 server **定义**(commit),`~/.claude.json` 放 user/local scope 的 server;settings.json 里的 `mcp__zzz_od` 只是"**允许调用**"的**权限规则**。两件事分开,server 定义塞进 settings.json 不生效。
2. **"repo 不能给自己授权"**:`defaultMode:auto`、`enableArtifact`、`skipDangerousModePermissionPrompt`、`autoMode` 等安全敏感 key 在 project/local **被官方刻意忽略**,只能 user/managed。防的是 clone 一个恶意 repo 就自动拿到高危模式。
3. **secret 进 committed settings.json = 泄露**:用 `env` 的 `${VAR}` 引用,或挪进 `.local.json` / `~/.claude.json`(这俩 gitignore)。
4. **managed-only 的天花板**:`claudeMd`、`forceRemoteSettingsRefresh`、各种 `strict*/allow*Only` 只认 managed settings,project 写了静默无效——别指望在 repo 里强制团队策略。

## 4. 本仓库现状对照

| 当前 `.claude/settings.json` 内容 | 判定 |
|---|---|
| `env.ENABLE_LSP_TOOL` | ✅ 团队级合理 |
| `allow: Bash(uv *)` + 3 个 `mcp__*` | ✅ 团队公用工具,合理(`mcp__*` 是权限规则) |
| `deny: Bash(python *)` / `python3 *` | ✅ 项目约定(强制走 uv),很适合团队级 |
| `enabledPlugins`: context7、uv-pyright | ✅ 团队建议(注意:实际安装需每个用户自己 trust) |
| `lspServers` | ✅ 团队统一,合理 |
| `additionalDirectories: []` | 空数组,无所谓 |

**整体归口正确**:没有把个人 / secret / 被忽略的 key 放错位置。zzz_od / zzz_od_daemon 的 server **定义**应落在 `.mcp.json`(commit)或 `~/.claude.json`(若含本机端口),当前 settings.json 里只有它们的权限规则,没塞定义——对的。

## 来源

- [Claude Code settings](https://code.claude.com/docs/en/settings)(scope 表 / 优先级 / key 参考 / managed-only 清单)
- [Configure permissions](https://code.claude.com/docs/en/permissions)(merge 规则 / managed 天花板)
- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices)(CLAUDE.md check-in / permissions allowlist 实践)
