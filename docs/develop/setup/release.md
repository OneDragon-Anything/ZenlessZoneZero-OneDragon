# 发版流程

> 发版统一手动触发，**不要先推 tag**：tag 由 Release 步骤和产物一起创建，避免出现 tag 已经可见、安装包还没上传的空窗。

## 触发方式

GitHub Actions 里手动运行 `Build and Release`：

| 输入 | 说明 |
|---|---|
| `create_release` | 勾选才创建 Release、签名和上传产物；不勾选只做构建检查 |
| `version` | 可选。留空时在最新 tag 上自动递增 beta（如 `v2.5.2-beta.3` → `v2.5.2-beta.4`）；正式版填 `v2.6.0` |

`push tag` 不再触发发版。已经在 tag 上时，仍可手动运行本工作流做补发（此时复用该 tag，不再检查 tag 是否存在；手填的 `version` 会被忽略）。

## 流程

1. `version` 作业算出版本号（`tools/ci/get_version.py`），只输出，不推 tag。
2. `build` 作业构建安装器、启动器、集成启动器和依赖包。
3. `sign` 作业提交 SignPath 签名。
4. `release` 作业先确认远端还没有同名 tag，再用 `softprops/action-gh-release` 创建 Release：`tag_name` 为版本号、`target_commitish` 为本次构建的 commit，产物随同一次请求上传，tag 在这一步才出现。作业使用固定的 concurrency 组串行，两次发版不会同时跑。
5. Release 创建后由 `release` 作业显式 `workflow_dispatch` 触发 `.github/workflows/sync-cnb.yml` 把 tag 镜像到 CNB（`GITHUB_TOKEN` 创建的 tag 不会触发 `push` / `release` 事件，不能指望事件）；末步再触发 CNB 的 `api_trigger_release` 同步 Release 附件。

## 版本号规则

- 正式版：`vX.Y.Z`
- 预发布：`vX.Y.Z-beta.N`，Release 会自动标为 prerelease
- 自动递增只看远端 tag，tag 不存在就导入 `v0.1.0-beta.1`
- 手填版本号必须是上面两种格式之一；分支发版时如果同名 tag 已存在会直接失败，换版本号或删掉旧 tag 再来

## 失败处理

- 构建或签名失败：不会产生 tag 和 Release，直接修完重跑。
- Release 已创建但附件缺失：重跑工作流，或者用 `gh release upload` 补传。
- 只想重建产物、不发版：把 `create_release` 留空（不勾），构建产物以 Actions artifact 的形式保留。