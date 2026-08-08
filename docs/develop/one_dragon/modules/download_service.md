# 下载服务与环境文件候选源回退

## 作用

`DownloadService` 负责统一处理各种文件下载：环境文件（uv、Python、环境压缩包）走 `download_env_file()`，其他 URL 直链下载走 `download_file_from_url()`。环境文件下载源由项目级 `repository.yml` 的 `env_source` 组声明，框架不写死具体镜像。

## 环境文件下载候选回退

`download_env_file()` 不再只使用单个 `env_source` 值，而是按候选源顺序逐个尝试：

1. 当前配置值（用户手动选择或上次成功源，即 `env_config.env_source`）优先；
2. 其后是 `repository.yml` 中 `env_source` 组的其余选项，按 YAML 声明顺序，与当前值去重；
3. 一个源失败立即尝试下一个，全部失败才返回失败；
4. 成功时将本次成功的基础 URL 写回 `env_config.env_source`，下次优先尝试。

该语义与 [GitService 的代码源候选回退](git_service.md) 对齐：代码、环境包和 Python 下载共用「用户偏好/上次成功源优先，失败立即切换，全部失败才报告，成功源持久化」。

## 覆盖范围

`download_env_file()` 的调用链是：

```text
PythonService.install_default_uv / install_standalone_python
  └─ DownloadService.download_and_extract_env_file
       └─ DownloadService.download_env_file（候选源回退）
```

因此 uv、Python（cpython zip）和项目环境压缩包下载都获得候选源回退，URL 拼接保持 `{env_source}/{project_name}/{file_name}` 不变。`cpython_source` 和 `pip_source` 仍是独立的源配置，不参与环境文件下载。
