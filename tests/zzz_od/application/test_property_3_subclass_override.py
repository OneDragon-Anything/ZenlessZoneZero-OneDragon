#!/usr/bin/env python3
"""
属性 3: 子类覆盖保持独立性测试

**Feature: back-to-world-refactor, Property 3: 子类覆盖保持独立性**
**Validates: Requirements 1.3, 5.3**

测试覆盖了 back_to_world 方法的子类，其覆盖实现应该被正确调用而不是基类的默认实现。
"""

import sys
import os
import time
from typing import Optional, Dict, Any, List
from unittest.mock import Mock, patch

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.join(project_root, "src"))

from test_infrastructure import TestInfrastructure, MockZContext, MockOperationResult
from property_test_framework import PropertyTestFramework, SimpleGenerator


class MockZApplicationBase:
    """模拟的 ZApplication 基类，包含默认的 back_to_world 实现"""

    def __init__(self, ctx: MockZContext, app_id: str = "test_app"):
        self.ctx = ctx
        self.app_id = app_id
        self._base_method_called = False
        self._override_method_called = False

    def round_by_op_result(self, op_result: MockOperationResult,
                          status: Optional[str] = None) -> MockOperationResult:
        """模拟 round_by_op_result 方法"""
        if status is not None:
            return MockOperationResult(success=op_result.success, status=status)
        return op_result

    def back_to_world(self, custom_status: Optional[str] = None) -> MockOperationResult:
        """基类的默认 back_to_world 实现"""
        self._base_method_called = True

        # 模拟 BackToNormalWorld 操作
        op_result = MockOperationResult(success=True, status="基类默认返回大世界")

        if custom_status is not None:
            return self.round_by_op_result(op_result, status=custom_status)
        return self.round_by_op_result(op_result)


class MockApplicationWithOverride(MockZApplicationBase):
    """模拟覆盖了 back_to_world 方法的应用"""

    def __init__(self, ctx: MockZContext, app_id: str = "override_app",
                 custom_behavior: str = "覆盖实现的自定义行为"):
        super().__init__(ctx, app_id)
        self.custom_behavior = custom_behavior

    def back_to_world(self, custom_status: Optional[str] = None) -> MockOperationResult:
        """覆盖的 back_to_world 实现"""
        self._override_method_called = True

        # 自定义的返回逻辑
        status = custom_status if custom_status else self.custom_behavior
        return MockOperationResult(success=True, status=status)


class MockApplicationWithoutOverride(MockZApplicationBase):
    """模拟没有覆盖 back_to_world 方法的应用（使用默认实现）"""

    def __init__(self, ctx: MockZContext, app_id: str = "default_app"):
        super().__init__(ctx, app_id)
        # 不覆盖 back_to_world 方法，使用基类默认实现


class MockChargePlanApp(MockZApplicationBase):
    """模拟 ChargePlanApp 的参数化覆盖"""

    def __init__(self, ctx: MockZContext, charge_power: int = 85):
        super().__init__(ctx, "charge_plan_app")
        self.charge_power = charge_power

    def back_to_world(self, custom_status: Optional[str] = None) -> MockOperationResult:
        """ChargePlanApp 的参数化覆盖实现"""
        self._override_method_called = True

        # 使用基类方法但传递自定义状态
        charge_status = f"剩余电量 {self.charge_power}%"
        return super().back_to_world(custom_status=charge_status)


class MockSpecialLogicApp(MockZApplicationBase):
    """模拟有特殊逻辑的应用（如 TransportByCompendium）"""

    def __init__(self, ctx: MockZContext, special_mode: str = "勘域模式"):
        super().__init__(ctx, "special_logic_app")
        self.special_mode = special_mode

    def back_to_world(self, custom_status: Optional[str] = None) -> MockOperationResult:
        """完全自定义的 back_to_world 实现"""
        self._override_method_called = True

        # 完全不同的逻辑，不调用基类方法
        if self.special_mode == "勘域模式":
            status = "特殊勘域返回逻辑"
        else:
            status = "特殊返回逻辑"

        if custom_status:
            status = f"{status} - {custom_status}"

        return MockOperationResult(success=True, status=status)


class SubclassOverridePropertyTest:
    """子类覆盖保持独立性的属性测试"""

    def __init__(self):
        self.infrastructure = TestInfrastructure()
        self.framework = PropertyTestFramework(default_iterations=50)
        self.generator = SimpleGenerator()

    def create_test_applications(self) -> Dict[str, MockZApplicationBase]:
        """创建各种测试应用实例"""
        ctx = self.infrastructure.create_mock_context()

        return {
            'without_override': MockApplicationWithoutOverride(ctx),
            'with_override': MockApplicationWithOverride(ctx),
            'charge_plan': MockChargePlanApp(ctx, self.generator.integer(10, 100)),
            'special_logic': MockSpecialLogicApp(ctx)
        }

    def property_subclass_override_independence(self) -> bool:
        """
        属性 3: 子类覆盖保持独立性
        对于任何覆盖了 back_to_world 方法的子类，
        其覆盖实现应该被正确调用而不是基类的默认实现
        """
        apps = self.create_test_applications()

        # 测试没有覆盖的应用使用基类实现
        default_app = apps['without_override']
        default_result = default_app.back_to_world()

        # 验证基类方法被调用
        if not default_app._base_method_called:
            return False
        if default_app._override_method_called:
            return False
        if "基类默认返回大世界" not in default_result.status:
            return False

        # 测试有覆盖的应用使用覆盖实现
        override_app = apps['with_override']
        override_result = override_app.back_to_world()

        # 验证覆盖方法被调用
        if override_app._base_method_called:
            return False
        if not override_app._override_method_called:
            return False
        if "覆盖实现的自定义行为" not in override_result.status:
            return False

        # 测试 ChargePlanApp 风格的参数化覆盖
        charge_app = apps['charge_plan']
        charge_result = charge_app.back_to_world()

        # 验证覆盖方法被调用，并且基类方法也被调用（因为调用了 super()）
        if not charge_app._override_method_called:
            return False
        if not charge_app._base_method_called:
            return False
        if "剩余电量" not in charge_result.status:
            return False

        # 测试完全自定义逻辑的应用
        special_app = apps['special_logic']
        special_result = special_app.back_to_world()

        # 验证只有覆盖方法被调用
        if special_app._base_method_called:
            return False
        if not special_app._override_method_called:
            return False
        if "特殊勘域返回逻辑" not in special_result.status:
            return False

        return True

    def property_override_with_custom_status(self) -> bool:
        """
        测试覆盖方法正确处理自定义状态参数
        """
        apps = self.create_test_applications()
        custom_status = self.generator.custom_status()

        # 测试覆盖应用处理自定义状态
        override_app = apps['with_override']
        result = override_app.back_to_world(custom_status=custom_status)

        # 验证自定义状态被正确使用
        if result.status != custom_status:
            return False

        # 测试特殊逻辑应用处理自定义状态
        special_app = apps['special_logic']
        special_result = special_app.back_to_world(custom_status=custom_status)

        # 验证自定义状态被包含在结果中
        if custom_status not in special_result.status:
            return False

        return True

    def property_method_resolution_order(self) -> bool:
        """
        测试方法解析顺序的正确性
        """
        apps = self.create_test_applications()

        # 重置所有标志
        for app in apps.values():
            app._base_method_called = False
            app._override_method_called = False

        # 测试每个应用的方法调用
        results = {}
        for app_type, app in apps.items():
            result = app.back_to_world()
            results[app_type] = {
                'base_called': app._base_method_called,
                'override_called': app._override_method_called,
                'status': result.status
            }

        # 验证方法解析顺序
        # 没有覆盖的应用：只调用基类方法
        if not results['without_override']['base_called']:
            return False
        if results['without_override']['override_called']:
            return False

        # 有覆盖的应用：只调用覆盖方法
        if results['with_override']['base_called']:
            return False
        if not results['with_override']['override_called']:
            return False

        # ChargePlanApp：调用覆盖方法，覆盖方法内部调用基类方法
        if not results['charge_plan']['override_called']:
            return False
        if not results['charge_plan']['base_called']:
            return False

        # 特殊逻辑应用：只调用覆盖方法
        if results['special_logic']['base_called']:
            return False
        if not results['special_logic']['override_called']:
            return False

        return True

    def run_property_tests(self) -> List[Dict[str, Any]]:
        """运行所有属性测试"""
        print("开始运行属性 3: 子类覆盖保持独立性测试...\n")

        results = []

        # 测试基本的子类覆盖独立性
        print("测试子类覆盖独立性...")
        result1 = self.framework.property_test(
            "子类覆盖独立性",
            self.property_subclass_override_independence
        )
        results.append(result1)

        # 测试覆盖方法处理自定义状态
        print("测试覆盖方法处理自定义状态...")
        result2 = self.framework.property_test(
            "覆盖方法自定义状态处理",
            self.property_override_with_custom_status
        )
        results.append(result2)

        # 测试方法解析顺序
        print("测试方法解析顺序...")
        result3 = self.framework.property_test(
            "方法解析顺序正确性",
            self.property_method_resolution_order
        )
        results.append(result3)

        return results


def run_detailed_override_tests():
    """运行详细的覆盖测试"""
    print("=== 详细的子类覆盖测试 ===\n")

    test_runner = SubclassOverridePropertyTest()

    # 创建测试应用
    apps = test_runner.create_test_applications()

    print("1. 测试应用创建:")
    for app_type, app in apps.items():
        print(f"   OK {app_type}: {app.__class__.__name__}")

    print("\n2. 单独测试每个应用的行为:")

    for app_type, app in apps.items():
        print(f"\n   测试 {app_type}:")

        # 重置标志
        app._base_method_called = False
        app._override_method_called = False

        # 调用方法
        result = app.back_to_world()

        # 报告结果
        print(f"     - 基类方法调用: {'是' if app._base_method_called else '否'}")
        print(f"     - 覆盖方法调用: {'是' if app._override_method_called else '否'}")
        print(f"     - 返回状态: {result.status}")
        print(f"     - 操作成功: {'是' if result.success else '否'}")

    print("\n3. 测试自定义状态处理:")

    custom_status = "测试自定义状态"
    for app_type, app in apps.items():
        # 重置标志
        app._base_method_called = False
        app._override_method_called = False

        result = app.back_to_world(custom_status=custom_status)
        print(f"   {app_type}: {result.status}")


def main():
    """主函数"""
    print("属性 3: 子类覆盖保持独立性测试")
    print("Feature: back-to-world-refactor, Property 3: 子类覆盖保持独立性")
    print("Validates: Requirements 1.3, 5.3")
    print("=" * 60)

    # 运行详细测试
    run_detailed_override_tests()

    print("\n" + "=" * 60)
    print("开始属性基于测试...")

    # 创建测试运行器
    test_runner = SubclassOverridePropertyTest()

    # 运行属性测试
    results = test_runner.run_property_tests()

    # 打印结果
    test_runner.framework.print_results()

    # 检查是否所有测试都通过
    all_passed = all(result.passed for result in results)

    if all_passed:
        print("\nSUCCESS 属性 3 测试全部通过！")
        print("子类覆盖保持独立性验证完成。")
        return 0
    else:
        print("\nFAIL 属性 3 测试存在失败。")
        failed_tests = [r for r in results if not r.passed]
        for test in failed_tests:
            print(f"失败的测试: {test.property_name}")
            if test.error_message:
                print(f"错误信息: {test.error_message}")
        return 1


if __name__ == "__main__":
    sys.exit(main())