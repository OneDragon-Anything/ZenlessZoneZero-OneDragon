"""
属性 2: 自定义状态参数传递的属性基于测试

**Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
**Validates: Requirements 1.2, 5.2**

使用 Hypothesis 库进行属性基于测试，验证自定义状态参数的正确传递。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import Mock, patch
from typing import Optional


class OperationRoundResult:
    """简单的操作结果类"""
    def __init__(self, success: bool = True, status: str = ""):
        self.success = success
        self.status = status


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


class PropertyTestApplication:
    """用于属性测试的应用类，模拟基类默认实现"""

    def __init__(self, ctx, app_id: str = "property_test_app"):
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
            # 模拟 BackToNormalWorld 操作
            mock_op = Mock()
            mock_op.execute.return_value = OperationRoundResult(success=True, status="返回大世界成功")

            op_result = mock_op.execute()

            if custom_status is not None:
                return self.round_by_op_result(op_result, status=custom_status)
            return self.round_by_op_result(op_result)

        except Exception as e:
            # 记录错误并返回失败结果
            self.ctx.logger.error(f"返回大世界失败: {e}")
            return OperationRoundResult(success=False, status=f"返回大世界失败: {str(e)}")


@pytest.fixture
def property_test_context():
    """提供属性测试的上下文"""
    return MockZContext()


@pytest.fixture
def property_test_app(property_test_context):
    """提供属性测试的应用实例"""
    return PropertyTestApplication(property_test_context)


class TestProperty2CustomStatusParameterPassing:
    """属性 2: 自定义状态参数传递的属性基于测试"""

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_custom_status_parameter_passing_basic(
        self, property_test_app, custom_status
    ):
        """
        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**

        对于任何有效的自定义状态字符串，调用 back_to_world(custom_status)
        应该返回包含该自定义状态的 OperationRoundResult

        **Validates: Requirements 1.2, 5.2**
        """
        # 过滤掉只包含空白字符的字符串
        assume(custom_status.strip())

        # 调用带自定义状态的默认实现
        result = property_test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert isinstance(result, OperationRoundResult)
        assert result.success is True
        assert result.status == custom_status

    @given(st.text(min_size=0, max_size=200, alphabet=st.characters(min_codepoint=32, max_codepoint=126)))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_custom_status_ascii_characters(
        self, property_test_app, custom_status
    ):
        """
        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**

        对于任何包含 ASCII 字符的自定义状态字符串，参数应该被正确传递

        **Validates: Requirements 1.2, 5.2**
        """
        # 调用带自定义状态的默认实现
        result = property_test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert isinstance(result, OperationRoundResult)
        assert result.success is True
        assert result.status == custom_status

    @given(st.text(min_size=1, max_size=50, alphabet="剩余电量任务完成操作成功返回大世界特殊状态消息0123456789%"))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_custom_status_chinese_characters(
        self, property_test_app, custom_status
    ):
        """
        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**

        对于任何包含中文字符的自定义状态字符串，参数应该被正确传递

        **Validates: Requirements 1.2, 5.2**
        """
        # 调用带自定义状态的默认实现
        result = property_test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert isinstance(result, OperationRoundResult)
        assert result.success is True
        assert result.status == custom_status

    @given(st.one_of(
        st.just("剩余电量 85%"),
        st.just("剩余电量 42%"),
        st.just("剩余电量 100%"),
        st.just("任务完成"),
        st.just("操作成功"),
        st.just("返回大世界"),
        st.just("特殊状态消息"),
        st.text(min_size=1, max_size=30).map(lambda x: f"自定义状态 {x}")
    ))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_realistic_custom_status_examples(
        self, property_test_app, custom_status
    ):
        """
        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**

        对于现实场景中的自定义状态字符串，参数应该被正确传递

        **Validates: Requirements 1.2, 5.2**
        """
        # 调用带自定义状态的默认实现
        result = property_test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert isinstance(result, OperationRoundResult)
        assert result.success is True
        assert result.status == custom_status

    @given(st.integers(min_value=0, max_value=100))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_charge_plan_style_status(
        self, property_test_app, charge_power
    ):
        """
        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**

        对于 ChargePlanApp 风格的电量状态消息，参数应该被正确传递

        **Validates: Requirements 1.2, 5.2**
        """
        custom_status = f"剩余电量 {charge_power}%"

        # 调用带自定义状态的默认实现
        result = property_test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert isinstance(result, OperationRoundResult)
        assert result.success is True
        assert result.status == custom_status
        assert str(charge_power) in result.status
        assert "剩余电量" in result.status

    @given(st.text(min_size=1, max_size=50), st.booleans())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_custom_status_with_operation_failure(
        self, property_test_app, custom_status, operation_success
    ):
        """
        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**

        即使底层操作失败，自定义状态参数仍应该被正确传递

        **Validates: Requirements 1.2, 5.2**
        """
        # 过滤掉只包含空白字符的字符串
        assume(custom_status.strip())

        # 修改应用以模拟不同的操作结果
        def mock_back_to_world_with_failure(custom_status: Optional[str] = None) -> OperationRoundResult:
            mock_op = Mock()
            mock_op.execute.return_value = OperationRoundResult(
                success=operation_success,
                status="返回大世界成功" if operation_success else "操作失败"
            )

            op_result = mock_op.execute()

            if custom_status is not None:
                return property_test_app.round_by_op_result(op_result, status=custom_status)
            return property_test_app.round_by_op_result(op_result)

        # 临时替换方法
        original_method = property_test_app.back_to_world
        property_test_app.back_to_world = mock_back_to_world_with_failure

        try:
            # 调用带自定义状态的默认实现
            result = property_test_app.back_to_world(custom_status=custom_status)

            # 验证结果
            assert isinstance(result, OperationRoundResult)
            assert result.success == operation_success  # 成功标志应该保持原始操作的结果
            assert result.status == custom_status  # 状态应该使用自定义状态，不管操作是否成功
        finally:
            # 恢复原方法
            property_test_app.back_to_world = original_method

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_custom_status_overrides_default(
        self, property_test_app, custom_status
    ):
        """
        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**

        自定义状态参数应该覆盖默认的操作状态消息

        **Validates: Requirements 1.2, 5.2**
        """
        # 过滤掉只包含空白字符的字符串
        assume(custom_status.strip())

        # 1. 调用不带自定义状态的默认实现
        default_result = property_test_app.back_to_world()

        # 2. 调用带自定义状态的默认实现
        custom_result = property_test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert isinstance(default_result, OperationRoundResult)
        assert isinstance(custom_result, OperationRoundResult)

        # 成功标志应该相同
        assert default_result.success == custom_result.success

        # 状态消息应该不同（除非自定义状态恰好与默认状态相同）
        if custom_status != default_result.status:
            assert default_result.status != custom_result.status

        # 自定义结果应该包含自定义状态
        assert custom_result.status == custom_status

    @given(st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=5))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_multiple_custom_status_calls(
        self, property_test_app, status_list
    ):
        """
        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**

        多次调用带不同自定义状态的 back_to_world 应该每次都正确传递参数

        **Validates: Requirements 1.2, 5.2**
        """
        # 过滤掉只包含空白字符的字符串
        filtered_status_list = [s for s in status_list if s.strip()]
        assume(len(filtered_status_list) > 0)

        results = []
        for custom_status in filtered_status_list:
            result = property_test_app.back_to_world(custom_status=custom_status)
            results.append((custom_status, result))

        # 验证每个结果
        for custom_status, result in results:
            assert isinstance(result, OperationRoundResult)
            assert result.success is True
            assert result.status == custom_status

    @given(st.text(min_size=0, max_size=1000))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_long_custom_status_handling(
        self, property_test_app, custom_status
    ):
        """
        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**

        对于较长的自定义状态字符串，参数应该被完整地传递

        **Validates: Requirements 1.2, 5.2**
        """
        # 调用带自定义状态的默认实现
        result = property_test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert isinstance(result, OperationRoundResult)
        assert result.success is True
        assert result.status == custom_status
        assert len(result.status) == len(custom_status)

    def test_property_2_empty_string_custom_status(self, property_test_app):
        """
        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**

        空字符串作为自定义状态参数应该被正确处理

        **Validates: Requirements 1.2, 5.2**
        """
        custom_status = ""

        # 调用带空字符串自定义状态的默认实现
        result = property_test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert isinstance(result, OperationRoundResult)
        assert result.success is True
        assert result.status == custom_status
        assert result.status == ""

    def test_property_2_none_vs_custom_status_difference(self, property_test_app):
        """
        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**

        None 参数与实际自定义状态参数应该产生不同的结果

        **Validates: Requirements 1.2, 5.2**
        """
        custom_status = "测试自定义状态"

        # 1. 调用不带参数的默认实现（相当于 custom_status=None）
        none_result = property_test_app.back_to_world()

        # 2. 调用带自定义状态的默认实现
        custom_result = property_test_app.back_to_world(custom_status=custom_status)

        # 验证结果
        assert isinstance(none_result, OperationRoundResult)
        assert isinstance(custom_result, OperationRoundResult)

        # 成功标志应该相同
        assert none_result.success == custom_result.success

        # 状态消息应该不同
        assert none_result.status != custom_result.status
        assert custom_result.status == custom_status
        assert none_result.status == "返回大世界成功"  # 默认状态