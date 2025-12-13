"""
back_to_world 重构测试运行器

运行所有与 back_to_world 重构相关的测试，包括基础设施验证、基准测试和属性测试。
"""

import sys
import os
from typing import Dict, Any, List

# 添加测试目录到路径
test_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(test_dir, "zzz_od", "application"))

from test_infrastructure import TestInfrastructure, run_infrastructure_tests
from property_test_framework import BackToWorldPropertyTests, PropertyTestFramework
from baseline_capture import BaselineCapture


class RefactorTestRunner:
    """重构测试运行器"""

    def __init__(self):
        self.infrastructure = None
        self.baseline_capture = None
        self.property_tests = None
        self.results = {}

    def setup(self):
        """设置测试环境"""
        print("=== 设置 back_to_world 重构测试环境 ===\n")

        # 创建基础设施
        self.infrastructure = TestInfrastructure()

        # 创建基准捕获器
        self.baseline_capture = BaselineCapture("refactor_baseline.json")

        # 创建属性测试
        self.property_tests = BackToWorldPropertyTests(self.infrastructure)

        print("测试环境设置完成\n")

    def run_infrastructure_validation(self) -> Dict[str, Any]:
        """运行基础设施验证"""
        print("=== 1. 基础设施验证 ===\n")

        validation_results = self.infrastructure.validate_test_environment()

        print("基础设施组件状态:")
        for component, status in validation_results.items():
            status_text = "✓" if status else "✗"
            print(f"  {status_text} {component}")

        passed = sum(validation_results.values())
        total = len(validation_results)
        print(f"\n基础设施验证: {passed}/{total} 通过\n")

        return {
            'validation_results': validation_results,
            'passed': passed,
            'total': total,
            'success_rate': passed / total if total > 0 else 0
        }

    def run_baseline_capture(self) -> Dict[str, Any]:
        """运行基准捕获"""
        print("=== 2. 基准行为捕获 ===\n")

        # 定义要测试的应用
        test_apps = [
            'EmailApp', 'ScratchCardApp', 'RandomPlayApp',
            'NotoriousHuntApp', 'LifeOnLineApp', 'CityFundApp',
            'CoffeeApp', 'ChargePlanApp'
        ]

        baseline_data = self.infrastructure.capture_baseline_behavior(test_apps)

        print(f"已捕获 {len(baseline_data)} 个基准行为:")
        for key, behavior in baseline_data.items():
            status = "✓" if behavior['success'] else "✗"
            print(f"  {status} {key}: {behavior['status']}")

        # 保存基准数据
        for key, behavior in baseline_data.items():
            self.baseline_capture.capture_behavior(
                app_name=behavior['app_name'],
                method_name=behavior['method'],
                input_params={},
                output_result=behavior,
                execution_time=behavior['execution_time'],
                success=behavior['success']
            )

        self.baseline_capture.save_baseline()
        print(f"\n基准数据已保存\n")

        return {
            'baseline_count': len(baseline_data),
            'baseline_data': baseline_data
        }

    def run_property_tests(self) -> Dict[str, Any]:
        """运行属性测试"""
        print("=== 3. 属性基于测试 ===\n")

        # 运行所有属性测试
        results = self.property_tests.run_all_property_tests()

        # 统计结果
        passed_tests = sum(1 for r in results if r.passed)
        total_tests = len(results)

        print(f"\n属性测试结果:")
        for result in results:
            status = "✓" if result.passed else "✗"
            print(f"  {status} {result.property_name}: {result.iterations} 次迭代")
            if not result.passed and result.error_message:
                print(f"    错误: {result.error_message}")

        print(f"\n属性测试总结: {passed_tests}/{total_tests} 通过\n")

        return {
            'results': results,
            'passed': passed_tests,
            'total': total_tests,
            'success_rate': passed_tests / total_tests if total_tests > 0 else 0
        }

    def run_integration_tests(self) -> Dict[str, Any]:
        """运行集成测试"""
        print("=== 4. 集成测试 ===\n")

        # 测试不同应用类型的集成
        app_categories = {
            'standard_apps': ['EmailApp', 'ScratchCardApp', 'RandomPlayApp'],
            'parameterized_apps': ['ChargePlanApp'],
            'special_apps': ['TransportByCompendium', 'LostVoidLottery']
        }

        integration_results = {}

        for category, apps in app_categories.items():
            print(f"测试 {category}:")
            category_results = []

            for app_name in apps:
                try:
                    # 模拟集成测试
                    result = self.infrastructure.simulate_standard_back_to_world(app_name)
                    success = result['success'] and result['operation_created']
                    category_results.append({
                        'app_name': app_name,
                        'success': success,
                        'result': result
                    })

                    status = "✓" if success else "✗"
                    print(f"  {status} {app_name}")

                except Exception as e:
                    category_results.append({
                        'app_name': app_name,
                        'success': False,
                        'error': str(e)
                    })
                    print(f"  ✗ {app_name}: {e}")

            integration_results[category] = category_results

        # 统计集成测试结果
        total_apps = sum(len(apps) for apps in app_categories.values())
        passed_apps = sum(
            sum(1 for result in results if result['success'])
            for results in integration_results.values()
        )

        print(f"\n集成测试总结: {passed_apps}/{total_apps} 应用通过\n")

        return {
            'integration_results': integration_results,
            'passed': passed_apps,
            'total': total_apps,
            'success_rate': passed_apps / total_apps if total_apps > 0 else 0
        }

    def generate_final_report(self) -> Dict[str, Any]:
        """生成最终报告"""
        print("=== 5. 最终测试报告 ===\n")

        # 汇总所有结果
        infrastructure_results = self.results.get('infrastructure', {})
        baseline_results = self.results.get('baseline', {})
        property_results = self.results.get('property_tests', {})
        integration_results = self.results.get('integration', {})

        # 计算总体成功率
        total_success_rate = (
            infrastructure_results.get('success_rate', 0) +
            property_results.get('success_rate', 0) +
            integration_results.get('success_rate', 0)
        ) / 3

        report = {
            'infrastructure': infrastructure_results,
            'baseline': baseline_results,
            'property_tests': property_results,
            'integration': integration_results,
            'overall_success_rate': total_success_rate,
            'ready_for_refactor': total_success_rate >= 0.9  # 90% 通过率才能开始重构
        }

        print("测试结果摘要:")
        print(f"  基础设施验证: {infrastructure_results.get('success_rate', 0):.1%}")
        print(f"  基准数据捕获: {baseline_results.get('baseline_count', 0)} 条记录")
        print(f"  属性测试: {property_results.get('success_rate', 0):.1%}")
        print(f"  集成测试: {integration_results.get('success_rate', 0):.1%}")
        print(f"  总体成功率: {total_success_rate:.1%}")

        if report['ready_for_refactor']:
            print("\n✓ 测试基础设施已就绪，可以开始重构")
        else:
            print("\n✗ 测试基础设施未完全就绪，建议修复失败的测试后再开始重构")

        return report

    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("开始运行 back_to_world 重构测试套件\n")

        # 设置环境
        self.setup()

        # 运行各个测试阶段
        self.results['infrastructure'] = self.run_infrastructure_validation()
        self.results['baseline'] = self.run_baseline_capture()
        self.results['property_tests'] = self.run_property_tests()
        self.results['integration'] = self.run_integration_tests()

        # 生成最终报告
        final_report = self.generate_final_report()

        # 保存完整结果
        self.infrastructure.test_results = self.results
        self.infrastructure.save_test_data("complete_refactor_test_results.json")

        print("\n=== 测试套件执行完成 ===")

        return final_report


def main():
    """主函数"""
    runner = RefactorTestRunner()
    report = runner.run_all_tests()

    # 返回退出码
    return 0 if report['ready_for_refactor'] else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)