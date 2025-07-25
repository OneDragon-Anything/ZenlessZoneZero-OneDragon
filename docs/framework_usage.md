# OneDragon 框架使用文档

## 1. 快速开始

### 1.1 环境要求

- Python 3.11.9 - 3.11.12
- Windows 10/11 (主要支持平台)
- 至少 4GB 内存
- 支持 DirectX 的显卡 (用于 ONNX 推理加速)

### 1.2 安装依赖

\\ash
# 安装核心依赖
pip install -r requirements-prod.txt

# 开发环境依赖 (可选)
pip install -r requirements-dev.txt

# 手柄支持 (可选)
pip install -r requirements-gamepad.txt
\
### 1.3 项目结构

\your_game_project/
 src/
    one_dragon/          # 框架核心
    your_game/           # 游戏特定实现
 config/                  # 配置文件
 assets/                  # 资源文件
    game_data/          # 游戏数据
    models/             # AI模型
    template/           # 模板图片
 requirements.txt        # 依赖列表
\
### 1.4 第一个应用

\\python
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.operation.application_base import Application

class MyGameContext(OneDragonContext):
    def __init__(self):
        super().__init__()
        # 游戏特定的初始化

class MyGameApp(Application):
    def __init__(self, ctx: MyGameContext):
        super().__init__(
            ctx=ctx,
            app_id='my_game_app',
            op_name='我的游戏应用'
        )
    
    def add_edges_and_nodes(self):
        # 定义操作流程
        pass
    
    def handle_init(self):
        # 初始化逻辑
        pass

# 使用示例
if __name__ == '__main__':
    ctx = MyGameContext()
    ctx.init_by_config()
    
    app = MyGameApp(ctx)
    result = app.execute()
    print(f'执行结果: {result.success}')
\
## 2. 核心概念

### 2.1 上下文 (Context)

上下文是框架的核心，管理全局状态和资源：

\\python
class MyGameContext(OneDragonContext):
    def __init__(self):
        super().__init__()
        
        # 游戏特定的服务
        self.game_service = GameService()
        self.battle_service = BattleService()
        
        # 加载游戏配置
        self.load_game_config()
    
    def load_game_config(self):
        # 加载游戏特定配置
        pass
\
### 2.2 操作 (Operation)

操作是执行具体任务的单元：

\\python
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult

class LoginOperation(Operation):
    def __init__(self, ctx: MyGameContext):
        super().__init__(
            ctx=ctx,
            op_name='登录游戏'
        )
    
    def add_edges_and_nodes(self):
        # 定义操作节点和连接关系
        start = self.create_node('开始登录', self.start_login)
        check = self.create_node('检查登录状态', self.check_login_status)
        success = self.create_node('登录成功', self.login_success)
        
        self.add_edge(start, check)
        self.add_edge(check, success, status='已登录')
    
    @operation_node(name='开始登录', is_start_node=True)
    def start_login(self) -> OperationRoundResult:
        # 执行登录逻辑
        screen = self.screenshot()
        
        # 查找登录按钮并点击
        result = self.round_by_find_and_click_area(
            screen, '登录界面', '登录按钮'
        )
        
        if result.is_success:
            return self.round_success('点击登录按钮')
        else:
            return self.round_retry('未找到登录按钮')
    
    @operation_node(name='检查登录状态')
    def check_login_status(self) -> OperationRoundResult:
        screen = self.screenshot()
        
        # 检查是否已经登录
        if self.find_area(screen, '主界面', '主菜单'):
            return self.round_success('已登录')
        else:
            return self.round_retry('等待登录完成')
    
    @operation_node(name='登录成功')
    def login_success(self) -> OperationRoundResult:
        return self.round_success('登录完成')
\
### 2.3 应用 (Application)

应用是完整功能的封装：

\\python
class DailyTaskApp(Application):
    def __init__(self, ctx: MyGameContext):
        super().__init__(
            ctx=ctx,
            app_id='daily_task',
            op_name='每日任务',
            run_record=ctx.daily_task_record,  # 运行记录
            need_notify=True  # 需要通知
        )
    
    def add_edges_and_nodes(self):
        login = self.create_node('登录', self.login)
        daily_tasks = self.create_node('执行每日任务', self.do_daily_tasks)
        logout = self.create_node('退出', self.logout)
        
        self.add_edge(login, daily_tasks)
        self.add_edge(daily_tasks, logout)
    
    @operation_node(name='登录', is_start_node=True)
    def login(self) -> OperationRoundResult:
        op = LoginOperation(self.ctx)
        return self.round_by_op_result(op.execute())
    
    @operation_node(name='执行每日任务')
    def do_daily_tasks(self) -> OperationRoundResult:
        # 执行各种每日任务
        tasks = ['签到', '领取邮件', '完成副本']
        
        for task in tasks:
            result = self.execute_task(task)
            if not result:
                return self.round_fail(f'任务失败: {task}')
        
        return self.round_success('所有任务完成')
    
    def execute_task(self, task_name: str) -> bool:
        # 执行具体任务的逻辑
        return True
\
## 3. 图像识别

### 3.1 OCR 文字识别

\\python
# 在操作中使用 OCR
@operation_node(name='查找文字')
def find_text(self) -> OperationRoundResult:
    screen = self.screenshot()
    
    # 在指定区域查找文字
    result = self.round_by_ocr(
        screen=screen,
        target_cn='确认',
        area=self.ctx.screen_loader.get_area('对话框', '按钮区域'),
        lcs_percent=0.8  # 匹配度阈值
    )
    
    if result.is_success:
        return self.round_success('找到确认按钮')
    else:
        return self.round_retry('未找到确认按钮')

# 查找并点击文字
@operation_node(name='点击文字')
def click_text(self) -> OperationRoundResult:
    screen = self.screenshot()
    
    result = self.round_by_ocr_and_click(
        screen=screen,
        target_cn='开始游戏',
        success_wait=2.0  # 点击后等待2秒
    )
    
    return result
\
### 3.2 模板匹配

\\python
# 使用模板匹配查找图像
@operation_node(name='模板匹配')
def template_match(self) -> OperationRoundResult:
    screen = self.screenshot()
    
    # 查找模板图像
    result = self.round_by_find_area(
        screen=screen,
        screen_name='主界面',
        area_name='设置按钮',
        retry_wait=1.0
    )
    
    return result

# 点击模板匹配的结果
@operation_node(name='点击模板')
def click_template(self) -> OperationRoundResult:
    screen = self.screenshot()
    
    result = self.round_by_find_and_click_area(
        screen=screen,
        screen_name='主界面',
        area_name='背包按钮',
        success_wait=1.0
    )
    
    return result
\
---

本文档提供了 OneDragon 框架的完整使用指南，从基础概念到高级特性，帮助开发者快速上手并深入使用框架进行游戏自动化开发。
