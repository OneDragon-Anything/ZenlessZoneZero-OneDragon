# 返回大世界应用

## 功能说明

这是一个简单的应用，用于将游戏状态返回到大世界（普通世界）。无论当前处于什么界面（邮件、商店、战斗等），都可以通过此应用返回到大世界。

## 使用方法

### 通过 GUI 使用

1. 启动一条龙程序
2. 在应用列表中找到"返回大世界"
3. 点击运行按钮

### 通过命令行使用

```bash
uv run --env-file .env src/zzz_od/application/zzz_application_launcher.py back_to_world
```

## 技术实现

该应用基于 `BackToNormalWorld` 操作实现，能够智能识别当前游戏状态并执行相应的返回操作：

- 如果在菜单界面，点击返回按钮
- 如果在战斗界面，退出战斗
- 如果在对话框，关闭对话框
- 如果在其他特殊界面，执行相应的返回逻辑

## 文件结构

```
back_to_world/
├── __init__.py                          # 包初始化文件
├── back_to_world_const.py               # 常量定义
├── back_to_world_app.py                 # 应用主类
├── back_to_world_app_factory.py         # 应用工厂
├── back_to_world_run_record.py          # 运行记录
└── test_back_to_world.py                # 测试文件
```

## 注意事项

- 该应用会自动处理各种异常情况，确保能够成功返回大世界
- 如果卡在某个界面，应用会尝试多种返回方式
- 支持从空洞、战斗、对话等各种状态返回
