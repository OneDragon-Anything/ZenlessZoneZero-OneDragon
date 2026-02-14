# 开发环境说明

## 标准开发环境

- Python 环境：使用 `uv sync --group dev` 进行环境搭建

## Claude Code 配置

### 插件安装

在项目根目录运行以下命令安装插件：

```bash
claude plugin marketplace add OneDragon-Anything/OneDragon-CC-Plugins
```

#### 所需插件列表

- uv-pyright-lsp - 使用uv run运行的LSP server
