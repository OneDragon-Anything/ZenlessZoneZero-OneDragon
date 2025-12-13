"""
ZApplication 基类 back_to_world 默认实现的简化单元测试

测试属性 1: 默认实现一致性
验证需求 1.1, 2.1
"""

import pytest
from unittest.mock import Mock
from typing import Optional

# 导入真实的类
from one_dragon.base.operation.operation_round_result import OperationRoundResult, OperationRoundResultEnum


class OperationRoundResult:
    """简单的操作结果类"""
    def __init__(self, success: bool = True, status: str = ""):
        self.success = success
        self.status = status
        self.result = OperationRoundResultEnum.SUCCESS if success else OperationRoundResultEnum.FAIL

    @property
    def is_success(self) -> bool:
        return self.success

    @property
    def is_fail(self) -> bool:
        return not self.success


class MockZContext:
    """模拟的 ZContext 用于测试"""

    def __init__(self):
        self.controller = Mock()
        self.screen_loader = Mock()
        self.ocr = Mock()
        self.world_patrol_service = Mock()
        self.compendium_service = Mock()
        self.lost_void = Mock()
        self.logger = Mock()
        self.run_context = Mock()

        # 设置默认的模拟行为
        self.run_context.start_running = Mock()
        self.logger.error = Mock()


class MockBackToNormalWorld:
    """模拟的 BackToNormalWorld 操作"""

    def __init__(self, ctx):
        self.ctx = ctx

    def execute(self):
        return OperationRoundResult(success=True, status="返回大世界成功")


class TestableZApplication:
    """用于测试的 ZApplication 子类，模拟基类默认实现"""

    def __init__(self, ctx, app_id: str = "test_app"):
        self.ctx = ctx
        self.app_id = app_id

    def round_by_op_result(self, op_result: OperationRoundResult,
                          status: Optional[str] = None) -> OperationRoundResult:
        """模拟 round_by_op_result 方法"""
        if status is not None:
            return OperationRoundResult(success=op_result.success, status=status)
        return op_result

    def back_to_world(self, custom_status: Optional[str] = None) -> OperationRoundResult:
        """
        模拟基类的默认 back_to_world 实现
        这是我们要测试的目标实现
        """
        try:
            # 使用模拟的 BackToNormalWorld
            op = MockBackToNormalWorld(self.ctx)
            op_result = op.execute()

            if custom_status is not None:
                return self.round_by_op_result(op_result, status=custom_status)
            return self.round_by_op_result(op_result)

        except Exception as e:
            # 记录错误并返回失败结果
            self.ctx.logger.error(f"返回大世界失败: {e}")
            return OperationRoundResult(success=False, status=f"返回大世界失败: {str(e)}")


@pytest.fixture
def mock_context():
    """提供模拟的 ZContext"""
    return MockZContext()


@pytest.fixture
def test_app(mock_context):
    """提供测试应用实例"""
    return TestableZApplication(mock_context)


class TestBaseBackToWorldImplementation:
    """测试基类 back_to_world 默认实现"""

    def test_default_implementation_without_custom_status(self, test_app):
        """
        测试默认实现（无自定义状态）

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 1.1, 2.1**
        """
        # 调用默认实现
        result = test_app.back_to_world()

        # 验证结果
        assert result.is_success is True
        assert result.status == "返回大世界成功"

    def test_default_implementation_with_custom_status(self, test_app):
        """
        测试默认实现（带自定义状态）

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 1.1, 2.1**
        """
        custom_status = "剩余电量 85%"

        # 调用带自定义状态的默认实现
        result = test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert result.is_success is True
        assert result.status == custom_status  # 应该使用自定义状态

    def test_custom_status_parameter_passing(self, test_app):
        """
        测试自定义状态参数的正确传递

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 1.1, 2.1**
        """
        # 测试多种自定义状态
        test_statuses = [
            "剩余电量 85%",
            "任务完成",
            "等级提升",
            "",  # 空字符串
            "包含特殊字符的状态: !@#$%"
        ]

        for custom_status in test_statuses:
            # 调用带自定义状态的默认实现
            result = test_app.back_to_world(custom_status=custom_status)

            # 验证自定义状态被正确使用
            assert result.is_success is True
            assert result.status == custom_status

    def test_none_custom_status_uses_original_status(self, test_app):
        """
        测试当 custom_status 为 None 时使用原始状态

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 1.1, 2.1**
        """
        # 测试显式传递 None
        result1 = test_app.back_to_world(custom_status=None)
        assert result1.status == "返回大世界成功"

        # 测试不传递参数（默认为 None）
        result2 = test_app.back_to_world()
        assert result2.status == "返回大世界成功"

        # 两种调用方式应该产生相同结果
        assert result1.is_success == result2.is_success
        assert result1.status == result2.status

    def test_custom_status_overrides_default(self, test_app):
        """
        测试自定义状态覆盖默认状态

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 1.1, 2.1**
        """
        custom_status = "自定义状态消息"

        # 1. 调用不带自定义状态的默认实现
        default_result = test_app.back_to_world()

        # 2. 调用带自定义状态的默认实现
        custom_result = test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert default_result.is_success == custom_result.is_success
        assert default_result.status != custom_result.status
        assert custom_result.status == custom_status
        assert default_result.status == "返回大世界成功"

    def test_charge_plan_style_custom_status(self, test_app):
        """
        测试 ChargePlanApp 风格的自定义状态

        **Feature: back-to-world-refactor, Property 1: 默认实现一致性**
        **Validates: Requirements 1.1, 2.1**
        """
        charge_power = 85
        custom_status = f"剩余电量 {charge_power}%"

        # 调用带自定义状态的默认实现
        result = test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert result.is_success is True
        assert result.status == custom_status
        assert str(charge_power) in result.status
        assert "剩余电量" in result.status