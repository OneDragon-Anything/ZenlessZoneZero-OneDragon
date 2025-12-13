"""
属性 4 测试验证 - 确保测试能够检测到失败情况

这个测试故意引入一些失败情况来验证测试框架的正确性。
"""

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.join(project_root, "tests", "zzz_od", "application"))

from test_infrastructure import TestInfrastructure
from property_test_framework import PropertyTestFramework


class FailureTestMockBehavior:
    """故意引入失败的模拟行为"""

    def __init__(self, infrastructure: TestInfrastructure):
        self.infrastructure = infrastructure
        self.failure_rate = 0.2  # 20% 的失败率

    def simulate_before_refactor_with_failures(self, app_name: str) -> dict:
        """模拟重构前的行为，有时会失败"""
        result = self.infrastructure.simulate_standard_back_to_world(app_name)

        # 随机引入失败
        import random
        if random.random() < self.failure_rate:
            result['success'] = False
            result['status'] = "模拟失败"

        return result

    def simulate_after_refactor_with_failures(self, app_name: str) -> dict:
        """模拟重构后的行为，有时会失败"""
        result = self.infrastructure.simulate_standard_back_to_world(app_name)

        # 随机引入不同的失败
        import random
        if random.random() < self.failure_rate:
            result['operation_created'] = False
            result['status'] = "重构后失败"

        return result


def test_failure_detection():
    """测试失败检测能力"""
    print("测试属性测试框架的失败检测能力...")

    infrastructure = TestInfrastructure()
    framework = PropertyTestFramework(default_iterations=20)
    mock_behavior = FailureTestMockBehavior(infrastructure)

    def failing_property_test() -> bool:
        """一个会失败的属性测试"""
        app_name = "TestApp"

        before_result = mock_behavior.simulate_before_refactor_with_failures(app_name)
        after_result = mock_behavior.simulate_after_refactor_with_failures(app_name)

        # 比较核心字段
        return (before_result.get('success') == after_result.get('success') and
                before_result.get('operation_created') == after_result.get('operation_created'))

    # 运行测试
    result = framework.property_test("失败检测测试", failing_property_test)

    print(f"测试结果:")
    print(f"  是否通过: {'✓' if result.passed else '✗'}")
    print(f"  迭代次数: {result.iterations}")

    if not result.passed:
        print(f"  失败示例: {result.failed_example}")
        print("  ✓ 测试框架正确检测到了失败")
    else:
        print("  ⚠ 测试框架可能没有正确检测到失败（或者运气太好）")

    return result


def main():
    """主函数"""
    print("=" * 50)
    print("属性 4 测试验证")
    print("=" * 50)
    print()

    # 测试失败检测
    result = test_failure_detection()

    print()
    print("验证完成。")
    print("如果看到失败检测，说明测试框架工作正常。")

    return result


if __name__ == "__main__":
    main()