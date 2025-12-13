#!/usr/bin/env python3
"""
属性 2 测试运行器

运行自定义状态参数传递的属性基于测试，并生成测试报告。
"""

import subprocess
import sys
import time
from pathlib import Path


def run_property_2_tests():
    """运行属性 2 的测试"""
    print("=== 运行属性 2: 自定义状态参数传递测试 ===\n")

    # 记录开始时间
    start_time = time.time()

    # 运行测试
    test_file = "zzz_od/application/test_property_2_custom_status.py"
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
            print("✓ 所有属性测试通过")
            print("\n属性 2 验证:")
            print("- ✓ 自定义状态参数正确传递")
            print("- ✓ 支持各种字符编码（ASCII、中文）")
            print("- ✓ 处理现实场景的状态消息")
            print("- ✓ ChargePlanApp 风格的电量状态")
            print("- ✓ 操作失败时状态参数仍正确传递")
            print("- ✓ 自定义状态覆盖默认状态")
            print("- ✓ 多次调用的一致性")
            print("- ✓ 长字符串处理")
            print("- ✓ 空字符串处理")
            print("- ✓ None 与自定义状态的区别")
        else:
            print("✗ 部分属性测试失败")
            print("请检查上面的错误输出以了解失败原因")

        return result.returncode == 0

    except Exception as e:
        print(f"运行测试时发生错误: {e}")
        return False


def main():
    """主函数"""
    print("属性 2 测试运行器")
    print("Feature: back-to-world-refactor, Property 2: 自定义状态参数传递")
    print("Validates: Requirements 1.2, 5.2")
    print()

    success = run_property_2_tests()

    if success:
        print("\n🎉 属性 2 测试全部通过！")
        print("自定义状态参数传递功能验证完成。")
    else:
        print("\n❌ 属性 2 测试存在失败。")
        print("请修复失败的测试后重新运行。")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())