# Claude Code:Pyright LSP(uv 方式)

> 给 Claude Code 接入 pyright LSP(代码导航:定义 / 引用 / 符号),用 **uv 方式**启动,不用官方的全局 pyright。本文是 Claude Code 的具体落地;定位见 [ai_coding.md § LSP](../ai_coding.md#lsp)。

## 为什么不用官方 pyright-lsp

Claude Code 官方的 [`pyright-lsp@claude-plugins-official`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/pyright-lsp) 启动 command 是裸 `pyright-langserver` —— 走**系统 PATH**、全局装 pyright。它跑在系统 Python 环境里,解析 import 时看不到项目 `.venv` 的依赖(`pyside6`、`onnxruntime-directml`…),Python 版本也可能对不上 → 跟项目的 uv 环境冲突。

本项目(及一条龙系列)用 [`uv-pyright-lsp@onedragon-cc-plugins`](https://github.com/OneDragon-Anything/OneDragon-CC-Plugins) 改造版:command 是 `uv run pyright-langserver` → **锁在项目 venv**,pyright 和项目依赖、Python 版本同源,不冲突。

## 怎么工作

插件 `plugin.json` 声明 lspServers,Claude Code 启用插件后按它经 `uv run` 拉起 pyright-langserver(stdio),内置 LSP 工具(hover / 定义 / 引用 / 符号)再连接它:

```json
{
  "lspServers": {
    "uv-pyright": {
      "command": "uv",
      "args": ["run", "pyright-langserver", "--stdio"],
      "extensionToLanguage": { ".py": "python", ".pyi": "python" }
    }
  }
}
```

## 安装

分两块:团队共享(`pyproject.toml`,提交)+ 个人本地(`.claude/`,gitignore)。

### 1. 团队共享:`pyproject.toml`(已配)

`uv sync --group dev` 即装好 pyright(dev 组);`[tool.pyright]` 已配导航用(不刷类型诊断):

```toml
[tool.pyright]
include = ["src"]
exclude = ["**/__pycache__", ".venv", ".debug", ".install", "zzz-od-test"]
extraPaths = ["src"]        # src-layout + package=false:让 pyright 去 src/ 解析导入
typeCheckingMode = "off"    # 起步只用导航;TODO 后续随改造提升 → basic → standard
```

### 2. 个人本地:装插件 + 开开关

```bash
# 添加一条龙插件市场
claude plugin marketplace add OneDragon-Anything/OneDragon-CC-Plugins
# 安装并启用
claude plugin install uv-pyright-lsp@onedragon-cc-plugins
claude plugin enable uv-pyright-lsp@onedragon-cc-plugins
```

`.claude/settings.json` 里开 LSP 工具 + 确认插件启用:

```json
{
  "env": { "ENABLE_LSP_TOOL": "true" },
  "enabledPlugins": { "uv-pyright-lsp@onedragon-cc-plugins": true }
}
```

> 不要在 `settings.json` 另写 `lspServers` —— 插件已提供同一份定义,重复手写是冗余(跟随插件上游维护即可)。

## 验证

新会话里用 LSP 工具(首启 pyright 经 `uv run` + node 要 warm up 一会儿):

- `documentSymbol`:列文件符号
- `hover`:看类型
- `findReferences` / `goToDefinition`:跨文件导航

## 备注

- **坚持 uv 方式**:勿启用官方 `pyright-lsp@claude-plugins-official`(走全局 pyright,和 uv 环境冲突)。
- **typeCheckingMode 暂 off**:现有代码未 type-clean,strict 会刷一堆错干扰;只用导航。后续随改造提升(见 `pyproject.toml` 的 `TODO(type-check)`)。
- **个人/团队 scope**:`pyproject.toml`(pyright 依赖 + `[tool.pyright]`)团队共享、提交;`.claude/`(插件 enable + `ENABLE_LSP_TOOL`)个人本地、gitignore(`.claude/*` 默认不进版本库),各自机器配。
