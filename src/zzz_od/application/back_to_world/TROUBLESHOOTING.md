# 返回大世界 - 画面识别问题排查指南

## 🐛 问题描述

**现象**：应用执行时一直显示"未识别到大世界, 点击左上角"，但实际上当前画面已经是"大世界-普通"。

**日志示例**：
```
[23:32:41.153] [INFO]: 指令[ 进入游戏 ] 节点 画面识别 -> 进入游戏后操作 返回状态 未识别到大世界, 点击左上角
[23:32:44.391] [INFO]: 指令[ 进入游戏 ] 节点 画面识别 -> 进入游戏后操作 返回状态 未识别到大世界, 点击左上角
[23:32:47.757] [INFO]: 指令[ 进入游戏 ] 节点 画面识别 -> 进入游戏后操作 返回状态 未识别到大世界, 点击左上角
```

## 🔍 问题分析

### 根本原因

`BackToNormalWorld` 操作通过以下步骤检测是否已在大世界：

1. **调用 `check_and_update_current_screen()`** 识别当前画面
2. **检查是否在屏幕列表中**：`['大世界-普通', '大世界-勘域']`
3. **如果不在**，尝试通过路径导航回到大世界
4. **如果路径失败**，点击左上角返回按钮重试

### 可能的原因

#### 1. 画面识别模板问题
- 识别模板过时或不匹配
- 游戏更新导致界面变化
- 分辨率或缩放比例影响

#### 2. 截图时机问题
- 截图时画面还在加载中
- 动画效果干扰识别
- 网络延迟导致画面卡顿

#### 3. 配置问题
- 屏幕加载器配置不正确
- 识别区域定义错误
- OCR 模型不准确

#### 4. 环境因素
- 游戏窗口被遮挡
- 亮度/对比度异常
- 特殊活动界面未被识别

## 🛠️ 解决方案

### 方案 1：等待画面稳定（推荐）

在返回大世界之前，添加短暂的等待时间，确保画面完全加载：

```python
@operation_node(name='返回大世界', is_start_node=True)
def back_to_world(self) -> OperationRoundResult:
    """返回大世界"""
    import time
    
    # 等待画面稳定
    time.sleep(1)
    
    # 创建返回大世界操作
    op = BackToNormalWorld(self.ctx, ensure_normal_world=False)
    result = op.execute()
    
    return self.round_by_op_result(result)
```

### 方案 2：增加重试次数

修改 `BackToNormalWorld` 操作的重试次数：

```python
@operation_node(name='返回大世界', is_start_node=True, node_max_retry_times=120)
def back_to_world(self) -> OperationRoundResult:
    """返回大世界，增加重试次数"""
    op = BackToNormalWorld(self.ctx, ensure_normal_world=False)
    result = op.execute()
    
    return self.round_by_op_result(result)
```

### 方案 3：强制刷新画面识别

在调用前手动触发一次画面识别：

```python
@operation_node(name='返回大世界', is_start_node=True)
def back_to_world(self) -> OperationRoundResult:
    """返回大世界，先刷新画面识别"""
    from one_dragon.utils.log_utils import log
    
    # 手动截图并识别
    screen = self.screenshot()
    current_screen = self.check_and_update_current_screen(screen=screen)
    log.info(f"初始画面识别结果: {current_screen}")
    
    # 如果已经在大世界，直接返回成功
    if current_screen in ['大世界-普通', '大世界-勘域']:
        log.info(f"已在大世界: {current_screen}")
        return self.round_success(current_screen)
    
    # 否则执行返回操作
    op = BackToNormalWorld(self.ctx, ensure_normal_world=False)
    result = op.execute()
    
    return self.round_by_op_result(result)
```

### 方案 4：使用简化版本

如果不需要复杂的状态处理，可以直接点击返回按钮：

```python
@operation_node(name='返回大世界', is_start_node=True)
def back_to_world(self) -> OperationRoundResult:
    """简化版返回大世界"""
    from one_dragon.utils.log_utils import log
    
    # 最多尝试 10 次
    for i in range(10):
        screen = self.screenshot()
        current_screen = self.check_and_update_current_screen(screen=screen)
        
        if current_screen in ['大世界-普通', '大世界-勘域']:
            log.info(f"成功返回大世界: {current_screen}")
            return self.round_success(current_screen)
        
        # 尝试点击通用返回按钮
        result = self.round_by_find_and_click_area(
            screen, 
            '画面-通用', 
            '返回',
            success_wait=0.5,
            retry_wait=0.5
        )
        
        if not result.is_success:
            # 如果没有找到返回按钮，尝试点击空白区域
            self.ctx.controller.click_back()
            time.sleep(0.5)
    
    log.warning("超过最大重试次数")
    return self.round_fail("无法返回大世界")
```

## 📊 调试步骤

### 步骤 1：确认当前画面

在代码中添加调试信息，查看实际识别到的画面：

```python
@operation_node(name='返回大世界', is_start_node=True)
def back_to_world(self) -> OperationRoundResult:
    from one_dragon.utils.log_utils import log
    
    # 连续截图 3 次，查看识别结果
    for i in range(3):
        screen = self.screenshot()
        current_screen = self.check_and_update_current_screen(screen=screen)
        log.info(f"第 {i+1} 次识别结果: {current_screen}")
        time.sleep(0.5)
    
    # 继续正常流程...
```

### 步骤 2：保存截图用于分析

```python
@operation_node(name='返回大世界', is_start_node=True)
def back_to_world(self) -> OperationRoundResult:
    import cv2
    from one_dragon.utils import os_utils
    from one_dragon.utils.log_utils import log
    
    # 保存截图
    screenshot_path = os_utils.get_path_under_work_dir(
        '.debug', 
        'back_to_world_debug.png'
    )
    screen = self.screenshot()
    cv2.imwrite(screenshot_path, screen)
    log.info(f"截图已保存到: {screenshot_path}")
    
    # 识别画面
    current_screen = self.check_and_update_current_screen(screen=screen)
    log.info(f"识别结果: {current_screen}")
    
    # 继续正常流程...
```

### 步骤 3：检查屏幕配置

查看屏幕配置文件是否正确：

```bash
# 查看屏幕配置目录
ls assets/template/screen/

# 检查是否有"大世界-普通"的配置文件
find assets/template/screen/ -name "*大世界*"
```

### 步骤 4：测试画面识别

使用调试工具测试画面识别：

```python
from zzz_od.context.zzz_context import ZContext
import cv2

ctx = ZContext()
ctx.init_by_config()

# 加载测试图片
screen = cv2.imread('path/to/screenshot.png')

# 测试识别
current_screen = ctx.screen_loader.check_and_update_current_screen(screen=screen)
print(f"识别结果: {current_screen}")
```

## 🔧 高级调试

### 启用详细日志

在 `.env` 文件中设置：
```env
IS_DEBUG=true
LOG_LEVEL=DEBUG
```

### 查看屏幕识别日志

```bash
# 实时查看日志
Get-Content .log\log.txt -Wait -Tail 100 | Select-String "画面识别|大世界"
```

### 检查识别模板

```python
from zzz_od.context.zzz_context import ZContext

ctx = ZContext()
ctx.init_by_config()

# 获取"大世界-普通"的识别区域
area = ctx.screen_loader.get_area('大世界-普通', '某个区域')
print(f"区域名称: {area.name}")
print(f"区域位置: {area.rect}")
print(f"识别类型: {area.match_type}")
```

## 💡 预防措施

### 1. 定期更新识别模板

当游戏更新后，及时更新屏幕识别模板：
```bash
# 重新生成模板
python tools/update_screen_templates.py
```

### 2. 添加健康检查

在应用启动时检查画面识别是否正常：

```python
def handle_init(self) -> None:
    """初始化时检查画面识别"""
    from one_dragon.utils.log_utils import log
    
    screen = self.screenshot()
    current_screen = self.check_and_update_current_screen(screen=screen)
    
    if current_screen is None:
        log.warning("画面识别可能存在问题，请检查配置")
    else:
        log.info(f"画面识别正常，当前画面: {current_screen}")
```

### 3. 设置合理的超时

```python
ZApplication.__init__(
    self,
    ctx=ctx,
    app_id=back_to_world_const.APP_ID,
    op_name=back_to_world_const.APP_NAME,
    timeout_seconds=120,  # 2分钟超时
)
```

## 📝 常见问题

### Q1: 为什么有时能识别，有时不能？

**A**: 可能是以下原因：
- 画面加载速度不一致
- 网络延迟导致画面卡顿
- 电脑性能波动

**解决**：添加等待时间或增加重试次数。

### Q2: 如何确认是识别问题还是其他问题？

**A**: 通过保存截图并手动检查：
1. 保存执行时的截图
2. 手动查看截图内容
3. 对比识别结果

如果截图显示是大世界但识别失败，就是识别问题。

### Q3: 能否跳过识别直接返回？

**A**: 可以，但不推荐。因为：
- 不知道当前在什么状态
- 可能需要不同的返回策略
- 容易卡在特殊界面

建议保留识别逻辑，但可以优化识别方式。

## 🎯 推荐方案

根据经验，**方案 1（等待画面稳定）** 是最简单有效的解决方法：

```python
@operation_node(name='返回大世界', is_start_node=True)
def back_to_world(self) -> OperationRoundResult:
    """返回大世界"""
    import time
    from one_dragon.utils.log_utils import log
    
    # 等待 1 秒让画面稳定
    time.sleep(1)
    
    # 执行返回操作
    op = BackToNormalWorld(self.ctx, ensure_normal_world=False)
    result = op.execute()
    
    if result.is_success:
        log.info(f"✅ 返回大世界成功: {result.status}")
    else:
        log.warning(f"❌ 返回大世界失败: {result.error_str}")
    
    return self.round_by_op_result(result)
```

这个方案的优点：
- ✅ 简单有效
- ✅ 不影响原有逻辑
- ✅ 适用于大多数情况
- ✅ 易于维护

---

**最后更新**: 2026-05-11  
**相关问题**: 画面识别失败、无限循环点击、状态检测异常
