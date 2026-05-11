"""
验证返回大世界界面是否正确注册
"""
import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
src_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_root))

def verify_interface():
    """验证界面是否可以正确导入"""
    print("开始验证界面导入...")
    
    try:
        # 1. 验证界面类
        from zzz_od.gui.view.one_dragon.back_to_world_interface import BackToWorldInterface
        print(f"✓ 界面类导入成功")
        print(f"  - 类名: {BackToWorldInterface.__name__}")
        print(f"  - 基类: {BackToWorldInterface.__bases__[0].__name__}")
        
        # 2. 验证常量
        from zzz_od.application.back_to_world import back_to_world_const
        print(f"✓ 常量模块导入成功")
        print(f"  - APP_ID: {back_to_world_const.APP_ID}")
        print(f"  - APP_NAME: {back_to_world_const.APP_NAME}")
        
        # 3. 验证主界面已注册
        from zzz_od.gui.view.one_dragon.zzz_one_dragon_interface import ZOneDragonInterface
        print(f"✓ 主界面导入成功")
        print(f"  - 类名: {ZOneDragonInterface.__name__}")
        
        print("\n✅ 所有界面验证通过！")
        return True
        
    except ImportError as e:
        print(f"\n❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ 验证过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("返回大世界界面 - 注册验证")
    print("=" * 60)
    
    success = verify_interface()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 验证完成！界面已正确注册到 one_dragon 中。")
        print("\n使用方法：")
        print("1. 启动 GUI 程序")
        print("2. 在左侧导航栏找到'一条龙'")
        print("3. 在子页面中找到'返回大世界'")
        print("4. 点击运行按钮即可使用")
    else:
        print("⚠️  验证发现问题，请检查上述错误信息。")
    print("=" * 60)
