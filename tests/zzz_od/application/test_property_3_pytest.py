#!/usr/bin/env python3
"""
属性 3: 子类覆盖保持独立性的 pytest 测试

**Feature: back-to-world-refactor, Property 3: 子类覆盖保持独立性**
**Validates: Requirements 1.3, 5.3**
"""

import sys
import os
from typing import Optional

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.join(project_root, "src"))

from test_property_3_subclass_override import SubclassOverridePropertyTest


def test_property_3_subclass_override_independence():
    """
    测试属性 3: 子类覆盖保持独立性

    **Feature: back-to-world-refactor, Property 3: 子类覆盖保持独立性**
    **Validates: Requirements 1.3, 5.3**
    """
    test_runner = SubclassOverridePropertyTest()

    # 运行属性测试
    results = test_runner.run_property_tests()

    # 验证所有测试都通过
    assert all(result.passed for result in results), f"部分属性测试失败: {[r.property_name for r in results if not r.passed]}"

    # 验证至少运行了预期的测试数量
    assert len(results) >= 3, f"测试数量不足，期望至少 3 个，实际 {len(results)} 个"

    # 验证特定的属性测试
    test_names = [r.property_name for r in results]
    assert "子类覆盖独立性" in test_names, "缺少子类覆盖独立性测试"
    assert "覆盖方法自定义状态处理" in test_names, "缺少覆盖方法自定义状态处理测试"
    assert "方法解析顺序正确性" in test_names, "缺少方法解析顺序正确性测试"


def test_property_3_detailed_behavior():
    """
    测试属性 3 的详细行为验证
    """
    test_runner = SubclassOverridePropertyTest()

    # 创建测试应用
    apps = test_runner.create_test_applications()

    # 验证应用创建成功
    assert len(apps) == 4, f"应用创建数量不正确，期望 4 个，实际 {len(apps)} 个"

    # 测试没有覆盖的应用
    default_app = apps['without_override']
    default_app._base_method_called = False
    default_app._override_method_called = False

    result = default_app.back_to_world()
    assert default_app._base_method_called, "没有覆盖的应用应该调用基类方法"
    assert not default_app._override_method_called, "没有覆盖的应用不应该调用覆盖方法"
    assert "基类默认返回大世界" in result.status, "默认应用应该返回基类状态"

    # 测试有覆盖的应用
    override_app = apps['with_override']
    override_app._base_method_called = False
    override_app._override_method_called = False

    result = override_app.back_to_world()
    assert not override_app._base_method_called, "有覆盖的应用不应该调用基类方法"
    assert override_app._override_method_called, "有覆盖的应用应该调用覆盖方法"
    assert "覆盖实现的自定义行为" in result.status, "覆盖应用应该返回覆盖状态"


if __name__ == "__main__":
    # 直接运行测试
    test_property_3_subclass_override_independence()
    test_property_3_detailed_behavior()
    print("所有 pytest 测试通过！")