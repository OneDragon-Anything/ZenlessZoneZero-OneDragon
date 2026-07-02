# Claude Code：自动注入 commit trailer

> 这是 [ai_coding.md](../ai_coding.md) 里「AI 辅助提交的署名 → 做法二 → 2b（git hook + 工具 hook 写模型名）」在 Claude Code 上的具体实现。思路通用，下面是 Claude Code 的落地。

## 目标

每次 `git commit` 自动追加两行 `Co-Authored-By`：

- **工具一行**：`Claude Code <noreply@anthropic.com>`（固定，因为本项目只跑 Claude Code）；
- **模型一行**：`<当前模型> <厂商邮箱>`，模型一换跟着变（GLM→`bigmodel.cn`、DeepSeek→`deepseek.com`）。

不依赖模型记忆；链式 `&&`、`git -C <dir>`、`--amend` 全覆盖。

## 怎么工作

两个钩子 + 一处配置，各司其职：

1. **Claude Code hook（PreToolUse）** `commit_trailer.ps1`：每次 `git commit` 前，从会话 transcript 取当前模型，写到 `.debug/temp/.cc_model`。**不改命令**，只记模型。
2. **git hook** `prepare-commit-msg`：git 每次提交自动调它，读 `.cc_model` → 用 `git interpret-trailers` 追加两行 trailer。无模型记录（非 Claude Code 提交）则跳过；已有则幂等跳过。
3. **`attribution.commit=""`**：把 Claude Code 默认的 co-author 指令置空，避免和 git hook 撞车重复。

> 为什么用 git 钩子注入、而不是让 Claude Code hook 改写命令？git 钩子由 git **逐提交**调用，链式 `&&`、`git -C <dir>`、`--amend` 都自动覆盖，也不用解析命令文本（不会误伤提交消息里出现的 “git commit” 字样）。

## 脚本

### 1. Claude Code hook 配置（`.claude/settings.local.json`，节选）

```json
{
  "attribution": { "commit": "" },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "pwsh -NoProfile -ExecutionPolicy Bypass -File \"$CLAUDE_PROJECT_DIR/.claude/hooks/commit_trailer.ps1\""
          }
        ]
      }
    ]
  }
}
```

> 用 pwsh（PowerShell 7）。matcher 是 `Bash`，每条 bash 命令都触发 → 脚本内部再用 `git\s.*commit` 过滤，只在实际是 git commit 时才记模型（纯 pwsh，无 bash wrapper）。

### 2. Claude Code hook 脚本（`.claude/hooks/commit_trailer.ps1`）

```powershell
# commit_trailer.ps1 — 记录当前会话模型到 .debug/temp/.cc_model,供 git 的 prepare-commit-msg 钩子读取。
# 由 PreToolUse(Bash) 直接调用(纯 pwsh,无 bash wrapper):内部仅 git commit 时刷新模型。永远 exit 0、不改命令。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
    $data = $raw | ConvertFrom-Json
    # 仅 git commit 时记录(纯 pwsh 内部过滤,替代原 bash wrapper)
    $cmd = $data.tool_input.command
    if (-not $cmd -or ($cmd -notmatch 'git\s.*commit')) { exit 0 }
    $tp = $data.transcript_path
    if (-not $tp -or -not (Test-Path -LiteralPath $tp)) { exit 0 }
    # 只读尾部 200 行(快),取最后一条带 model 的记录 = 当前模型
    $model = $null
    $lines = @(Get-Content -LiteralPath $tp -Tail 200)
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        $line = $lines[$i]
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try { $o = $line | ConvertFrom-Json } catch { continue }
        $m = $null
        if ($o.message -and $o.message.model) { $m = $o.message.model }
        elseif ($o.model) { $m = $o.model }
        if ($m) { $model = [string]$m; break }
    }
    if (-not $model) { exit 0 }
    $dir = Join-Path $env:CLAUDE_PROJECT_DIR '.debug\temp'
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [System.IO.File]::WriteAllText((Join-Path $dir '.cc_model'), $model)
}
catch {
    # 静默失败,绝不阻断
}
exit 0
```

### 3. git 钩子（`.git/hooks/prepare-commit-msg`）

```sh
#!/bin/sh
# prepare-commit-msg — 每次提交追加 Co-Authored-By trailer(Claude Code + 当前模型)。
# 模型来自 $GIT_TOPLEVEL/.debug/temp/.cc_model(由 Claude Code 的 PreToolUse hook 写入)。
# 无模型记录(非 CC 提交)则跳过;已有 Claude Code co-author 则幂等跳过。
msgfile="$1"
root="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$root" ] || exit 0
modelfile="$root/.debug/temp/.cc_model"
[ -f "$modelfile" ] || exit 0
model="$(tr -d '[:space:]' < "$modelfile")"
[ -n "$model" ] || exit 0
case "$model" in
  glm*)      email='noreply@bigmodel.cn' ;;
  deepseek*) email='noreply@deepseek.com' ;;
  *)         email='noreply@anthropic.com' ;;
esac
grep -q 'Co-Authored-By: Claude Code' "$msgfile" && exit 0
git interpret-trailers --in-place \
  --trailer "Co-Authored-By: Claude Code <noreply@anthropic.com>" \
  --trailer "Co-Authored-By: $model <$email>" \
  "$msgfile" 2>/dev/null
exit 0
```

> git 钩子要可执行：`chmod +x .git/hooks/prepare-commit-msg`（Windows 下 Git Bash）。

## 安装

三个文件放对位置：

- `.claude/settings.local.json` — 加上面的 `attribution` + `hooks`（`.claude/*` 已 gitignore，个人本地）。
- `.claude/hooks/commit_trailer.ps1` — 上面脚本（`.claude/*` gitignore）。
- `.git/hooks/prepare-commit-msg` — 上面脚本 + `chmod +x`（`.git/` 本机本地）。

> 改 `.claude/settings.local.json` 的 hooks 配置后，需重载（`/hooks` 或重启 Claude Code）生效；脚本内容改动即时生效（每次调用从磁盘重读）。

## 效果示例

跑 GLM 模型时，每次提交自动得到：

```
<你的提交标题>

Co-Authored-By: Claude Code <noreply@anthropic.com>
Co-Authored-By: glm-5.2 <noreply@bigmodel.cn>
```

## 备注

- **邮箱只是占位**：GLM/DeepSeek 等厂商目前没有官方 GitHub bot 邮箱，模型那行的邮箱（在 GitHub 上）不会出头像/contributor，仅作标识。等哪方出了官方 bot 再换。
- **个人/本地**：这套都在 gitignore 路径（`.claude/*`、`.git/`），不进版本库，各自机器按需复制。
- **泛化到多工具**：本项目只跑 Claude Code，所以工具那行写死、工具 hook 只写模型名。多工具时让各工具自带的 hook 把「工具名 + 模型名」都写进侧信道、git 钩子统一读即可——换工具、换模型都自动反映。
