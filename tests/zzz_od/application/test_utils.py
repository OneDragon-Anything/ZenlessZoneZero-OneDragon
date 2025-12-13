"""
back_to_world 重构测试的工具模块

提供测试过程中需要的各种工具函数和辅助类。
"""

from typing import Dict, Any, List, Optional, Callable
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
import inspect

from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.application.zzz_application import ZApplication


@dataclass
class RefactorTestConfig:
    """重构测试配置"""
    # 可以安全移除的实现（使用默认实现）
    removable_implementations: List[str]

    # 需要转换为参数化调用的实现
    parameterizable_implementations: Dict[str, str]

    # 需要保留自定义逻辑的实现
    preserved_implementations: List[str]


class MockApplicationFactory:
    """模拟应用工厂"""

    @staticmethod
    def create_standard_app(ctx: ZContext, app_name: str) -> ZApplication:
        """创建标准的应用实例（使用默认 back_to_world）"""

        class StandardApp(ZApplication):
            def __init__(self, ctx: ZContext):
                super().__init__(ctx, app_id=app_name.lower())

            def round_by_op_result(self, op_result: OperationRoundResult,
                                 status: Optional[str] = None) -> OperationRoundResult:
                if status is not None:
                    return OperationRoundResult(success=op_result.success, status=status)
                return op_result

        return StandardApp(ctx)

    @staticmethod
    def create_parameterized_app(ctx: ZContext, app_name: str,
                               custom_status: str) -> ZApplication:
        """创建参数化的应用实例（使用自定义状态）"""

        class ParameterizedApp(ZApplication):
            def __init__(self, ctx: ZContext, custom_status: str):
                super().__init__(ctx, app_id=app_name.lower())
                self.custom_status = custom_status

            def round_by_op_result(self, op_result: OperationRoundResult,
                                 status: Optional[str] = None) -> OperationRoundResult:
                if status is not None:
                    return OperationRoundResult(success=op_result.success, status=status)
                return op_result

            def back_to_world(self) -> OperationRoundResult:
                """模拟参数化的 back_to_world 实现"""
                from zzz_od.operation.back_to_normal_world import BackToNormalWorld
                op = BackToNormalWorld(self.ctx)
                op_result = op.execute()
                return self.round_by_op_result(op_result, status=self.custom_status)

        return ParameterizedApp(ctx, custom_status)

    @staticmethod
    def create_special_app(ctx: ZContext, app_name: str,
                         custom_logic: Callable) -> ZApplication:
        """创建特殊逻辑的应用实例"""

        class SpecialApp(ZApplication):
            def __init__(self, ctx: ZContext, custom_logic: Callable):
                super().__init__(ctx, app_id=app_name.lower())
                self.custom_logic = custom_logic

            def round_by_op_result(self, op_result: OperationRoundResult,
                                 status: Optional[str] = None) -> OperationRoundResult:
                if status is not None:
                    return OperationRoundResult(success=op_result.success, status=status)
                return op_result

            def back_to_world(self) -> OperationRoundResult:
                """使用自定义逻辑的 back_to_world 实现"""
                self.custom_logic()
                return OperationRoundResult(success=True, status="特殊逻辑完成")

        return SpecialApp(ctx, custom_logic)


class BackToWorldBehaviorComparator:
    """back_to_world 行为比较器"""

    def __init__(self):
        self.baseline_results: Dict[str, Any] = {}
        self.current_results: Dict[str, Any] = {}

    def capture_baseline(self, app: ZApplication, test_name: str) -> Dict[str, Any]:
        """捕获基准行为"""
        with patch('zzz_od.operation.back_to_normal_world.BackToNormalWorld') as mock_class:
            mock_instance = Mock()
            expected_result = OperationRoundResult(success=True, status="返回大世界成功")
            mock_instance.execute.return_value = expected_result
            mock_class.return_value = mock_instance

            # 执行 back_to_world
            if hasattr(app, 'back_to_world'):
                result = app.back_to_world()
            else:
                # 模拟标准实现
                from zzz_od.operation.back_to_normal_world import BackToNormalWorld
                op = BackToNormalWorld(app.ctx)
                result = app.round_by_op_result(op.execute())

            behavior = {
                'success': result.success,
                'status': result.status,
                'operation_created': mock_class.called,
                'execute_called': mock_instance.execute.called if mock_class.called else False
            }

            self.baseline_results[test_name] = behavior
            return behavior

    def capture_current(self, app: ZApplication, test_name: str) -> Dict[str, Any]:
        """捕获当前行为"""
        with patch('zzz_od.operation.back_to_normal_world.BackToNormalWorld') as mock_class:
            mock_instance = Mock()
            expected_result = OperationRoundResult(success=True, status="返回大世界成功")
            mock_instance.execute.return_value = expected_result
            mock_class.return_value = mock_instance

            # 执行 back_to_world
            result = app.back_to_world()

            behavior = {
                'success': result.success,
                'status': result.status,
                'operation_created': mock_class.called,
                'execute_called': mock_instance.execute.called if mock_class.called else False
            }

            self.current_results[test_name] = behavior
            return behavior

    def compare_behaviors(self, test_name: str) -> Dict[str, Any]:
        """比较基准和当前行为"""
        baseline = self.baseline_results.get(test_name, {})
        current = self.current_results.get(test_name, {})

        comparison = {
            'equivalent': baseline == current,
            'differences': {},
            'baseline': baseline,
            'current': current
        }

        # 找出差异
        all_keys = set(baseline.keys()) | set(current.keys())
        for key in all_keys:
            baseline_val = baseline.get(key)
            current_val = current.get(key)
            if baseline_val != current_val:
                comparison['differences'][key] = {
                    'baseline': baseline_val,
                    'current': current_val
                }

        return comparison


class TestDataGenerator:
    """测试数据生成器"""

    @staticmethod
    def generate_custom_status_examples() -> List[str]:
        """生成自定义状态示例"""
        return [
            "剩余电量 85%",
            "剩余电量 42%",
            "剩余电量 100%",
            "任务完成",
            "操作成功",
            "返回大世界",
            "特殊状态消息",
            "自定义状态 123"
        ]

    @staticmethod
    def generate_app_configurations() -> RefactorTestConfig:
        """生成应用配置"""
        return RefactorTestConfig(
            removable_implementations=[
                'EmailApp', 'ScratchCardApp', 'RandomPlayApp',
                'NotoriousHuntApp', 'LifeOnLineApp', 'CityFundApp', 'CoffeeApp'
            ],
            parameterizable_implementations={
                'ChargePlanApp': 'f"剩余电量 {self.charge_power}"'
            },
            preserved_implementations=[
                'TransportByCompendium', 'LostVoidLottery', 'LostVoidRouteChange'
            ]
        )


class MockContextBuilder:
    """模拟上下文构建器"""

    def __init__(self):
        self.ctx = Mock(spec=ZContext)
        self._setup_default_mocks()

    def _setup_default_mocks(self):
        """设置默认的模拟行为"""
        self.ctx.controller = Mock()
        self.ctx.screen_loader = Mock()
        self.ctx.ocr = Mock()
        self.ctx.world_patrol_service = Mock()
        self.ctx.compendium_service = Mock()
        self.ctx.lost_void = Mock()
        self.ctx.logger = Mock()
        self.ctx.run_context = Mock()

        # 设置默认行为
        self.ctx.run_context.start_running = Mock()
        self.ctx.logger.error = Mock()

    def with_controller(self, controller_mock: Mock) -> 'MockContextBuilder':
        """设置控制器模拟"""
        self.ctx.controller = controller_mock
        return self

    def with_logger(self, logger_mock: Mock) -> 'MockContextBuilder':
        """设置日志模拟"""
        self.ctx.logger = logger_mock
        return self

    def build(self) -> ZContext:
        """构建模拟上下文"""
        return self.ctx


def create_test_suite_summary() -> Dict[str, List[str]]:
    """创建测试套件摘要"""
    return {
        'infrastructure_tests': [
            'test_mock_context_creation',
            'test_testable_application_creation',
            'test_mock_operation_result_creation'
        ],
        'baseline_tests': [
            'test_baseline_standard_behavior',
            'test_baseline_custom_status_behavior'
        ],
        'property_tests': [
            'test_default_implementation_consistency',
            'test_custom_status_parameter_passing',
            'test_subclass_override_independence',
            'test_refactor_behavior_equivalence'
        ],
        'integration_tests': [
            'test_all_applications_back_to_world',
            'test_special_implementations_preserved'
        ]
    }


def validate_test_environment() -> Dict[str, bool]:
    """验证测试环境"""
    validation_results = {}

    try:
        # 检查必要的导入
        from zzz_od.context.zzz_context import ZContext
        validation_results['zzz_context_import'] = True
    except ImportError:
        validation_results['zzz_context_import'] = False

    try:
        from zzz_od.application.zzz_application import ZApplication
        validation_results['zzz_application_import'] = True
    except ImportError:
        validation_results['zzz_application_import'] = False

    try:
        from zzz_od.operation.back_to_normal_world import BackToNormalWorld
        validation_results['back_to_normal_world_import'] = True
    except ImportError:
        validation_results['back_to_normal_world_import'] = False

    try:
        from one_dragon.base.operation.operation_round_result import OperationRoundResult
        validation_results['operation_round_result_import'] = True
    except ImportError:
        validation_results['operation_round_result_import'] = False

    return validation_results


if __name__ == "__main__":
    # 验证测试环境
    results = validate_test_environment()
    print("测试环境验证结果:")
    for component, status in results.items():
        status_text = "✓" if status else "✗"
        print(f"  {status_text} {component}")

    # 生成测试数据示例
    generator = TestDataGenerator()
    config = generator.generate_app_configurations()
    print(f"\n应用配置:")
    print(f"  可移除实现: {len(config.removable_implementations)} 个")
    print(f"  参数化实现: {len(config.parameterizable_implementations)} 个")
    print(f"  保留实现: {len(config.preserved_implementations)} 个")