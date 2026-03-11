# RuntimeLauncher 应用内自更新

本文档描述 `OneDragon-RuntimeLauncher.exe + .runtime/` 的应用内自更新方案。`src/` 及其他业务代码不走这条链路，仍按现有 git 更新方式维护。

## 更新对象

自更新系统只负责以下内容：

- `OneDragon-RuntimeLauncher.exe`
- `.runtime/`

不负责：

- `src/`
- `WithRuntime.zip`
- `Full` / `Full-Environment`

现有发布物的角色：

- `ZenlessZoneZero-OneDragon-RuntimeLauncher.zip`
  - 作为全量更新包
  - GitHub Release 继续上传
  - 同时同步到 S3/CDN，S3 中保存为 `runtime-full.zip`
- `ZenlessZoneZero-OneDragon-<ver>-WithRuntime.zip`
  - 继续作为首次安装、离线恢复、手动覆盖修复包
  - 不进入应用内自更新流程

## 元数据与对象路径

S3/CDN 路径固定为：

- `channels/stable/latest.json`
- `channels/beta/latest.json`
- `versions/<ver>/runtime-full.zip`
- `versions/<ver>/diff-from-<old>.zip`

其中：

- `runtime-full.zip` 的内容与 GitHub Release 的 `ZenlessZoneZero-OneDragon-RuntimeLauncher.zip` 完全一致
- `diff-from-<old>.zip` 只包含变化文件，并在 zip 根目录内带一个 `changes.json`

`changes.json` 固定结构：

```json
{
  "from_version": "v1.2.2",
  "to_version": "v1.2.3",
  "added": ["path/a"],
  "modified": ["OneDragon-RuntimeLauncher.exe", ".runtime/x.dll"],
  "deleted": [".runtime/old.dll"]
}
```

`latest.json` 固定结构：

```json
{
  "version": "v1.2.3",
  "channel": "stable",
  "release_notes": "",
  "published_at": "",
  "sources": {
    "s3": {
      "full": {
        "url": "https://cdn.example.com/versions/v1.2.3/runtime-full.zip",
        "sha256": "...",
        "size": 123
      },
      "diffs": [
        {
          "from": "v1.2.2",
          "url": "https://cdn.example.com/versions/v1.2.3/diff-from-v1.2.2.zip",
          "sha256": "...",
          "size": 45
        }
      ]
    },
    "github": {
      "full": {
        "url": "https://github.com/.../ZenlessZoneZero-OneDragon-RuntimeLauncher.zip",
        "sha256": "...",
        "size": 123
      },
      "diffs": [
        {
          "from": "v1.2.2",
          "url": "https://github.com/.../ZenlessZoneZero-OneDragon-RuntimeLauncher-diff-from-v1.2.2-to-v1.2.3.zip",
          "sha256": "...",
          "size": 45
        }
      ]
    }
  }
}
```

应用内更新时：

- `自动`：优先使用 S3/CDN，失败后回退到 GitHub
- `S3/CDN`：只使用 S3/CDN
- `GitHub`：只使用 GitHub
- `Mirror酱`：预留

## GitHub Release 需要新增的资产

保持现有资产不变，继续上传：

- `ZenlessZoneZero-OneDragon-<ver>-Full.zip`
- `ZenlessZoneZero-OneDragon-<ver>-Full-Environment.zip`
- `ZenlessZoneZero-OneDragon-<ver>-Installer.exe`
- `ZenlessZoneZero-OneDragon-<ver>-WithRuntime.zip`
- `ZenlessZoneZero-OneDragon-Launcher.zip`
- `ZenlessZoneZero-OneDragon-RuntimeLauncher.zip`

新增应用内更新专用资产：

- `ZenlessZoneZero-OneDragon-RuntimeLauncher-Update-Latest.json`
- `ZenlessZoneZero-OneDragon-RuntimeLauncher-diff-from-<old>-to-<new>.zip`

这些新增资产主要给应用内更新使用，不需要在 Release 页面单独解释给普通用户。

## CI 新增内容

`build-release.yml` 在 `prepare_release_assets.py` 之后新增两个环节：

1. 生成 RuntimeLauncher 自更新资产
2. 将这些资产上传到 S3/CDN

生成脚本：

- `tools/ci/generate_runtime_update_assets.py`

脚本职责：

- 读取当前版本的 `ZenlessZoneZero-OneDragon-RuntimeLauncher.zip`
- 从 GitHub Release 下载最近 5 个历史版本的 `RuntimeLauncher.zip`
- 生成：
  - `runtime_update_assets/channels/<channel>/latest.json`
  - `runtime_update_assets/versions/<ver>/runtime-full.zip`
  - `runtime_update_assets/versions/<ver>/diff-from-<old>.zip`
- 同时把 GitHub 需要上传的：
  - `ZenlessZoneZero-OneDragon-RuntimeLauncher-Update-Latest.json`
  - `ZenlessZoneZero-OneDragon-RuntimeLauncher-diff-from-<old>-to-<new>.zip`
  放到仓库根目录

上传顺序固定：

1. 上传 `versions/<ver>/runtime-full.zip`
2. 上传 `versions/<ver>/diff-from-<old>.zip`
3. 确认对象可访问
4. 最后覆盖 `channels/<channel>/latest.json`

这样可以避免客户端读到新版本元数据，但对象还没传完。

## S3/CDN 配置

当前工作流使用 S3 兼容接口，支持：

- AWS S3
- Cloudflare R2
- MinIO

GitHub Actions 中新增的变量与密钥：

仓库变量：

- `RUNTIME_UPDATE_S3_BUCKET`
- `RUNTIME_UPDATE_S3_REGION`
- `RUNTIME_UPDATE_S3_ENDPOINT`
- `RUNTIME_UPDATE_S3_PUBLIC_BASE_URL`

仓库密钥：

- `RUNTIME_UPDATE_S3_ACCESS_KEY_ID`
- `RUNTIME_UPDATE_S3_SECRET_ACCESS_KEY`

说明：

- `RUNTIME_UPDATE_S3_ENDPOINT`
  - AWS S3 可留空
  - Cloudflare R2 / MinIO 需要填写
- `RUNTIME_UPDATE_S3_PUBLIC_BASE_URL`
  - 客户端实际使用的公开下载地址
  - 必须是稳定的 HTTPS 公网地址
  - 客户端不会直接使用内部 API endpoint

如果使用 Cloudflare R2：

- bucket 可以保持私有
- 通过公共域名或自定义域名暴露只读下载
- CI 用 S3 兼容 endpoint 上传
- 客户端只读取 `runtime_update_cdn_base_url`

项目默认配置位于：

- `config/project.yml`

字段：

- `runtime_update_cdn_base_url`

如果该字段为空，GUI 中不会提供 `S3/CDN` 选项，应用内只会使用 GitHub 源。

## 保留策略

建议由对象存储生命周期策略处理旧版本清理：

- 全量包保留最近 5 个版本
- diff 包保留最近 5 个版本到最新版的链路

客户端行为：

- 找得到当前版本对应的 diff，就优先下载 diff
- 找不到 diff，就直接下载 full

因此生命周期删除旧 diff 不会阻塞升级，只会让更老版本回退为全量下载。

## Mirror酱接入

当前仓库保持现有：

- `.github/workflows/mirrorchyan_uploading.yml`

Mirror酱在这套系统里的定位是“后续可选下载源”，不是元数据中心。

后续接法：

1. 保持 `latest.json` 仍由自家 S3/CDN 或 GitHub 维护
2. 如果 Mirror酱能为 RuntimeLauncher 全量包或 diff 包提供稳定下载链接，则在 `latest.json` 中新增 `mirror` 源
3. GUI 增加 `Mirror酱` 选项

不做的事情：

- 不让应用直接依赖 Mirror酱专有元数据格式
- 不让 Mirror酱 托管 `latest.json`

## 本地更新目录

运行时会在工作目录生成以下文件和目录：

- `.update_staging/`
- `.update_backup/`
- `.update_logs/`
- `runtime_update_state.json`

用途：

- `.update_staging/`：下载和解压更新包
- `.update_backup/`：应用更新前备份 `exe + .runtime`
- `.update_logs/`：PowerShell 替换与回滚日志
- `runtime_update_state.json`：记录最近一次 RuntimeLauncher 更新结果

这些路径已经加入 `.gitignore`，不会进入仓库。
