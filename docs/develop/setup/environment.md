# 开发环境

## 依赖管理

本项目使用 [uv](https://github.com/astal-sh/uv/releases/latest) 进行依赖管理。安装开发环境：

```shell
uv sync --group dev
```

## 源码布局（src-layout）

项目使用 `src-layout` 结构，源代码位于 `src/` 目录下。请自行在 IDE 中设置为 `Sources Root`，或增加环境变量 `PYTHONPATH=src`。
