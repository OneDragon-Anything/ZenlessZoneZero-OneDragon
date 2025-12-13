"""
基准测试捕获模块

用于捕获重构前的 back_to_world 方法行为，以便在重构后进行对比验证。
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class BaselineBehavior:
    """基准行为数据结构"""
    app_name: str
    method_name: str
    input_params: Dict[str, Any]
    output_result: Dict[str, Any]
    execution_time: float
    timestamp: str
    success: bool
    error_message: Optional[str] = None


class BaselineCapture:
    """基准测试捕获器"""

    def __init__(self, baseline_file: str = "baseline_results.json"):
        self.baseline_file = baseline_file
        self.baseline_data: List[BaselineBehavior] = []
        self._load_existing_baseline()

    def _load_existing_baseline(self):
        """加载现有的基准数据"""
        if os.path.exists(self.baseline_file):
            try:
                with open(self.baseline_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.baseline_data = [
                        BaselineBehavior(**item) for item in data
                    ]
            except Exception as e:
                print(f"加载基准数据失败: {e}")
                self.baseline_data = []

    def capture_behavior(self, app_name: str, method_name: str,
                        input_params: Dict[str, Any],
                        output_result: Dict[str, Any],
                        execution_time: float,
                        success: bool,
                        error_message: Optional[str] = None) -> BaselineBehavior:
        """捕获方法行为"""
        behavior = BaselineBehavior(
            app_name=app_name,
            method_name=method_name,
            input_params=input_params,
            output_result=output_result,
            execution_time=execution_time,
            timestamp=datetime.now().isoformat(),
            success=success,
            error_message=error_message
        )

        self.baseline_data.append(behavior)
        return behavior

    def save_baseline(self):
        """保存基准数据到文件"""
        try:
            with open(self.baseline_file, 'w', encoding='utf-8') as f:
                json.dump([asdict(behavior) for behavior in self.baseline_data],
                         f, indent=2, ensure_ascii=False)
            print(f"基准数据已保存到 {self.baseline_file}")
        except Exception as e:
            print(f"保存基准数据失败: {e}")

    def get_baseline_for_app(self, app_name: str) -> List[BaselineBehavior]:
        """获取特定应用的基准数据"""
        return [b for b in self.baseline_data if b.app_name == app_name]

    def compare_with_baseline(self, app_name: str, method_name: str,
                            current_result: Dict[str, Any]) -> Dict[str, Any]:
        """与基准数据进行对比"""
        baseline_behaviors = [
            b for b in self.baseline_data
            if b.app_name == app_name and b.method_name == method_name
        ]

        if not baseline_behaviors:
            return {
                'status': 'no_baseline',
                'message': f'没有找到 {app_name}.{method_name} 的基准数据'
            }

        # 使用最新的基准数据进行对比
        latest_baseline = max(baseline_behaviors, key=lambda x: x.timestamp)

        comparison = {
            'status': 'compared',
            'baseline': asdict(latest_baseline),
            'current': current_result,
            'differences': {},
            'is_equivalent': True
        }

        # 对比关键字段
        key_fields = ['success', 'status']
        for field in key_fields:
            baseline_val = latest_baseline.output_result.get(field)
            current_val = current_result.get(field)

            if baseline_val != current_val:
                comparison['differences'][field] = {
                    'baseline': baseline_val,
                    'current': current_val
                }
                comparison['is_equivalent'] = False

        return comparison


def create_mock_operation_result(success: bool = True, status: str = "操作成功") -> Dict[str, Any]:
    """创建模拟的操作结果"""
    return {
        'success': success,
        'status': status,
        'timestamp': datetime.now().isoformat()
    }


def simulate_back_to_world_execution(app_name: str, custom_status: Optional[str] = None) -> Dict[str, Any]:
    """模拟 back_to_world 方法的执行"""
    import time
    import random

    # 模拟执行时间
    execution_time = random.uniform(0.1, 0.5)
    time.sleep(execution_time)

    # 模拟不同的结果
    if custom_status:
        result = create_mock_operation_result(success=True, status=custom_status)
    else:
        result = create_mock_operation_result(success=True, status="返回大世界成功")

    return {
        'result': result,
        'execution_time': execution_time,
        'app_name': app_name
    }


if __name__ == "__main__":
    # 演示基准捕获的使用
    capture = BaselineCapture("test_baseline.json")

    # 模拟捕获一些应用的基准行为
    test_apps = [
        'EmailApp', 'ScratchCardApp', 'RandomPlayApp',
        'NotoriousHuntApp', 'ChargePlanApp'
    ]

    print("开始捕获基准行为...")

    for app_name in test_apps:
        # 模拟标准调用
        sim_result = simulate_back_to_world_execution(app_name)
        capture.capture_behavior(
            app_name=app_name,
            method_name="back_to_world",
            input_params={},
            output_result=sim_result['result'],
            execution_time=sim_result['execution_time'],
            success=True
        )

        # 如果是 ChargePlanApp，模拟自定义状态调用
        if app_name == 'ChargePlanApp':
            custom_sim_result = simulate_back_to_world_execution(
                app_name, custom_status="剩余电量 85%"
            )
            capture.capture_behavior(
                app_name=app_name,
                method_name="back_to_world_custom",
                input_params={"custom_status": "剩余电量 85%"},
                output_result=custom_sim_result['result'],
                execution_time=custom_sim_result['execution_time'],
                success=True
            )

    # 保存基准数据
    capture.save_baseline()

    print(f"已捕获 {len(capture.baseline_data)} 条基准行为数据")

    # 演示对比功能
    print("\n演示对比功能:")
    current_result = create_mock_operation_result(success=True, status="返回大世界成功")
    comparison = capture.compare_with_baseline('EmailApp', 'back_to_world', current_result)
    print(f"对比结果: {comparison['status']}")
    print(f"是否等价: {comparison['is_equivalent']}")