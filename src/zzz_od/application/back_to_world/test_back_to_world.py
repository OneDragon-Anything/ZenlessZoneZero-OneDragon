"""
返回大世界应用测试
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from zzz_od.context.zzz_context import ZContext
from zzz_od.application.back_to_world.back_to_world_app import BackToWorldApp


def test_back_to_world_app():
    """测试返回大世界应用"""
    print("初始化上下文...")
    ctx = ZContext()
    ctx.init()
    
    print("创建返回大世界应用...")
    app = BackToWorldApp(ctx)
    
    print(f"应用ID: {app.app_id}")
    print(f"应用名称: {app.op_name}")
    
    print("应用创建成功！")
    print("可以通过 GUI 或命令行启动此应用来返回大世界")


if __name__ == '__main__':
    test_back_to_world_app()
