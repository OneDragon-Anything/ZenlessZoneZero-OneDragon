# 开发流程规范

本文档说明项目的开发流程规范，包括日常开发、Submodule 使用、PR 处理等。

## 日常开发流程

### 1. 开始新功能

1. 同步 main 分支最新代码
2. 从 main 创建开发分支，子模块也切换到相同的分支
3. 在分支上进行开发

### 2. 自测检查

1. 为本次修改编写对应测试
2. 确保测试全部通过
3. 使用 ruff 和 pyright 进行代码检测并修复

### 3. 提交代码

1. 按照提交规范编写提交信息（feat/fix/refactor/docs/test/chore）
2. 创建 PR

### 4. PR 处理

1. 确保相关 action check 通过
2. 对 reviewer 发起的 thread 进行修复或回复
3. 确保所有 thread 都 resolve

### 5. 合并代码

1. 优先使用 squash 进行合并代码
2. 先对子模块进行合并
3. 将子模块切换到最新的 main
4. 回到主仓库，更新 submodule 引用
5. 合并主仓库的功能分支到 main
