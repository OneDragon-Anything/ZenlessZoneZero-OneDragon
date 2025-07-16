# ScreenArea使用示例和最佳实践

## 1. 弹窗处理示例

### 1.1 简单确认弹窗

```yaml
# 配置文件: confirm_dialog.yml
screen_id: confirm_dialog
screen_name: 确认对话框
pc_alt: false

area_list:
  # 弹窗背景遮罩
  - area_name: 弹窗遮罩
    area_type: popup
    layer_level: 2
    priority: 1
    pc_rect: [0, 0, 1920, 1080]  # 全屏遮罩
    id_mark: true
    # 通过半透明背景识别
    color_threshold:
      type: alpha_channel
      min_alpha: 0.3
      max_alpha: 0.8

  # 确认按钮
  - area_name: 确认按钮
    area_type: button
    layer_level: 2
    priority: 10
    parent_area: 弹窗遮罩
    pc_rect: [760, 600, 860, 640]
    text: 确认
    lcs_percent: 0.9
    interaction_type: click
    goto_list: [主界面]
    # 点击后等待弹窗消失
    wait_after_click: 1.0

  # 取消按钮
  - area_name: 取消按钮
    area_type: button
    layer_level: 2
    priority: 10
    parent_area: 弹窗遮罩
    pc_rect: [1060, 600, 1160, 640]
    text: 取消
    lcs_percent: 0.9
    interaction_type: click
    # 点击取消后关闭弹窗
    post_click_actions:
      - close_dialog
```

### 1.2 复杂多层弹窗

```yaml
# 主弹窗
- area_name: 设置弹窗
  area_type: popup
  layer_level: 2
  priority: 5
  pc_rect: [300, 200, 1620, 880]
  id_mark: true
  template_sub_dir: ui
  template_id: settings_dialog
  child_areas:
    - 音频设置标签
    - 视频设置标签
    - 控制设置标签
    - 设置确认按钮

# 子弹窗（音频设置详细）
- area_name: 音频详细设置
  area_type: popup
  layer_level: 3  # 更高层级
  priority: 8
  parent_area: 设置弹窗
  pc_rect: [400, 300, 1520, 780]
  # 只有在音频标签激活时显示
  show_conditions:
    - current_tab == "audio"
    - detail_mode == true
```

## 2. Tab切换处理示例

### 2.1 标准Tab切换

```yaml
# Tab容器
- area_name: 主菜单标签容器
  area_type: tab
  layer_level: 1
  priority: 5
  pc_rect: [200, 100, 1720, 150]
  current_state: tab_home
  state_transitions:
    tab_home: [tab_inventory, tab_character, tab_settings]
    tab_inventory: [tab_home, tab_character, tab_settings]
    tab_character: [tab_home, tab_inventory, tab_settings]
    tab_settings: [tab_home, tab_inventory, tab_character]

# 各个Tab按钮
- area_name: 主页标签
  area_type: button
  layer_level: 1
  priority: 6
  parent_area: 主菜单标签容器
  pc_rect: [250, 110, 350, 140]
  text: 主页
  interaction_type: click
  # 点击后更新父容器状态
  post_click_actions:
    - update_parent_state:tab_home

- area_name: 背包标签
  area_type: button
  layer_level: 1
  priority: 6
  parent_area: 主菜单标签容器
  pc_rect: [400, 110, 500, 140]
  text: 背包
  interaction_type: click
  post_click_actions:
    - update_parent_state:tab_inventory

# Tab内容区域
- area_name: 背包内容区
  area_type: container
  layer_level: 1
  priority: 3
  pc_rect: [200, 200, 1720, 900]
  # 只有在背包标签激活时显示
  show_conditions:
    - parent_state == "tab_inventory"
  child_areas:
    - 物品列表
    - 物品详情
    - 操作按钮组
```

### 2.2 动态Tab内容

```yaml
# 动态物品列表
- area_name: 物品列表
  area_type: dynamic
  layer_level: 1
  priority: 4
  parent_area: 背包内容区
  relative_to: 背包内容区
  relative_offset: [20, 20]
  auto_resize: true
  min_size: [400, 600]
  max_size: [600, 800]
  # 根据物品数量动态调整
  context_conditions:
    item_count: "> 0"
    sort_type: name
  # 自定义滚动处理
  custom_properties:
    scrollable: true
    scroll_direction: vertical
    items_per_page: 10
```

## 3. 动态内容处理示例

### 3.1 列表项识别

```yaml
# 动态列表容器
- area_name: 任务列表容器
  area_type: container
  layer_level: 1
  priority: 5
  pc_rect: [100, 200, 800, 800]
  # 根据任务数量显示
  show_conditions:
    - task_count > 0
  context_conditions:
    list_type: active_tasks
    filter: incomplete

# 单个任务项模板
- area_name: 任务项模板
  area_type: dynamic
  layer_level: 1
  priority: 3
  parent_area: 任务列表容器
  # 使用特征识别而非固定位置
  feature_type: template_matching
  feature_params:
    template_path: task_item_template.png
    match_threshold: 0.7
    max_matches: 20  # 最多识别20个任务项
  # 自适应阈值
  adaptive_threshold: true
  threshold_range: [0.5, 0.9]
```

### 3.2 状态相关的动态内容

```yaml
# 战斗状态UI
- area_name: 战斗UI容器
  area_type: container
  layer_level: 4  # 覆盖层
  priority: 15
  # 只在战斗状态显示
  show_conditions:
    - game_mode == "battle"
    - battle_started == true
  # 战斗结束时隐藏
  hide_conditions:
    - battle_ended == true
    - game_mode == "menu"

# 血量条（动态变化）
- area_name: 玩家血量条
  area_type: dynamic
  layer_level: 4
  priority: 20
  parent_area: 战斗UI容器
  pc_rect: [50, 50, 350, 80]
  # 颜色识别血量
  color_threshold:
    type: hsv_range
    lower: [0, 100, 100]    # 红色
    upper: [10, 255, 255]
  feature_type: color_percentage
  feature_params:
    target_color: red
    min_percentage: 0.1  # 至少10%红色才认为有血量
  # 血量状态管理
  current_state: healthy
  state_transitions:
    healthy: [injured, critical]
    injured: [healthy, critical]
    critical: [injured, dead]
    dead: [healthy]  # 复活后
```

## 4. 条件识别示例

### 4.1 时间相关条件

```yaml
# 每日任务提醒
- area_name: 每日任务提醒
  area_type: popup
  layer_level: 5  # 提示层
  priority: 25
  pc_rect: [1400, 100, 1800, 200]
  text: 每日任务
  # 时间条件
  time_conditions:
    show_after: "06:00:00"  # 每天6点后显示
    hide_after: "23:59:59"  # 每天24点前隐藏
    weekdays_only: false    # 周末也显示
  # 状态条件
  state_conditions:
    daily_tasks_completed: false
    login_today: true
```

### 4.2 等级相关条件

```yaml
# 高级功能按钮
- area_name: 高级功能按钮
  area_type: button
  layer_level: 1
  priority: 8
  pc_rect: [1500, 50, 1650, 100]
  text: 高级功能
  # 等级限制
  show_conditions:
    - player_level >= 20
    - vip_level >= 3
  # 功能未解锁时隐藏
  hide_conditions:
    - feature_locked == true
    - maintenance_mode == true
  # 点击条件
  click_conditions:
    - cooldown_remaining <= 0
    - energy >= 10
```

## 5. 相对定位示例

### 5.1 基于其他元素的定位

```yaml
# 主按钮
- area_name: 主操作按钮
  area_type: button
  layer_level: 1
  priority: 10
  pc_rect: [800, 500, 1000, 550]
  text: 开始游戏
  id_mark: true

# 相对定位的辅助按钮
- area_name: 设置按钮
  area_type: button
  layer_level: 1
  priority: 8
  relative_to: 主操作按钮
  relative_offset: [220, 0]  # 在主按钮右侧220像素
  template_sub_dir: ui
  template_id: settings_icon

- area_name: 帮助按钮
  area_type: button
  layer_level: 1
  priority: 8
  relative_to: 设置按钮
  relative_offset: [60, 0]   # 在设置按钮右侧60像素
  template_sub_dir: ui
  template_id: help_icon
```

### 5.2 动态相对定位

```yaml
# 弹出菜单
- area_name: 右键菜单
  area_type: popup
  layer_level: 3
  priority: 15
  # 相对于鼠标位置
  position_calculator: mouse_position
  position_params:
    offset_x: 10
    offset_y: -10
    boundary_check: true  # 检查边界，避免超出屏幕
  # 显示条件
  show_conditions:
    - right_click_detected == true
  # 自动隐藏
  hide_conditions:
    - left_click_detected == true
    - timeout_seconds > 5
```

## 6. 最佳实践总结

### 6.1 性能优化

```yaml
# 使用条件减少不必要的识别
- area_name: 优化示例
  area_type: button
  layer_level: 1
  priority: 5
  # 只在特定条件下进行识别
  show_conditions:
    - screen_active == true
    - ui_visible == true
  # 使用缓存
  custom_properties:
    cache_duration: 1.0  # 缓存1秒
    cache_key: button_state
```

### 6.2 错误处理

```yaml
# 带重试机制的关键按钮
- area_name: 关键确认按钮
  area_type: button
  layer_level: 2
  priority: 15
  pc_rect: [800, 600, 1000, 650]
  text: 确认
  lcs_percent: 0.95  # 高精度匹配
  retry_times: 5     # 重试5次
  wait_after_click: 2.0  # 等待2秒
  # 失败时的备选方案
  custom_properties:
    fallback_template: confirm_button_alt.png
    fallback_threshold: 0.6
```

### 6.3 调试支持

```yaml
# 调试模式配置
- area_name: 调试按钮
  area_type: button
  layer_level: 1
  priority: 1
  pc_rect: [100, 100, 200, 150]
  text: 调试
  # 调试属性
  custom_properties:
    debug_mode: true
    save_screenshots: true
    log_recognition_details: true
    highlight_area: true
```

## 7. 迁移指南

### 7.1 从旧版本升级

旧版本的配置文件无需修改即可正常工作，但建议逐步迁移以获得更好的功能。

#### 旧格式
```yaml
- area_name: 确认按钮
  id_mark: true
  pc_rect: [800, 600, 1000, 650]
  text: 确认
  lcs_percent: 0.8
  goto_list: [主界面]
```

#### 新格式（推荐）
```yaml
- area_name: 确认按钮
  area_type: button
  layer_level: 2
  priority: 10
  id_mark: true
  pc_rect: [800, 600, 1000, 650]
  text: 确认
  lcs_percent: 0.8
  interaction_type: click
  goto_list: [主界面]
  # 新增功能
  show_conditions:
    - dialog_visible == true
  wait_after_click: 1.0
```

### 7.2 常见迁移场景

#### 弹窗识别优化
```yaml
# 旧方式：依赖固定位置
- area_name: 弹窗确认
  pc_rect: [800, 600, 1000, 650]
  text: 确认

# 新方式：使用层级和条件
- area_name: 弹窗确认
  area_type: popup
  layer_level: 2
  priority: 10
  pc_rect: [800, 600, 1000, 650]
  text: 确认
  show_conditions:
    - popup_active == true
```

#### Tab切换优化
```yaml
# 旧方式：每个tab独立配置
- area_name: 背包标签
  pc_rect: [400, 100, 500, 130]
  text: 背包
  goto_list: [背包界面]

# 新方式：使用状态管理
- area_name: 背包标签
  area_type: tab
  layer_level: 1
  pc_rect: [400, 100, 500, 130]
  text: 背包
  current_state: tab_inventory
  state_transitions:
    tab_inventory: [tab_character, tab_settings]
```

### 7.3 性能优化建议

1. **添加显示条件**: 为不常显示的区域添加show_conditions
2. **使用层级管理**: 设置合适的layer_level和priority
3. **启用缓存**: 对稳定的区域启用识别缓存
4. **相对定位**: 对相关联的界面元素使用相对定位

这些示例展示了新ScreenArea模型在各种复杂游戏场景中的应用，包括弹窗处理、tab切换、动态内容识别等。通过合理使用这些功能，可以大大提高游戏自动化的准确性和稳定性。
