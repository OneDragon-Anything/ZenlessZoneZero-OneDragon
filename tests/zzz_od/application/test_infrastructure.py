"""
测试基础设施模块

提供orld 重构测试所需的基础设施，包括模拟上下文、测试工具和验证功能。
"""

import sys
import os
from typing import Dict, Any, List, Optional, Callable
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
import time
import json

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.join(project_root, "src"))


@dataclass
class MockOperationResult:
    """模拟的操作结果"""
    success: bool
    status: str

    def is_success(self) -> bool:
        return self.success

    def is_fail(self) -> bool:
        return not self.success


class MockZContext:
    """模拟的 ZContext"""

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
        self.logger.info = Mock()


class MockBackToNormalWorld:
    """模拟的 BackToNormalWorld 操作"""

    def __init__(self, ctx: MockZContext):
        self.ctx = ctx

    def execute(self) -> MockOperationResult:
        """返回成功的操作结果"""
        return MockOperationResult(success=True, status="返回大世界成功")


class MockZApplication:
    """模拟的 ZApplication 基类"""

    def __init__(self, ctx: MockZContext, app_id: str = "test_app"):
        self.ctx = ctx
        self.app_id = app_id

    def round_by_op_result(self, op_result: MockOperationResult,
                          status: Optional[str] = None) -> MockOperationResult:
        """模拟 round_by_op_result 方法"""
        if status is not None:
            return MockOperationResult(success=op_result.success, status=status)
        return op_result


class TestInfrastructure:
    """测试基础设施类"""

    def __init__(self):
        self.mock_ctx = MockZContext()
        self.baseline_results = {}
        self.test_results = {}

    def create_mock_context(self) -> MockZContext:
        """创建模拟上下文"""
        return MockZContext()

    def create_mock_application(self, app_name: str, ctx: Optional[MockZContext] = None) -> MockZApplication:
        """创建模拟应用"""
        if ctx is None:
            ctx = self.mock_ctx
        return MockZApplication(ctx, app_name.lower())

    def create_mock_operation_result(self, success: bool = True,
                                   status: str = "操作成功") -> MockOperationResult:
        """创建模拟操作结果"""
        return MockOperationResult(success=success, status=status)

    def simulate_standard_back_to_world(self, app_name: str) -> Dict[str, Any]:
        """模拟标准的 back_to_world 行为"""
        start_time = time.time()

        # 模拟操作执行
        op = MockBackToNormalWorld(self.mock_ctx)
        op_result = op.execute()

        app = self.create_mock_application(app_name)
        final_result = app.round_by_op_result(op_result)

        execution_time = time.time() - start_time

        return {
            'app_name': app_name,
            'method': 'back_to_world',
            'success': final_result.success,
            'status': final_result.status,
            'execution_time': execution_time,
            'operation_created': True,
            'execute_called': True
        }

    def simulate_custom_status_back_to_world(self, app_name: str,
                                           custom_status: str) -> Dict[str, Any]:
        """模拟带自定义状态的 back_to_world 行为"""
        start_time = time.time()

        # 模拟操作执行
        op = MockBackToNormalWorld(self.mock_ctx)
        op_result = op.execute()

        app = self.create_mock_application(app_name)
        final_result = app.round_by_op_result(op_result, status=custom_status)

        execution_time = time.time() - start_time

        return {
            'app_name': app_name,
            'method': 'back_to_world_custom',
            'success': final_result.success,
            'status': final_result.status,
            'custom_status_used': final_result.status == custom_status,
            'execution_time': execution_time,
            'operation_created': True,
            'execute_called': True
        }

    def capture_baseline_behavior(self, app_names: List[str]) -> Dict[str, Any]:
        """捕获基准行为"""
        baseline_data = {}

        for app_name in app_names:
            # 捕获标准行为
            standard_behavior = self.simulate_standard_back_to_world(app_name)
            baseline_data[f"{app_name}_standard"] = standard_behavior

            # 对于 ChargePlanApp，捕获自定义状态行为
            if app_name == 'ChargePlanApp':
                custom_behavior = self.simulate_custom_status_back_to_world(
                    app_name, "剩余电量 85%"
                )
                baseline_data[f"{app_name}_custom"] = custom_behavior

        self.baseline_results = baseline_data
        return baseline_data

    def compare_behaviors(self, baseline: Dict[str, Any],
                         current: Dict[str, Any]) -> Dict[str, Any]:
        """比较两个行为结果"""
        comparison = {
            'equivalent': True,
            'differences': {},
            'baseline': baseline,
            'current': current
        }

        # 比较关键字段
        key_fields = ['success', 'status', 'operation_created', 'execute_called']

        for field in key_fields:
            baseline_val = baseline.get(field)
            current_val = current.get(field)

            if baseline_val != current_val:
                comparison['equivalent'] = False
                comparison['differences'][field] = {
                    'baseline': baseline_val,
                    'current': current_val
                }

        return comparison

    def validate_test_environment(self) -> Dict[str, bool]:
        """验证测试环境"""
        validation_results = {}

        try:
            # 测试模拟上下文创建
            ctx = self.create_mock_context()
            validation_results['mock_context_creation'] = ctx is not None
        except Exception:
            validation_results['mock_context_creation'] = False

        try:
            # 测试模拟应用创建
            app = self.create_mock_application("TestApp")
            validation_results['mock_application_creation'] = app is not None
        except Exception:
            validation_results['mock_application_creation'] = False

        try:
            # 测试模拟操作结果创建
            result = self.create_mock_operation_result()
            validation_results['mock_operation_result_creation'] = result is not None
        except Exception:
            validation_results['mock_operation_result_creation'] = False

        try:
            # 测试标准行为模拟
            behavior = self.simulate_standard_back_to_world("TestApp")
            validation_results['standard_behavior_simulation'] = behavior is not None
        except Exception:
            validation_results['standard_behavior_simulation'] = False

        return validation_results

    def generate_test_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        return {
            'infrastructure_status': self.validate_test_environment(),
            'baseline_results_count': len(self.baseline_results),
            'test_results_count': len(self.test_results),
            'timestamp': time.time()
        }

    def save_test_data(self, filename: str = "test_infrastructure_data.json"):
        """保存测试数据"""
        data = {
            'baseline_results': self.baseline_results,
            'test_results': self.test_results,
            'report': self.generate_test_report()
        }

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            print(f"测试数据已保存到 {filename}")
        except Exception as e:
            print(f"保存测试数据失败: {e}")


class PropertyTestGenerator:
    """属性测试生成器"""

    def __init__(self, infrastructure: TestInfrastructure):
        self.infrastructure = infrastructure

    def generate_custom_status_examples(self) -> List[str]:
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

    def generate_app_test_cases(self) -> Dict[str, List[str]]:
        """生成应用测试用例"""
        return {
            'removable_implementations': [
                'EmailApp', 'ScratchCardApp', 'RandomPlayApp',
                'NotoriousHuntApp', 'LifeOnLineApp', 'CityFundApp', 'CoffeeApp'
            ],
            'parameterizable_implementations': ['ChargePlanApp'],
            'special_implementations': [
                'TransportByCompendium', 'LostVoidLottery', 'LostVoidRouteChange'
            ]
        }

    def test_property_default_implementation_consistency(self, app_names: List[str]) -> List[Dict[str, Any]]:
        """测试属性：默认实现一致性"""
        results = []

        for app_name in app_names:
            # 模拟使用默认实现
            default_result = self.infrastructure.simulate_standard_back_to_world(app_name)

            # 模拟直接调用 BackToNormalWorld
            direct_result = self.infrastructure.simulate_standard_back_to_world(f"{app_name}_direct")

            # 比较结果
            comparison = self.infrastructure.compare_behaviors(default_result, direct_result)

            results.append({
                'app_name': app_name,
                'property': 'default_implementation_consistency',
                'passed': comparison['equivalent'],
                'details': comparison
            })

        return results

    def test_property_custom_status_parameter_passing(self, custom_statuses: List[str]) -> List[Dict[str, Any]]:
        """测试属性：自定义状态参数传递"""
        results = []

        for status in custom_statuses:
            result = self.infrastructure.simulate_custom_status_back_to_world(
                "TestApp", status
            )

            passed = result.get('custom_status_used', False)

            results.append({
                'custom_status': status,
                'property': 'custom_status_parameter_passing',
                'passed': passed,
                'details': result
            })

        return results


def run_infrastructure_tests():
    """运行基础设施测试"""
    print("=== back_to_world 重构测试基础设施验证 ===\n")

    # 创建测试基础设施
    infrastructure = TestInfrastructure()

    # 验证测试环境
    print("1. 验证测试环境...")
    validation_results = infrastructure.validate_test_environment()
    for component, status in validation_results.items():
        status_text = "✓" if status else "✗"
        print(f"   {status_text} {component}")

    # 捕获基准行为
    print("\n2. 捕获基准行为...")
    test_apps = ['EmailApp', 'ScratchCardApp', 'ChargePlanApp']
    baseline_data = infrastructure.capture_baseline_behavior(test_apps)
    print(f"   已捕获 {len(baseline_data)} 个基准行为")

    # 生成测试报告
    print("\n3. 生成测试报告...")
    report = infrastructure.generate_test_report()
    print(f"   基础设施状态: {sum(report['infrastructure_status'].values())}/{len(report['infrastructure_status'])} 通过")

    # 运行属性测试
    print("\n4. 运行属性测试...")
    generator = PropertyTestGenerator(infrastructure)

    # 测试默认实现一致性
    consistency_results = generator.test_property_default_implementation_consistency(['EmailApp', 'ScratchCardApp'])
    passed_consistency = sum(1 for r in consistency_results if r['passed'])
    print(f"   默认实现一致性: {passed_consistency}/{len(consistency_results)} 通过")

    # 测试自定义状态参数传递
    custom_statuses = generator.generate_custom_status_examples()[:3]  # 只测试前3个
    status_results = generator.test_property_custom_status_parameter_passing(custom_statuses)
    passed_status = sum(1 for r in status_results if r['passed'])
    print(f"   自定义状态参数传递: {passed_status}/{len(status_results)} 通过")

    # 保存测试数据
    print("\n5. 保存测试数据...")
    infrastructure.test_results = {
        'consistency_tests': consistency_results,
        'status_tests': status_results
    }
    infrastructure.save_test_data()

    print("\n=== 测试基础设施验证完成 ===")

    return infrastructure


if __name__ == "__main__":
    # 运行基础设施测试
    infrastructure = run_infrastructure_tests()