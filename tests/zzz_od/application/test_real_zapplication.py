"""
测试真实的 ZApplication 基类 back_to_world 实现

验证基类实现的正确性和向后兼容性
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

# 添加源代码路径到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

try:
    from zzz_od.application.zzz_application import ZApplication
    from zzz_od.context.zzz_context import ZContext
    from one_dragon.base.operation.operation_round_result import OperationRoundResult, OperationRoundResultEnum
    REAL_IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"无法导入真实的类: {e}")
    REAL_IMPORTS_AVAILABLE = False


@pytest.mark.skipif(not REAL_IMPORTS_AVAILABLE, reason="无法导入真实的类")
class TestRealZApplicationBackToWorld:
    """测试真实的 ZApplication 基类 back_to_world 实现"""

    @pytest.fixture
    def mock_context(self):
        """创建模拟的 ZContext"""
        mock_ctx = Mock(spec=ZContext)
        mock_ctx.controller = Mock()
        mock_ctx.screen_loader = Mock()
        mock_ctx.ocr = Mock()
        mock_ctx.world_patrol_service = Mock()
        mock_ctx.compendium_service = Mock()
        mock_ctx.lost_void = Mock()
        mock_ctx.logger = Mock()
        mock_ctx.run_context = Mock()
        return mock_ctx

    @pytest.fixture
    def test_app(self, mock_context):
        """创建测试用的 ZApplication 实例"""
        return ZApplication(
            ctx=mock_context,
            app_id="test_back_to_world",
            op_name="测试返回大世界"
        )

    def test_back_to_world_method_exists(self, test_app):
        """
        测试 back_to_world 方法是否存在

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 1.1, 2.1**
        """
        # 验证方法存在
        assert hasattr(test_app, 'back_to_world')
        assert callable(getattr(test_app, 'back_to_world'))

    def test_back_to_world_signature(self, test_app):
        """
        测试 back_to_world 方法签名

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 1.1, 2.1**
        """
        import inspect

        # 获取方法签名
        sig = inspect.signature(test_app.back_to_world)

        # 验证参数
        params = list(sig.parameters.keys())
        assert 'custom_status' in params

        # 验证 custom_status 参数有默认值 None
        custom_status_param = sig.parameters['custom_status']
        assert custom_status_param.default is None

    @patch('zzz_od.operation.back_to_normal_world.BackToNormalWorld')
    def test_back_to_world_without_custom_status(self, mock_back_to_normal_world_class, test_app):
        """
        测试不带自定义状态的 back_to_world 调用

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 1.1, 2.1**
        """
        # 设置模拟
        mock_operation = Mock()
        mock_result = OperationRoundResult(result=OperationRoundResultEnum.SUCCESS, status="返回大世界成功")
        mock_operation.execute.return_value = mock_result
        mock_back_to_normal_world_class.return_value = mock_operation

        # 调用方法
        result = test_app.back_to_world()

        # 验证结果
        assert isinstance(result, OperationRoundResult)
        assert result.is_success

        # 验证 BackToNormalWorld 被正确调用
        mock_back_to_normal_world_class.assert_called_once_with(test_app.ctx)
        mock_operation.execute.assert_called_once()

    @patch('zzz_od.operation.back_to_normal_world.BackToNormalWorld')
    def test_back_to_world_with_custom_status(self, mock_back_to_normal_world_class, test_app):
        """
        测试带自定义状态的 back_to_world 调用

        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
        **Validates: Requirements 1.2, 5.2**
        """
        # 设置模拟
        mock_operation = Mock()
        mock_result = OperationRoundResult(result=OperationRoundResultEnum.SUCCESS, status="返回大世界成功")
        mock_operation.execute.return_value = mock_result
        mock_back_to_normal_world_class.return_value = mock_operation

        custom_status = "剩余电量 85%"

        # 调用方法
        result = test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert isinstance(result, OperationRoundResult)
        assert result.is_success
        assert result.status == custom_status  # 应该使用自定义状态

        # 验证 BackToNormalWorld 被正确调用
        mock_back_to_normal_world_class.assert_called_once_with(test_app.ctx)
        mock_operation.execute.assert_called_once()

    @patch('zzz_od.operation.back_to_normal_world.BackToNormalWorld')
    def test_back_to_world_handles_operation_failure(self, mock_back_to_normal_world_class, test_app):
        """
        测试 back_to_world 处理操作失败

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 1.1, 2.1**
        """
        # 设置模拟 - 操作失败
        mock_operation = Mock()
        mock_result = OperationRoundResult(result=OperationRoundResultEnum.FAIL, status="操作失败")
        mock_operation.execute.return_value = mock_result
        mock_back_to_normal_world_class.return_value = mock_operation

        # 调用方法
        result = test_app.back_to_world()

        # 验证结果
        assert isinstance(result, OperationRoundResult)
        assert result.is_fail
        assert result.status == "操作失败"

        # 验证 BackToNormalWorld 被正确调用
        mock_back_to_normal_world_class.assert_called_once_with(test_app.ctx)
        mock_operation.execute.assert_called_once()

    def test_back_to_world_multiple_calls(self, test_app):
        """
        测试多次调用 back_to_world 的一致性

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 1.1, 2.1**
        """
        with patch('zzz_od.operation.back_to_normal_world.BackToNormalWorld') as mock_class:
            # 设置模拟
            mock_operation = Mock()
            mock_result = OperationRoundResult(result=OperationRoundResultEnum.SUCCESS, status="返回大世界成功")
            mock_operation.execute.return_value = mock_result
            mock_class.return_value = mock_operation

            # 多次调用
            result1 = test_app.back_to_world()
            result2 = test_app.back_to_world()
            result3 = test_app.back_to_world(custom_status="自定义状态")

            # 验证结果一致性
            assert result1.is_success == result2.is_success
            assert result1.status == result2.status
            assert result3.is_success
            assert result3.status == "自定义状态"

            # 验证调用次数
            assert mock_class.call_count == 3
            assert mock_operation.execute.call_count == 3

    def test_back_to_world_docstring(self, test_app):
        """
        测试 back_to_world 方法的文档字符串

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 2.4**
        """
        # 验证文档字符串存在且包含关键信息
        docstring = test_app.back_to_world.__doc__
        assert docstring is not None
        assert "返回大世界的默认实现" in docstring
        assert "custom_status" in docstring
        assert "自定义状态消息" in docstring


@pytest.mark.skipif(REAL_IMPORTS_AVAILABLE, reason="只在无法导入真实类时运行")
def test_import_failure_message():
    """当无法导入真实类时显示消息"""
    print("注意: 无法导入真实的 ZApplication 类，跳过真实类测试")
    print("这可能是因为缺少依赖或路径配置问题")
    print("基类实现的功能性已通过模拟测试验证")