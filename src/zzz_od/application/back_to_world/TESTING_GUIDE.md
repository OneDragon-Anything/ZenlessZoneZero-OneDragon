# 返回大世界应用 - 测试与调试指南

## 🧪 测试方法

### 1. 直接运行应用（推荐）

```bash
cd d:\my\project\ZenlessZoneZero-OneDragon
uv run --env-file .env src/zzz_od/application/back_to_world/back_to_world_app.py
```

这会执行 `__debug()` 函数，使用配置文件初始化上下文并运行应用。

### 2. 通过应用启动器运行

```bash
uv run --env-file .env src/zzz_od/application/zzz_application_launcher.py back_to_world
```

### 3. 在 Python 中调用

```python
from zzz_od.context.zzz_context import ZContext
from zzz_od.application.back_to_world.back_to_world_app import BackToWorldApp

# 初始化上下文
ctx = ZContext()
ctx.init_by_config()

# 创建并执行应用
app = BackToWorldApp(ctx)
result = app.execute()

# 检查结果
if result.is_success:
    print(f"✅ 成功！状态: {result.status}")
else:
    print(f"❌ 失败: {result.error_str}")
```

### 4. 通过 GUI 运行

1. 启动 GUI：`uv run --env-file .env src/zzz_od/gui/app.py`
2. 导航到"一条龙" → "返回大世界"
3. 点击"运行"按钮

## 🔍 调试技巧

### 启用调试模式

在 `.env` 文件中设置：
```env
IS_DEBUG=true
```

### 查看日志

日志文件位置：`.log/log.txt`

查看实时日志：
```bash
# PowerShell
Get-Content .log\log.txt -Wait -Tail 50

# 或使用 VS Code 的日志查看器
```

### 截图调试

在代码中添加截图保存：
```python
@operation_node(name='返回大世界', is_start_node=True)
def back_to_world(self) -> OperationRoundResult:
    # 保存当前截图用于调试
    import cv2
    from one_dragon.utils import os_utils
    
    screenshot_path = os_utils.get_path_under_work_dir('.debug', 'back_to_world_screenshot.png')
    cv2.imwrite(screenshot_path, self.last_screenshot)
    
    op = BackToNormalWorld(self.ctx)
    return self.round_by_op_result(op.execute())
```

### 单步调试

使用 Python 调试器：
```python
import pdb; pdb.set_trace()
```

或在 VS Code 中设置断点。

## 📊 验证检查清单

### 功能验证

- [ ] 从菜单界面能返回大世界
- [ ] 从战斗界面能退出并返回大世界
- [ ] 从对话界面能关闭并返回大世界
- [ ] 从邮件界面能返回大世界
- [ ] 从商店界面能返回大世界
- [ ] 从空洞探索能退出并返回大世界
- [ ] 从快捷手册能退出并返回大世界

### 性能验证

- [ ] 执行时间在 5-15 秒内
- [ ] 不会卡死或无限循环
- [ ] 内存使用正常
- [ ] CPU 使用率正常

### 异常处理验证

- [ ] 游戏未启动时有适当提示
- [ ] 网络断开时能正确处理
- [ ] 特殊活动界面能正确处理
- [ ] 超时情况能正确退出

## 🐛 常见问题排查

### 问题 1: 应用执行后没有反应

**可能原因**：
- 游戏窗口未激活
- 游戏未启动
- 权限不足

**解决方法**：
1. 确保游戏正在运行
2. 将游戏窗口置于前台
3. 以管理员身份运行程序

### 问题 2: 卡在某个界面

**可能原因**：
- 特殊活动界面未被识别
- 网络延迟导致界面加载慢
- 游戏 bug

**解决方法**：
1. 查看日志了解卡在哪里
2. 手动点击返回按钮
3. 重启游戏后重试

### 问题 3: 执行时间过长

**可能原因**：
- 电脑性能不足
- 网络问题
- 游戏卡顿

**解决方法**：
1. 检查系统资源使用情况
2. 关闭不必要的后台程序
3. 检查网络连接

## 📝 日志分析

### 成功执行的日志示例

```
2026-05-11 10:30:00,123 | INFO | 开始执行返回大世界操作
2026-05-11 10:30:01,234 | INFO | 检测到当前画面: 菜单
2026-05-11 10:30:02,345 | INFO | 点击返回按钮
2026-05-11 10:30:03,456 | INFO | 检测到大世界-普通
2026-05-11 10:30:03,567 | INFO | 返回大世界成功
```

### 失败执行的日志示例

```
2026-05-11 10:30:00,123 | INFO | 开始执行返回大世界操作
2026-05-11 10:30:01,234 | WARNING | 未检测到已知画面
2026-05-11 10:30:02,345 | WARNING | 尝试点击通用返回按钮
2026-05-11 10:30:30,456 | ERROR | 超过最大重试次数
2026-05-11 10:30:30,567 | ERROR | 返回大世界失败
```

## 🔧 高级调试

### 修改重试次数

```python
@operation_node(name='返回大世界', is_start_node=True, node_max_retry_times=120)
def back_to_world(self) -> OperationRoundResult:
    op = BackToNormalWorld(self.ctx)
    return self.round_by_op_result(op.execute())
```

### 添加超时控制

```python
def __init__(self, ctx: ZContext):
    ZApplication.__init__(
        self,
        ctx=ctx,
        app_id=back_to_world_const.APP_ID,
        op_name=back_to_world_const.APP_NAME,
        timeout_seconds=60,  # 60秒超时
    )
```

### 自定义错误处理

```python
@operation_node(name='返回大世界', is_start_node=True)
def back_to_world(self) -> OperationRoundResult:
    try:
        op = BackToNormalWorld(self.ctx)
        result = op.execute()
        
        if not result.is_success:
            # 记录详细错误信息
            from one_dragon.utils.log_utils import log
            log.error(f"返回大世界失败: {result.error_str}")
            
        return self.round_by_op_result(result)
    except Exception as e:
        from one_dragon.utils.log_utils import log
        log.exception(f"返回大世界异常: {e}")
        return self.round_fail(str(e))
```

## 📚 相关文档

- [应用开发总结](DEVELOPMENT_SUMMARY.md)
- [应用使用说明](USAGE_GUIDE.md)
- [应用 README](README.md)
- [GUI 注册说明](../../gui/view/one_dragon/BACK_TO_WORLD_REGISTRATION.md)

## 💡 提示

1. **首次运行**：建议先在测试环境中运行，确保一切正常
2. **日志保留**：遇到问题时，保留完整的日志文件以便分析
3. **截图保存**：遇到界面识别问题时，保存截图有助于调试
4. **版本兼容**：确保使用最新版本的程序和游戏客户端

---

**最后更新**: 2026-05-11
