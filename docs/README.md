# 文档

项目文档目录。

## 目录结构

```
docs/
├── README.md              # 本文件
├── develop/              # 开发文档
│   ├── project-overview.md              # 项目概述和快速开始
│   ├── development-guide.md             # 开发指引总览
│   ├── coding-standards.md            # 开发规范
│   ├── development-environments.md      # 开发环境配置
│   ├── testing-standards.md           # 测试规范
│   ├── documentation-standards.md     # 文档编写规范
│   ├── one_dragon/                  # one_dragon 框架文档
│   └── zzz/                         # zzz 游戏开发文档
└── user/                 # 用户文档
    ├── README.md                     # 用户文档导航
    ├── app/                         # 应用使用说明
    │   └── battle-assistant.md
    ├── installation.md
    ├── quick-start.md
    └── faq.md
```

## 文档分类

### 开发文档 (`develop/`)

面向项目开发者，包含架构说明、开发规范和测试指南。

- **[项目概述](develop/project-overview.md)** - 项目介绍、技术栈、快速开始
- **[开发指引](develop/development-guide.md)** - 开发文档总览
- **[开发规范](develop/coding-standards.md)** - Python 代码规范和编码约定
- **[测试规范](develop/testing-standards.md)** - 测试编写和执行规范
- **[文档规范](develop/documentation-standards.md)** - 文档编写规范
- **one_dragon** - 一条龙框架架构和模块文档
- **zzz** - ZZZ 游戏特定开发文档

### 用户文档 (`user/`)

面向最终用户，提供安装、配置和使用指南。

- **[用户文档导航](user/README.md)** - 用户文档首页
- **[应用文档](user/app/)** - 各应用的使用说明
- **[安装指南](user/installation.md)** - 安装步骤
- **[快速开始](user/quick-start.md)** - 快速上手
- **[常见问题](user/faq.md)** - 常见问题解答

### 运维文档 (`ops/`)

面向运维人员，包含版本更新和运维相关文档。

- **[版本更新](ops/版本更新.md)** - 版本更新说明
- **[锄大地](ops/锄大地.md)** - 大地图录制和路线说明
