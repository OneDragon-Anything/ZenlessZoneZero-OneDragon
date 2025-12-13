#!/usr/bin/env python3
"""
属性 3 测试运行器

运行子类覆盖保持独立性的属性基于测试，并生成测试报告。
"""

import subprocess
import sys
import time
from pathlib import Path


def run_property_3_tests():
    """运行属性 3 的测试"""
    print("=== 运行属性 3: 子类覆盖保持独立性测试 ===\n")

    # 记录开始时间
    start_time = time.time()

    # 运行测试
    test_file = "zzz_od/application/test_property_3_subclass_override.py"
    cmd = [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"]

    print(f"执行命令: {' '.join(cmd)}")
    print("=" * 60)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)

        # 打印输出
        if result.stdout:
            print("测试输出:")
            print(result.stdout)

        if result.stderr:
            print("错误输出:")
            print(result.stderr)

        # 计算执行时间
        execution_time = time.time() - start_time

        # 生成报告
        print("\n" + "=" * 60)
        print("测试执行报告")
        print("=" * 60)
        print(f"测试文件: {test_file}")
        print(f"执行时间: {execution_time:.2f} 秒")
        print(f"退出代码: {result.returncode}")

        if result.returncode == 0:
            print("OK 所有属性测试通过")
            print("\n属性 3 验证:")
            print("- OK 子类覆盖方法被正确调用")
            print("- OK 基类默认实现不被错误调用")
            print("- OK 方法解析顺序正确")
            print("- OK 覆盖方法正确处理自定义状态")
            print("- OK 参数化覆盖（ChargePlanApp 风格）正常工作")
            print("- OK 完全自定义逻辑（特殊应用）正常工作")
            print("- OK 不同覆盖策略的独立性")
        else:
            print("FAIL 部分属性测试失败")
            print("请检查上面的错误输出以了解失败原因")

        return result.returncode == 0

    except Exception as e:
        print(f"运行测试时发生错误: {e}")
        return False


def run_direct_test():
    """直接运行测试文件"""
    print("=== 直接运行属性 3 测试 ===\n")

    # 记录开始时间
    start_time = time.time()

    # 直接运行测试文件
    test_file = Path(__file__).parent / "zzz_od" / "application" / "test_property_3_subclass_override.py"
    cmd = [sys.executable, str(test_file)]

    print(f"执行命令: {' '.join(cmd)}")
    print("=" * 60)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        # 打印输出
        if result.stdout:
            print("测试输出:")
            print(result.stdout)

        if result.stderr:
            print("错误输出:")
            print(result.stderr)

        # 计算执行时间
        execution_time = time.time() - start_time

        # 生成报告
        print("\n" + "=" * 60)
        print("直接测试执行报告")
        print("=" * 60)
        print(f"测试文件: {test_file}")
        print(f"执行时间: {execution_time:.2f} 秒")
        print(f"退出代码: {result.returncode}")

        return result.returncode == 0

    except Exception as e:
        print(f"运行测试时发生错误: {e}")
        return False


def main():
    """主函数"""
    print("属性 3 测试运行器")
    print("Feature: back-to-world-refactor, Property 3: 子类覆盖保持独立性")
    print("Validates: Requirements 1.3, 5.3")
    print()

    # 首先尝试直接运行测试
    print("尝试直接运行测试...")
    direct_success = run_direct_test()

    if direct_success:
        print("\nSUCCESS 属性 3 测试全部通过！")
        print("子类覆盖保持独立性功能验证完成。")
        return 0
    else:
        print("\n尝试使用 pytest 运行测试...")
        pytest_success = run_property_3_tests()

        if pytest_success:
            print("\nSUCCESS 属性 3 测试全部通过！")
            print("子类覆盖保持独立性功能验证完成。")
            return 0
        else:
            print("\nFAIL 属性 3 测试存在失败。")
            print("请检查测试实现或修复失败的测试后重新运行。")
            return 1


if __name__ == "__main__":
    sys.exit(main())