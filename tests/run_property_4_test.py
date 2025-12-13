#!/usr/bin/env python3
"""
属性 4 测试运行器

运行重构后行为等价性的属性基于测试。

**Feature: back-to-world-refactor, Property 4: 重构后行为等价性**
"""

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, "tests", "zzz_od", "application"))

from test_property_4_refactor_equivalence import Property4RefactorEquivalenceTest


def main():
    """运行属性 4 测试"""
    print("=" * 60)
    print("属性 4: 重构后行为等价性测试")
    print("=" * 60)
    print()

    # 创建测试实例
    test = Property4RefactorEquivalenceTest()

    # 运行属性测试
    print("1. 运行属性基于测试 (100 次迭代)...")
    property_result = test.run_property_test()

    # 显示结果
    status = "✓ 通过" if property_result.passed else "✗ 失败"
    print(f"   结果: {status}")
    print(f"   迭代次数: {property_result.iterations}")
    print(f"   执行时间: {property_result.execution_time:.3f}s")

    if not property_result.passed:
        print(f"   失败示例: {property_result.failed_example}")
        if property_result.error_message:
            print(f"   错误信息: {property_result.error_message}")

    print()
    print("2. 运行详细的等价性验证...")
    comprehensive_result = test.run_comprehensive_equivalence_test()

    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)

    # 返回测试是否通过
    return property_result.passed and comprehensive_result['overall_success_rate'] >= 0.95


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)