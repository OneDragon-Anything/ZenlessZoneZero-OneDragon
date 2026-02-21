# 项目概述

ZenlessZoneZero-OneDragon (绝区零一条龙) 是针对游戏《绝区零》(ZenlessZoneZero) 的自动化框架。

## 项目目标

提供一套完整的自动化解决方案，支持日常任务自动执行、战斗辅助、大地图探索等功能。

## 技术栈

- **Python 3.11+**
- **PySide6** - GUI 框架
- **OpenCV** - 图像处理
- **YOLO** - 目标检测
- **OCR** - 文字识别

## 项目结构

```
ZenlessZoneZero-OneDragon/
├── src/
│   ├── one_dragon/     # 基础自动化框架
│   ├── zzz_od/         # 绝区零游戏特定实现
│   ├── zzz_mcp/        # MCP 服务器（游戏窗口检测和操作）
│   └── one_dragon_qt/  # Qt GUI 组件库
├── zzz-od-test/        # 测试代码仓库（Git Submodule）
├── docs/                # 项目文档
└── deploy/              # 构建和部署脚本
```

## 核心模块

### one_dragon 框架

提供通用的自动化能力，包括：
- 操作系统（基于节点的状态机）
- 屏幕系统（画面识别和导航）
- 应用层（高层业务逻辑）
- 插件系统（支持第三方扩展）

详细文档见 [one_dragon 框架](one_dragon/)

### zzz_od 游戏

绝区零游戏的自动化实现，包括：
- 战斗助手
- 每日任务
- 空洞探索
- 大地图探索

详细文档见 [zzz 游戏](zzz/)

### zzz_mcp 服务器

MCP (Model Context Protocol) 服务器，提供：
- 游戏窗口检测和定位
- 游戏截图操作
- 跨网络远程调用支持

详细文档见 [MCP 服务器](zzz/mcp/)

## 快速开始

### 克隆项目

```bash
# 克隆主仓库
git clone https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon.git
cd ZenlessZoneZero-OneDragon

# 初始化并更新子模块（必须）
git submodule update --init --recursive
```

### 安装依赖

```bash
uv sync --group dev
```

### 环境变量

项目使用 `.env` 文件管理环境变量。主要变量：

- **PYTHONPATH=src** - 必须设置，指定 Python 源码路径
- 其他推送服务相关变量（可选）

配置方式：
1. 复制测试仓库中的 `.env.sample` 到项目根目录
2. 重命名为 `.env`
3. 根据需要修改配置

### 运行命令

**重要**：所有 `uv run` 命令必须加上 `--env-file .env` 参数，否则会因为找不到模块而报错。

```bash
# 运行应用
uv run --env-file .env python src/zzz_od/gui/app.py

# 运行测试
uv run --env-file .env pytest zzz-od-test/

# 代码检查
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# 类型检查
uv run pyright src/
```
