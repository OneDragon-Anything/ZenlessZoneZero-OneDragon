# 返回大世界应用 - 使用指南

## 📋 目录

- [快速开始](#快速开始)
- [功能说明](#功能说明)
- [使用方法](#使用方法)
- [常见问题](#常见问题)
- [开发者指南](#开发者指南)

---

## 🚀 快速开始

### 前提条件

1. 已安装绝区零一条龙程序
2. 游戏已启动并处于运行状态
3. Python 环境已配置（使用 uv）

### 三步使用

```bash
# 1. 进入项目目录
cd d:\my\project\ZenlessZoneZero-OneDragon

# 2. 运行返回大世界应用
uv run --env-file .env src/zzz_od/application/zzz_application_launcher.py back_to_world

# 3. 等待执行完成
```

---

## 📖 功能说明

### 主要功能

将游戏从**任何状态**智能返回到**大世界**（普通世界）。

### 支持的状态

✅ 菜单界面  
✅ 战斗界面  
✅ 对话界面  
✅ 邮件界面  
✅ 商店界面  
✅ 空洞探索  
✅ 好感度事件  
✅ 快捷手册  
✅ 其他特殊界面  

### 工作原理

1. **智能识别**：自动检测当前游戏画面状态
2. **策略选择**：根据当前状态选择合适的返回策略
3. **多重保障**：尝试多种返回方式，确保成功
4. **异常处理**：处理各种异常情况，避免卡死

---

## 💡 使用方法

### 方法一：GUI 界面（推荐新手）

1. 启动一条龙程序（双击 `debug.bat` 或运行 GUI）
2. 在左侧导航栏找到"应用运行"
3. 在应用列表中找到 **"返回大世界"**
4. 点击右侧的 **"运行"** 按钮
5. 等待执行完成

**优点**：
- 可视化操作，简单直观
- 可以查看执行日志
- 适合不熟悉命令行的用户

### 方法二：命令行（推荐开发者）

```bash
# 基本用法
uv run --env-file .env src/zzz_od/application/zzz_application_launcher.py back_to_world

# 指定实例（多账号场景）
uv run --env-file .env src/zzz_od/application/zzz_application_launcher.py back_to_world --instance 0
```

**优点**：
- 可以快速执行
- 适合脚本自动化
- 可以集成到其他工具中

### 方法三：代码调用（推荐高级用户）

```python
from zzz_od.context.zzz_context import ZContext
from zzz_od.application.back_to_world.back_to_world_app import BackToWorldApp

# 初始化上下文
ctx = ZContext()
ctx.init()

# 创建并执行应用
app = BackToWorldApp(ctx)
result = app.execute()

# 检查结果
if result.is_success:
    print(f"✅ 成功返回大世界！状态: {result.status}")
else:
    print(f"❌ 返回失败: {result.error_str}")
```

**优点**：
- 完全自定义控制
- 可以嵌入到其他应用中
- 适合开发复杂自动化流程

### 方法四：作为操作使用（最底层）

```python
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld

ctx = ZContext()
ctx.init()

# 直接调用操作
op = BackToNormalWorld(ctx)
result = op.execute()

if result.is_success:
    print(f"成功！当前状态: {result.status}")
```

**优点**：
- 最轻量级
- 无应用层开销
- 适合在 Operation 中直接调用

---

## ❓ 常见问题

### Q1: 应用执行后没有反应？

**A**: 请检查以下几点：
1. 游戏是否正在运行
2. 游戏窗口是否处于激活状态
3. 是否有其他程序遮挡了游戏窗口
4. 查看日志文件 `.log/log.txt` 了解详细错误信息

### Q2: 卡在某个界面无法返回？

**A**: 可能的原因和解决方案：
1. **特殊活动界面**：某些活动界面可能需要手动关闭
2. **网络问题**：如果网络断开，可能无法正常返回
3. **游戏 bug**：极少数情况下游戏本身可能卡住
   
   **解决方法**：
   - 尝试手动点击返回按钮
   - 重启游戏后再次尝试
   - 查看日志了解具体卡在哪里

### Q3: 执行时间过长？

**A**: 正常情况下应该在 5-15 秒内完成。如果超过 30 秒：
1. 检查电脑性能是否正常
2. 查看是否有其他程序占用资源
3. 检查网络连接是否正常
4. 查看日志了解执行进度

### Q4: 如何在其他应用中调用？

**A**: 有两种方式：

**方式一：调用应用**
```python
from zzz_od.application.back_to_world.back_to_world_app import BackToWorldApp

app = BackToWorldApp(self.ctx)
app.execute()
```

**方式二：调用操作（推荐）**
```python
from zzz_od.operation.back_to_normal_world import BackToNormalWorld

op = BackToNormalWorld(self.ctx)
op.execute()
```

### Q5: 应用会修改游戏数据吗？

**A**: **不会**。此应用只执行界面操作（点击、返回等），不会：
- 修改游戏存档
- 修改游戏内存
- 影响游戏数据
- 触发反作弊系统

它只是模拟玩家手动点击返回按钮的行为。

### Q6: 支持多开吗？

**A**: 支持。通过指定不同的实例索引：

```bash
# 第一个账号
uv run --env-file .env src/zzz_od/application/zzz_application_launcher.py back_to_world --instance 0

# 第二个账号
uv run --env-file .env src/zzz_od/application/zzz_application_launcher.py back_to_world --instance 1
```

---

## 👨‍💻 开发者指南

### 项目结构

```
src/zzz_od/application/back_to_world/
├── __init__.py                      # 包初始化
├── back_to_world_const.py           # 常量定义
├── back_to_world_app.py             # 应用主类
├── back_to_world_app_factory.py     # 应用工厂
├── back_to_world_run_record.py      # 运行记录
├── test_back_to_world.py            # 测试脚本
├── usage_examples.py                # 使用示例
├── quick_verify.py                  # 快速验证
├── README.md                        # 使用说明
└── DEVELOPMENT_SUMMARY.md           # 开发总结
```

### 核心代码解析

#### 1. 常量定义 (`back_to_world_const.py`)

```python
APP_ID = "back_to_world"        # 应用唯一标识
APP_NAME = "返回大世界"          # 应用显示名称
DEFAULT_GROUP = False           # 不在默认应用组
NEED_NOTIFY = False             # 不需要推送通知
```

#### 2. 应用主类 (`back_to_world_app.py`)

```python
class BackToWorldApp(ZApplication):
    
    @operation_node(name='返回大世界', is_start_node=True)
    def back_to_world(self) -> OperationRoundResult:
        """返回大世界的操作节点"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())
```

**关键点**：
- 继承自 `ZApplication`
- 使用 `@operation_node` 装饰器定义操作节点
- `is_start_node=True` 表示这是起始节点
- 调用 `BackToNormalWorld` 操作实现功能

#### 3. 应用工厂 (`back_to_world_app_factory.py`)

```python
class BackToWorldAppFactory(ApplicationFactory):
    
    def create_application(self, instance_idx: int, group_id: str) -> Application:
        return BackToWorldApp(self.ctx)
    
    def create_run_record(self, instance_idx: int) -> AppRunRecord:
        return BackToWorldRunRecord(
            instance_idx=instance_idx,
            game_refresh_hour_offset=self.ctx.game_account_config.game_refresh_hour_offset,
        )
```

**关键点**：
- 继承自 `ApplicationFactory`
- 负责创建应用实例和运行记录
- 遵循工厂模式

### 如何扩展功能

#### 示例 1: 添加超时控制

```python
class BackToWorldApp(ZApplication):
    
    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=back_to_world_const.APP_ID,
            op_name=back_to_world_const.APP_NAME,
            timeout_seconds=60,  # 设置 60 秒超时
        )
```

#### 示例 2: 添加重试机制

```python
@operation_node(name='返回大世界', is_start_node=True, node_max_retry_times=3)
def back_to_world(self) -> OperationRoundResult:
    op = BackToNormalWorld(self.ctx)
    return self.round_by_op_result(op.execute())
```

#### 示例 3: 添加日志记录

```python
@operation_node(name='返回大世界', is_start_node=True)
def back_to_world(self) -> OperationRoundResult:
    from one_dragon.utils.log_utils import log
    
    log.info("开始执行返回大世界操作")
    op = BackToNormalWorld(self.ctx)
    result = op.execute()
    
    if result.is_success:
        log.info(f"成功返回大世界，状态: {result.status}")
    else:
        log.warning(f"返回大世界失败: {result.error_str}")
    
    return self.round_by_op_result(result)
```

### 调试技巧

#### 1. 启用调试模式

在 `.env` 文件中设置：
```
IS_DEBUG=true
```

#### 2. 查看日志

日志文件位置：`.log/log.txt`

#### 3. 截图调试

在代码中添加截图：
```python
screen = self.screenshot()
import cv2
cv2.imwrite('debug_screenshot.png', screen)
```

#### 4. 单步执行

使用 Python 调试器：
```python
import pdb; pdb.set_trace()
```

### 测试建议

#### 单元测试

```python
def test_back_to_world_app_creation():
    """测试应用创建"""
    ctx = ZContext()
    ctx.init()
    
    app = BackToWorldApp(ctx)
    
    assert app.app_id == "back_to_world"
    assert app.op_name == "返回大世界"
    assert isinstance(app, BackToWorldApp)
```

#### 集成测试

```python
def test_back_to_world_execution():
    """测试应用执行（需要游戏运行）"""
    ctx = ZContext()
    ctx.init()
    
    app = BackToWorldApp(ctx)
    result = app.execute()
    
    assert result.is_success
    assert "大世界" in result.status
```

---

## 📚 相关资源

- [项目主页](https://github.com/your-repo/ZenlessZoneZero-OneDragon)
- [开发文档](docs/develop/README.md)
- [Application 架构说明](docs/develop/one_dragon/one_dragon_architecture.md)
- [操作节点说明](docs/develop/spec/agent_guidelines.md)

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 提交 Bug

请提供：
1. 详细的错误描述
2. 日志文件（`.log/log.txt`）
3. 复现步骤
4. 截图或录屏（如果有）

### 提交功能建议

请说明：
1. 功能描述
2. 使用场景
3. 预期效果
4. 实现思路（可选）

---

## 📄 许可证

本项目遵循项目主许可证。

---

## 🙏 致谢

感谢所有为这个项目做出贡献的开发者！

特别感谢 `drive_disk_enhance_bundle` 提供的参考实现。

---

**最后更新**: 2026-05-11
