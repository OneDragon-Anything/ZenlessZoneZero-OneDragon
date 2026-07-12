---
name: new-config
description: 新建配置工具 - 创建新的 agent state 模板、自动战斗 YAML 配置等，并运行构建脚本合并产物
version: 1.0.0
author: OneDragon-Anything
tags: [zzz, config, template, automation, powershell]
---

# 新建配置工具

用于在 ZenlessZoneZero-OneDragon 项目中快速创建新的配置模板并合并构建产物。

## 目录结构

```
skills/new-config/
  SKILL.md                  # 本说明文件
  new-config.ps1            # 构建 auto_battle merged.yml
  compile-po.ps1            # 编译 PO 多语言翻译文件
  generate-manifest.ps1     # 生成模块清单
```

## 使用方式

### new-config.ps1 — 构建 auto_battle merged.yml

修改或新增 `config/auto_battle/`、`config/auto_battle_state_handler/`、`config/auto_battle_operation/` 下的 sample YAML 文件后运行：

```powershell
powershell -File skills/new-config/new-config.ps1
```

设置 PYTHONPATH 到 `src`，运行 `src/zzz_od/auto_battle/build_utils.py` 构建所有合并 YAML。

### compile-po.ps1 — 编译 PO 翻译文件

```powershell
powershell -File skills/new-config/compile-po.ps1
```

运行 `src/one_dragon/devtools/compile_po.py`。

### generate-manifest.ps1 — 生成模块清单

```powershell
powershell -File skills/new-config/generate-manifest.ps1
```

运行 `deploy/generate_module_manifest.py`。

### 空运行

所有脚本支持 `-DryRun` 参数，只输出环境信息不执行：

```powershell
powershell -File skills/new-config/new-config.ps1 -DryRun
```

## 新建配置的一般流程

1. 在 `src/zzz_od/game_data/agent.py` 中定义新 Agent
2. 创建 `assets/template/agent_state/{agent_id}_3_1/` 等目录及 config.yml + mask.png
3. 创建 `assets/template/battle/avatar_*_{agent_id}/` 头像模板
4. 创建 `config/auto_battle_operation/` 下的操作模板 sample YAML
5. 创建 `config/auto_battle_state_handler/` 下的状态模板 sample YAML
6. 运行 `new-config.ps1` 构建合并产物
7. 提交所有改动及构建产物