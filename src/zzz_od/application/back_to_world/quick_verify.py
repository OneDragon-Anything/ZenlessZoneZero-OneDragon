"""
快速验证脚本 - 检查返回大世界应用是否可以被正确导入
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

def verify_imports():
    """验证所有必要的导入是否成功"""
    print("开始验证导入...")
    
    try:
        # 1. 验证常量模块
        from zzz_od.application.back_to_world import back_to_world_const
        print(f"✓ 常量模块导入成功")
        print(f"  - APP_ID: {back_to_world_const.APP_ID}")
        print(f"  - APP_NAME: {back_to_world_const.APP_NAME}")
        print(f"  - DEFAULT_GROUP: {back_to_world_const.DEFAULT_GROUP}")
        print(f"  - NEED_NOTIFY: {back_to_world_const.NEED_NOTIFY}")
        
        # 2. 验证应用类
        from zzz_od.application.back_to_world.back_to_world_app import BackToWorldApp
        print(f"✓ 应用类导入成功")
        print(f"  - 类名: {BackToWorldApp.__name__}")
        print(f"  - 基类: {BackToWorldApp.__bases__[0].__name__}")
        
        # 3. 验证工厂类
        from zzz_od.application.back_to_world.back_to_world_app_factory import BackToWorldAppFactory
        print(f"✓ 工厂类导入成功")
        print(f"  - 类名: {BackToWorldAppFactory.__name__}")
        print(f"  - 基类: {BackToWorldAppFactory.__bases__[0].__name__}")
        
        # 4. 验证运行记录类
        from zzz_od.application.back_to_world.back_to_world_run_record import BackToWorldRunRecord
        print(f"✓ 运行记录类导入成功")
        print(f"  - 类名: {BackToWorldRunRecord.__name__}")
        print(f"  - 基类: {BackToWorldRunRecord.__bases__[0].__name__}")
        
        # 5. 验证核心操作
        from zzz_od.operation.back_to_normal_world import BackToNormalWorld
        print(f"✓ 核心操作导入成功")
        print(f"  - 类名: {BackToNormalWorld.__name__}")
        
        print("\n✅ 所有导入验证通过！")
        return True
        
    except ImportError as e:
        print(f"\n❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 验证过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_file_structure():
    """验证文件结构是否完整"""
    print("\n验证文件结构...")
    
    required_files = [
        "__init__.py",
        "back_to_world_const.py",
        "back_to_world_app.py",
        "back_to_world_app_factory.py",
        "back_to_world_run_record.py",
    ]
    
    app_dir = Path(__file__).parent
    
    all_exist = True
    for file_name in required_files:
        file_path = app_dir / file_name
        if file_path.exists():
            print(f"  ✓ {file_name}")
        else:
            print(f"  ✗ {file_name} (缺失)")
            all_exist = False
    
    if all_exist:
        print("✅ 文件结构验证通过！")
    else:
        print("❌ 文件结构不完整！")
    
    return all_exist


if __name__ == '__main__':
    print("=" * 60)
    print("返回大世界应用 - 快速验证")
    print("=" * 60)
    
    structure_ok = verify_file_structure()
    imports_ok = verify_imports()
    
    print("\n" + "=" * 60)
    if structure_ok and imports_ok:
        print("🎉 验证完成！应用已正确创建，可以使用。")
    else:
        print("⚠️  验证发现问题，请检查上述错误信息。")
    print("=" * 60)
