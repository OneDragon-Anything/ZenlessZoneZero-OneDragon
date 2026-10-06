# 集成启动器分支审查报告

## 审查范围

- 审查分支：`feat/runtime-launcher-builtin-recovery`
- 审查内容：启动内核源码迁移与 profile 解耦、恢复重装流程、恢复界面、启动器替换事务和发行打包。
- 本报告以当前工作区最终实现为准，包含本轮根据审查结果补上的修复。

## 总体结论

当前实现符合本轮的主要架构约束：

- `runtime_launcher_bootstrap` 位于 `one_dragon/launcher/` 下。
- 通用启动内核只定义 `RuntimeLauncherProfile` 抽象基类和启动流程，不包含 `zzz_od` 或“绝区零”内容。
- 绝区零在 `zzz_od` 代码层提供 profile 子类和冻结入口，不再使用 JSON profile。
- 正常模式和恢复模式分别激活外部源码树与内置源码树；项目入口父包也会随选中的源码树重定向。
- 恢复页使用独立的固定布局和窗口内进度，不复用资源管理页或下载队列。
- 恢复服务不依赖 Qt，通过适配器接收界面回调。

此前审查发现的 3 项问题已经处理：版本标签查询不再由恢复窗口单独启动后台线程；资源管理页中的旧恢复分支和重复卡片已移除；恢复服务改为调用更新服务公开的暂存校验接口，并使用明确的下载参数类型。

## 审查问题及处理结果

### 已修复：关闭窗口不再等待独立版本标签查询

旧实现由 `start_tag_query()` 启动独立标签查询线程，窗口关闭时把该线程视为恢复任务的一部分，但查询没有独立的取消边界。

当前恢复页只显示“正式版”和“测试版”两个通道，不需要在页面打开时预取具体标签。独立标签查询线程、适配器标签信号和 `is_tag_query_active()` 已删除。用户点击重装后，候选标签查询在恢复工作线程内执行；窗口关闭只等待真正的重装任务完成或取消。

### 已修复：资源管理页不再保留第二套恢复界面

恢复模式现在只使用 `RecoveryRepairInterface`。`ResourceManagementInterface` 已移除恢复模式参数、恢复卡片、恢复事件处理、标签查询和重装启动分支；无入口的 `RecoveryRepairCard` 也已删除。正常资源管理页仍保留代码同步、启动器、模型和下载设置功能。

### 已修复：恢复服务使用明确的公开接口和下载参数

暂存启动器校验已由更新服务的私有方法改为公开的 `validate_staged_launcher()`，普通暂存更新和恢复重装复用同一校验入口。恢复服务的下载参数现在声明为 `CommonDownloaderParam`，不再使用 `object`。

### 已修复：代码检出后取消导致版本不一致

最终检出前的下载、校验、远程拉取和工作区确认仍可取消。`before_checkout` 完成最后一次工作区快照确认后，会在同一把状态锁内进入不可取消的提交阶段；从第一次写入工作区开始，即使用户请求取消，也会继续完成后续检出和启动器替换。恢复界面进入该阶段后禁用取消按钮，避免留下新代码配旧启动器的状态。

### 已修复：稳定更新服务固定在启动器，恢复服务进入冻结模块

Git、下载、更新、启动器替换事务和恢复编排属于启动器稳定层，不能随外部业务源码更新。此前恢复入口依赖 `one_dragon.envs.recovery_repair_service`，但该模块没有进入冻结导入清单；源码树切换后，缓存的 `one_dragon.envs` 包可能找不到内置源码中的恢复服务。

当前 `RuntimeLauncherProfile.frozen_import_modules` 声明必须固定在启动器中的稳定模块，PyInstaller spec 将其加入 hidden imports。绝区零 profile 已声明恢复服务，恢复界面仍从内置源码树动态加载。这样既不重定向稳定服务，也不会因 `one_dragon.envs` 包路径缓存导致恢复服务导入失败。

### 已修复：恢复 tag 拉取提前污染远程分支引用

恢复重装在用户最终确认前需要先拉取目标 tag，但这个过程不应改变普通同步使用的 `refs/remotes/<remote>/<branch>`。此前导入 tag 后额外把 tag 提交写入远程分支引用，用户取消或拒绝覆盖后，后续普通同步可能把 tag 错当作分支最新提交。

当前 tag fetch 只导入 `refs/tags/<tag>`，不再创建或覆盖目标远程分支引用；普通分支 fetch 仍按原逻辑更新远程分支引用。首次建仓或损坏重建使用 `initial_tag` 时，目标本地分支直接从 tag 创建，并跳过只适用于远程分支的同步步骤。新增回归测试覆盖已有仓库的 tag 导入、普通分支导入和 initial tag 建仓，分别验证远程分支 OID 保持不变、正常更新以及首次建仓可完成。

## 代码层 profile 方案

- 通用抽象：`src/one_dragon/launcher/runtime_launcher_bootstrap/profile.py`
- 通用启动流程：`src/one_dragon/launcher/runtime_launcher_bootstrap/launcher.py`
- 绝区零项目 profile：`src/zzz_od/win_exe/runtime_launcher_profile.py`
- 绝区零冻结入口：`src/zzz_od/win_exe/runtime_launcher_bootstrap.py`
- 内置源码清单生成：`deploy/generate_builtin_source.py`
- 发行包校验：`tools/ci/prepare_release_assets.py`

项目 profile 由冻结入口直接实例化并注入通用启动流程。生成器、测试和发行校验也直接复用项目 profile；`deploy/runtime_launcher_profile.json` 已移除。

## 验证情况

已验证：

- 启动器 profile、源码树切换和项目入口动态导入回归测试：8 项通过。
- 启动器审查问题与 Git 引用隔离相关回归测试：13 项通过，覆盖资源页接口、恢复页活动任务判断、公开暂存校验接口、Git 检出后取消仍完成启动器替换，以及 tag/普通分支导入和 initial tag 建仓的远程引用行为。
- 本轮修改文件的 Ruff 检查通过。
- 本轮修改文件的 Python 语法检查通过。
- 主仓和测试仓 `git diff --check` 通过。
- 通用启动内核中无 `zzz_od` 或“绝区零”字符串。
- 生产代码中无有效的 JSON profile 引用。

仍未验证：

- 已在隔离临时目录完成 PyInstaller 冻结构建，PYZ 清单确认包含恢复服务、Git 服务和项目同步策略；尚未生成内置源码快照并组成完整发行包。
- 未在实际冻结后的 EXE 中分别启动正常模式和恢复模式。
- 资源管理页旧测试有 5 项因测试夹具缺少当前 `proxy_type`、`model_resource_cards` 等上下文而失败；更新服务旧测试有 4 项因当前 API 和事务语义已经变化而失败。这些旧测试不能作为本轮实现的有效回归依据，需另行更新测试仓。

## 后续建议

1. 在 Windows 干净环境执行一次 RuntimeLauncher 冻结构建。
2. 对冻结产物分别做正常启动、ready 前失败进入恢复模式、恢复模式动态入口导入的冒烟验证。
3. 单独清理测试仓中仍引用旧 `RuntimeLauncher` API 的历史测试，避免收集阶段错误掩盖后续回归。
