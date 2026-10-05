# 资源下载源与候选回退

## 作用

HTTP 资源（OCR 模型、YOLO 模型、启动器等 release 附件）的下载源选择、候选回退与下载确认交互。与 [Git 服务的代码源回退](git_service.md) 同构：源列表由项目级 `repository.yml` 提供，框架不写死具体托管平台。

## 配置来源：repository.yml 的 resource_download 段

```yaml
resource_download:
  sources:            # 资源下载源元数据
    github:
      label: GitHub
      use_proxy: true # 是否使用 ghproxy 代理
    cnb:
      label: CNB
      use_proxy: false
  recommend:          # 按系统语言推荐的源
    zh: cnb
    en: github
  repos:              # 各 release 仓库在不同源上的 release 根路径
    main:             # 主仓库（启动器）
      github: "https://github.com/.../releases"
      cnb: "https://cnb.cool/.../-/releases"
    env:              # OneDragon-Env（OCR 模型、环境文件）
      ...
    yolo:             # OneDragon-YOLO（识别模型）
      ...
  models:             # 项目识别模型声明
    detector:
      label: 目标识别
      default: detector-v2
      repo: yolo
      tag: project_model
      gpu_config: detector_gpu
      required_files:
        - model.onnx
        - labels.csv
```

- `repos` 存 release 根路径（以 `/releases` 结尾）。附件地址由 `RepoConfig.get_resource_asset_urls(repo_key, tag, file_name)` 拼装：`tag` 非空时为 `{root}/download/{tag}/{file}`，为空时为 `{root}/latest/download/{file}`。GitHub 与 cnb 的路径结构一致（cnb 规范路径带 `/-/`，且同样支持 `latest/download`）。
- 某个仓库缺少某个源时，候选回退会自动跳过该源。
- 该段整体可选；未配置的项目回退到各构造点自带的下载地址。

## 源选择与自动模式

配置字段（`env_config`）：

- `resource_source`：用户选择；`auto` 为自动模式（默认）。
- `last_resource_source`：最近一次下载成功的源 ID。
- `resource_download_no_confirm`：自动下载前是否跳过确认弹窗。

候选顺序由 `RepoConfig.get_resource_source_candidates()` 生成：

```text
用户指定源 → 上次成功源 → 按语言推荐源（zh→cnb en→github）→ 其余源按 YAML 顺序
```

`EnvConfig.get_resource_source_order()` 封装了以上入参（当前语言来自 `i18_utils`）。

## 下载层：CommonDownloader

`CommonDownloaderParam.download_urls` 为 `源ID → 下载地址` 的映射。`CommonDownloader.download(source_order=...)` 按候选顺序逐个尝试：

- 只对 `github` 源拼接 ghproxy 前缀；
- 某源失败自动尝试下一个；用户取消（`progress_signal`）则立即终止不再回退；
- 自动模式下，非最后候选源有 10 秒启动宽限；之后最近约 4 秒持续低于 100 KB/s 时按失败处理并尝试下一个源。最后一个候选源不限速，避免慢网络完全无法下载。手动选择下载源时不启用低速淘汰。
- 成功后回调 `on_source_success(source_id)`，调用方以此写入 `last_resource_source`；自动模式中上次成功源失败或因持续低速被淘汰时，会先清除旧记录，后续源成功后再记录新源。
- 同时提供结构化进度，包含来源、阶段、字节数、总量和实时速度；旧的百分比回调继续保留。
- HTTP 下载先写同目录临时文件，成功后再替换目标文件；失败或取消会清理临时文件。

## 进程内下载队列

主程序中的 OCR、识别模型和启动器统一交给 `DownloadQueueService`。安装器仍使用原有安装步骤，代码同步也不进入队列。

- `ResourceDownloadSpec` 描述资源 ID、当前和目标版本、下载器以及下载前后处理。
- `ResourceDownloadTask` 保存单次任务的排队时间、结果、取消状态和结构化进度。
- 去重键为“资源 ID + 目标版本”，相同任务不会重复创建。
- 队列单线程顺序执行；OCR 初始化任务插到当前任务之后。
- 弹窗关闭只隐藏界面，不停止任务。标题栏的“下载”按钮可以重新打开同一个队列弹窗。
- 资源卡片首次点击“下载”只加入队列，并在标题栏下载按钮处显示提示；卡片随后显示“下载中”，再次点击该按钮才打开队列弹窗。其他尚未下载的卡片仍按首次加入队列处理。
- 运行项可取消，等待项可移出，失败项可重试，成功项可清理。取消只设置令牌，不在界面线程等待工作线程。
- 队列只保存在当前进程；存在活动任务时，主窗口会先提示取消再退出。

## 更新编排层

`one_dragon.envs.update_service.UpdateService` 负责资源更新中高于下载器的编排逻辑，当前包括启动器版本检查、目标通道计算、更新包参数构造和事务替换。版本检查会先识别当前安装的是原始启动器还是集成启动器，判断、展示和下载始终使用同一种启动器及同一个目标版本。启动器先下载并解压到临时目录，确认目标文件存在后才备份旧版本并替换；失败会回滚，程序启动时也会恢复中断替换留下的备份。`OneDragonEnvContext.update_service` 提供统一实例。

`ResourceUpdateCoordinator` 由框架主窗口持有，负责启动器检查、OCR 请求、项目资源检查结果聚合、首次欢迎弹窗避让、同批次抑制和统一入队。它会直接读取 `ctx.model_config` 中的模型声明，项目不需要注册更新服务、构造队列任务或处理下载结果。代码同步状态由资源管理页自行展示，不进入资源弹窗和下载队列。

项目模型只需在 `config/repository.yml` 的 `resource_download.models` 中声明配置键、显示名、推荐版本、资源仓库、发布标签、GPU 配置键和必需文件。`RepoConfig` 负责校验并解析，框架据此统一完成以下工作：

- 生成资源管理页中的模型卡片、版本选项和 GPU 开关；
- 检查当前模型必需文件是否完整，以及是否存在推荐版本更新；
- 构造下载参数、更新弹窗条目和队列任务；
- 下载成功后切换模型配置，失败或取消时保持原配置。

资源管理页直接使用框架的 `ResourceManagementInterface`，项目不需要再派生界面类。

界面只负责展示和触发：启动器下载卡、聚合资源更新和安装卡均调用框架服务，不再从具体 Qt 控件模块复用文件处理函数。`DownloadService` 继续只处理通用 HTTP 下载与解压，不承载更新生命周期。

## 界面交互

- **资源更新提醒**：框架协调器将 OCR 缺失请求、项目识别模型缺失或更新、启动器更新先聚合，首次欢迎弹窗关闭后再显示一次资源选择弹窗。绝区零项目只声明闪光识别、空洞格子识别和迷失之地识别三类模型；框架会同时检查当前模型的 `model.onnx` 与 `labels.csv`，即使配置已经是推荐版本，只要文件缺失也会显示为“未安装”并提醒下载。主页不再持有更新业务状态，也不显示更新 InfoBar；代码更新不出现在该弹窗。
- **资源选择弹窗**：每项显示当前版本、目标版本和原因，默认全选。没有选中项时不能确认；下载源只有确认时才保存，点“稍后”不会修改配置。同一批更新本次运行不会再次自动弹出。
- **下载队列弹窗**：显示来源、下载量、速度、进度和解压或应用阶段。它是非阻塞弹窗，关闭后下载继续。
- **资源管理页**：原“代码同步”路由改名为“资源管理”，导航标题不附加待更新数字。页面顶部的“下载设置”组集中放置下载源、可展开的代理设置和“资源自动下载”；该开关覆盖资源缺失和发现新版本两种情况。下方“更新与下载”组依次放置代码同步摘要卡、启动器、OCR 和项目识别模型。代码同步摘要卡提供版本记录、代码设置和同步操作，普通代码设置包含代码源、标准分支和强制更新，开发者选项包含自动更新与自定义分支。代理设置直接绑定 `proxy_type`、`personal_proxy`、`gh_proxy_url` 和自动获取配置，不跳转其他页面。页面不显示单独的下载说明卡，设置页也不再保留独立资源下载子页和日志窗口。
- **模型切换**：已存在的模型可立即切换；尚未下载的模型只有下载成功后才写入当前模型配置。

## 后端自动下载的确认链路

OCR 模型缺失时 `init_ocr()` 在后台线程发起确认，复用 `ContextNotifyEvent` 的事件总线模式扩展为请求-应答：

```text
后端线程                        主线程(UI)
init_ocr 发现模型缺失
  └─ dispatch ContextDownloadRequestEvent ──> MainAppWindowBase 经 Signal 转主线程
       wait(timeout=300)                        └─ 并入框架资源选择弹窗
       <────────────────────── 队列任务结束后 respond(结果, 是否记住)
  成功后加载 OCR 模型；取消、失败或超时则结束本次初始化
```

- 已设置 `resource_download_no_confirm` 或无前端监听（`has_event_listener` 为假，如脚本/启动器场景）时，按候选顺序自动下载。
- 有前端但等待超时视为取消，不能代替用户同意。
- 用户取消：本次跳过下载，实际使用 OCR 时由惰性初始化重试。
- 「以后自动下载」默认不勾选；勾选且任务成功后写入 `resource_download_no_confirm`。

## 开发者模式

`developer_mode` 只控制界面可见性，不改变 `is_debug` 的运行行为。五秒内连续点击标题栏“代码版本”七次可开启；开启后显示开发工具、调试开关、代码高级项和现有带密码实验项。密码校验仍然有效。开发者模式由框架主窗口统一刷新，脚本环境页通过配置适配器修改状态后也会立即更新所有入口。脚本环境页提供关闭入口，关闭不会改动已保存的调试、主题、背景或窗口标题配置。
