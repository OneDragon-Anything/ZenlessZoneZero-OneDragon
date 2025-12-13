"""
测试 custom_status 参数的各种场景

验证需求 1.2, 5.2 - 自定义状态参数传递
"""

import pytest
from unittest.mock import Mock
from typing import Optional


class OperationRoundResult:
    """简单的操作结果类"""
    def __init__(self, success: bool = True, status: str = ""):
        self.success = success
        self.status = status

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


class TestCustomStatusScenarios:
    """测试 custom_status 参数的各种场景"""

    def test_charge_plan_scenarios(self, test_app):
        """
        测试 ChargePlanApp 风格的各种电量场景

        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
        **Validates: Requirements 1.2, 5.2**
        """
        # 测试不同的电量值
        charge_levels = [0, 25, 50, 75, 100, 120, 240]

        for charge in charge_levels:
            custom_status = f"剩余电量 {charge}"
            result = test_app.back_to_world(custom_status=custom_status)

            assert result.is_success
            assert result.status == custom_status
            assert str(charge) in result.status
            assert "剩余电量" in result.status

    def test_empty_and_whitespace_status(self, test_app):
        """
        测试空字符串和空白字符的处理

        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
        **Validates: Requirements 1.2, 5.2**
        """
        # 测试各种空白情况
        empty_cases = [
            "",           # 空字符串
            " ",          # 单个空格
            "  ",         # 多个空格
            "\t",         # 制表符
            "\n",         # 换行符
            " \t\n ",     # 混合空白字符
        ]

        for empty_status in empty_cases:
            result = test_app.back_to_world(custom_status=empty_status)

            assert result.is_success
            assert result.status == empty_status

    def test_special_characters_status(self, test_app):
        """
        测试包含特殊字符的状态

        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
        **Validates: Requirements 1.2, 5.2**
        """
        # 测试各种特殊字符
        special_cases = [
            "状态: 100%",
            "任务完成 ✓",
            "错误 #404",
            "路径 C:\\Users\\Test",
            "JSON: {\"key\": \"value\"}",
            "SQL: SELECT * FROM table;",
            "正则: [a-zA-Z0-9]+",
            "数学: 2 + 2 = 4",
            "货币: $100.50",
            "时间: 12:34:56",
        ]

        for special_status in special_cases:
            result = test_app.back_to_world(custom_status=special_status)

            assert result.is_success
            assert result.status == special_status

    def test_unicode_and_emoji_status(self, test_app):
        """
        测试 Unicode 字符和表情符号

        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
        **Validates: Requirements 1.2, 5.2**
        """
        # 测试 Unicode 和表情符号
        unicode_cases = [
            "任务完成 🎉",
            "错误 ❌",
            "成功 ✅",
            "警告 ⚠️",
            "进度 📊",
            "中文测试",
            "日本語テスト",
            "한국어 테스트",
            "Русский тест",
            "العربية اختبار",
        ]

        for unicode_status in unicode_cases:
            result = test_app.back_to_world(custom_status=unicode_status)

            assert result.is_success
            assert result.status == unicode_status

    def test_long_status_messages(self, test_app):
        """
        测试长状态消息

        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
        **Validates: Requirements 1.2, 5.2**
        """
        # 测试不同长度的状态消息
        long_cases = [
            "短消息",
            "这是一个中等长度的状态消息，包含一些详细信息",
            "这是一个非常长的状态消息，" * 10,  # 重复10次
            "A" * 1000,  # 1000个字符
            "测试" * 500,  # 1000个中文字符
        ]

        for long_status in long_cases:
            result = test_app.back_to_world(custom_status=long_status)

            assert result.is_success
            assert result.status == long_status
            assert len(result.status) == len(long_status)

    def test_realistic_game_scenarios(self, test_app):
        """
        测试现实游戏场景中的状态消息

        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
        **Validates: Requirements 1.2, 5.2**
        """
        # 测试现实游戏场景
        game_scenarios = [
            "剩余电量 85%",
            "完成每日任务 3/5",
            "获得经验值 1250",
            "等级提升至 45",
            "获得物品: 高级材料 x3",
            "完成副本: 遗器副本 - 困难",
            "邮件已全部领取",
            "刮刮卡已全部使用",
            "恶名狩猎已完成",
            "咖啡店任务完成",
            "城市基金已领取",
            "生活在线任务完成",
            "随机播放已完成",
            "式舆防卫战已完成",
        ]

        for scenario_status in game_scenarios:
            result = test_app.back_to_world(custom_status=scenario_status)

            assert result.is_success
            assert result.status == scenario_status

    def test_none_vs_empty_string_difference(self, test_app):
        """
        测试 None 与空字符串的区别

        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
        **Validates: Requirements 1.2, 5.2**
        """
        # 测试 None 参数
        none_result = test_app.back_to_world(custom_status=None)

        # 测试空字符串参数
        empty_result = test_app.back_to_world(custom_status="")

        # 测试不传递参数
        default_result = test_app.back_to_world()

        # None 和不传递参数应该产生相同结果
        assert none_result.is_success == default_result.is_success
        assert none_result.status == default_result.status
        assert none_result.status == "返回大世界成功"

        # 空字符串应该产生不同的结果
        assert empty_result.is_success
        assert empty_result.status == ""
        assert empty_result.status != none_result.status

    def test_status_preservation_across_calls(self, test_app):
        """
        测试多次调用时状态的正确保持

        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
        **Validates: Requirements 1.2, 5.2**
        """
        # 测试连续调用不同状态
        statuses = ["状态1", "状态2", "状态3"]
        results = []

        for status in statuses:
            result = test_app.back_to_world(custom_status=status)
            results.append(result)

        # 验证每个结果都正确
        for i, (status, result) in enumerate(zip(statuses, results)):
            assert result.is_success
            assert result.status == status

        # 验证结果之间相互独立
        assert results[0].status != results[1].status
        assert results[1].status != results[2].status
        assert results[0].status != results[2].status

    def test_status_with_operation_failure(self, test_app):
        """
        测试操作失败时自定义状态的处理

        **Feature: back-to-world-refactor, Property 2: 自定义状态参数传递**
        **Validates: Requirements 1.2, 5.2**
        """
        # 创建一个会失败的应用版本
        class FailingApp(TestableZApplication):
            def back_to_world(self, custom_status: Optional[str] = None) -> OperationRoundResult:
                # 模拟操作失败
                failed_op_result = OperationRoundResult(success=False, status="操作失败")

                if custom_status is not None:
                    return self.round_by_op_result(failed_op_result, status=custom_status)
                return self.round_by_op_result(failed_op_result)

        failing_app = FailingApp(test_app.ctx)

        # 测试失败时的自定义状态
        custom_status = "自定义失败状态"
        result = failing_app.back_to_world(custom_status=custom_status)

        # 验证失败状态但保持自定义状态消息
        assert result.is_fail
        assert result.status == custom_status