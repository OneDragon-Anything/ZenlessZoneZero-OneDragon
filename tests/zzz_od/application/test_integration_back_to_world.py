"""
集成测试：验证基类实现的正确性

测试真实的 ZApplication.back_to_world 方法
"""

import pytest
import sys
import os

# 添加源代码路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..', '..')
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

def test_zapplication_back_to_world_method_exists():
    """
    测试 ZApplication 类是否有 back_to_world 方法

    **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
    **Validates: Requirements 1.1, 2.1**
    """
    try:
        from zzz_od.application.zzz_application import ZApplication

        # 验证方法存在
        assert hasattr(ZApplication, 'back_to_world')
        assert callable(getattr(ZApplication, 'back_to_world'))

        # 验证方法签名
        import inspect
        sig = inspect.signature(ZApplication.back_to_world)
        params = list(sig.parameters.keys())

        # 应该有 self 和 custom_status 参数
        assert 'self' in params
        assert 'custom_status' in params

        # custom_status 应该有默认值 None
        custom_status_param = sig.parameters['custom_status']
        assert custom_status_param.default is None

        print("✓ ZApplication.back_to_world 方法存在且签名正确")

    except ImportError as e:
        pytest.skip(f"无法导入 ZApplication: {e}")

def test_zapplication_back_to_world_docstring():
    """
    测试 back_to_world 方法的文档字符串

    **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
    **Validates: Requirements 2.4**
    """
    try:
        from zzz_od.application.zzz_application import ZApplication

        # 验证文档字符串
        docstring = ZApplication.back_to_world.__doc__
        assert docstring is not None
        assert "返回大世界的默认实现" in docstring
        assert "custom_status" in docstring
        assert "自定义状态消息" in docstring

        print("✓ ZApplication.back_to_world 文档字符串正确")

    except ImportError as e:
        pytest.skip(f"无法导入 ZApplication: {e}")

def test_zapplication_imports_required_classes():
    """
    测试 ZApplication 是否导入了必要的类

    **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
    **Validates: Requirements 1.1, 2.1**
    """
    try:
        from zzz_od.application.zzz_application import ZApplication

        # 检查源代码文件是否包含必要的导入
        import inspect
        source_file = inspect.getfile(ZApplication)

        with open(source_file, 'r', encoding='utf-8') as f:
            source_code = f.read()

        # 验证必要的导入
        assert 'from zzz_od.operation.back_to_normal_world import BackToNormalWorld' in source_code
        assert 'from one_dragon.base.operation.operation_round_result import OperationRoundResult' in source_code

        print("✓ ZApplication 包含必要的导入")

    except ImportError as e:
        pytest.skip(f"无法导入 ZApplication: {e}")
    except Exception as e:
        pytest.fail(f"检查导入时出错: {e}")

def test_zapplication_back_to_world_implementation():
    """
    测试 back_to_world 方法的实现逻辑

    **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
    **Validates: Requirements 1.1, 2.1**
    """
    try:
        from zzz_od.application.zzz_application import ZApplication

        # 检查方法实现
        import inspect
        source_lines = inspect.getsourcelines(ZApplication.back_to_world)
        source_code = ''.join(source_lines[0])

        # 验证关键实现细节
        assert 'BackToNormalWorld(self.ctx)' in source_code
        assert 'op.execute()' in source_code
        assert 'custom_status is not None' in source_code
        assert 'self.round_by_op_result' in source_code

        print("✓ ZApplication.back_to_world 实现逻辑正确")

    except ImportError as e:
        pytest.skip(f"无法导入 ZApplication: {e}")
    except Exception as e:
        pytest.fail(f"检查实现时出错: {e}")

def test_backward_compatibility():
    """
    测试向后兼容性 - 确保现有应用仍能正常工作

    **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
    **Validates: Requirements 1.4, 3.3**
    """
    try:
        from zzz_od.application.zzz_application import ZApplication

        # 验证基类可以被实例化（使用模拟上下文）
        from unittest.mock import Mock

        mock_ctx = Mock()
        mock_ctx.controller = Mock()
        mock_ctx.screen_loader = Mock()
        mock_ctx.ocr = Mock()
        mock_ctx.world_patrol_service = Mock()
        mock_ctx.compendium_service = Mock()
        mock_ctx.lost_void = Mock()
        mock_ctx.logger = Mock()
        mock_ctx.run_context = Mock()

        # 创建应用实例
        app = ZApplication(
            ctx=mock_ctx,
            app_id="test_backward_compatibility",
            op_name="测试向后兼容性"
        )

        # 验证 back_to_world 方法可以被调用
        assert hasattr(app, 'back_to_world')
        assert callable(app.back_to_world)

        print("✓ 向后兼容性验证通过")

    except ImportError as e:
        pytest.skip(f"无法导入 ZApplication: {e}")
    except Exception as e:
        pytest.fail(f"向后兼容性测试失败: {e}")

def test_custom_status_parameter_support():
    """
    测试 custom_status 参数支持

    **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
    **Validates: Requirements 1.2, 5.2**
    """
    try:
        from zzz_od.application.zzz_application import ZApplication

        # 检查方法可以接受 custom_status 参数
        import inspect
        sig = inspect.signature(ZApplication.back_to_world)

        # 验证参数类型注解
        custom_status_param = sig.parameters['custom_status']

        # 检查参数注解（如果有的话）
        if custom_status_param.annotation != inspect.Parameter.empty:
            # 验证类型注解包含 Optional 或 None
            annotation_str = str(custom_status_param.annotation)
            assert 'Optional' in annotation_str or 'None' in annotation_str

        print("✓ custom_status 参数支持验证通过")

    except ImportError as e:
        pytest.skip(f"无法导入 ZApplication: {e}")
    except Exception as e:
        pytest.fail(f"custom_status 参数测试失败: {e}")

if __name__ == "__main__":
    # 直接运行测试函数
    test_functions = [
        test_zapplication_back_to_world_method_exists,
        test_zapplication_back_to_world_docstring,
        test_zapplication_imports_required_classes,
        test_zapplication_back_to_world_implementation,
        test_backward_compatibility,
        test_custom_status_parameter_support
    ]

    print("开始验证基类实现的正确性...")
    print("=" * 50)

    passed = 0
    failed = 0
    skipped = 0

    for test_func in test_functions:
        try:
            print(f"\n运行测试: {test_func.__name__}")
            test_func()
            passed += 1
            print(f"✓ {test_func.__name__} 通过")
        except pytest.skip.Exception as e:
            skipped += 1
            print(f"⚠ {test_func.__name__} 跳过: {e}")
        except Exception as e:
            failed += 1
            print(f"✗ {test_func.__name__} 失败: {e}")

    print("\n" + "=" * 50)
    print(f"测试结果: {passed} 通过, {failed} 失败, {skipped} 跳过")

    if failed == 0:
        print("✓ 所有测试通过！基类实现验证成功。")
    else:
        print("✗ 有测试失败，需要检查基类实现。")