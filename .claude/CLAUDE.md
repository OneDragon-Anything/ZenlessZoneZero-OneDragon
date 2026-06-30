# CLAUDE.md

@../AGENTS.md

## 临时文件

运行时产生的临时文件，统一放项目根 `.debug/temp/`（`.debug/` 已 gitignore）。

## 知识维护：边干边补

人机知识对齐靠持续维护（[harness 核心准则](../docs/develop/harness/README.md)、[分层与判据](../docs/develop/harness/context_layering.md)）。**凡是文档没写、或与实际矛盾、而你在干活时又需要它——这就是知识缺口，要补上**：

- **能确定答案的 → 提议补进文档**（只补会重复用到的，一次性细节不补）。
- **确定不了的 → 问用户**（缺关键知识且无法安全推断时，别瞎猜）。
- **放哪**：个人偏好 → `CLAUDE.local.md`（或 auto-memory）；项目/工具特有 → 对应 `docs/`；跨工具通用 → `AGENTS.md`（详见 [ai_coding.md](../docs/develop/setup/ai_coding.md)）。
- **共享文档先确认**：`AGENTS.md`、`docs/` 是团队共享的，改动先经用户确认，不静默重写；个人记忆可自行更新。
