"""
pytest 配置文件

为 back_to_world 重构提供共享的 fixtures 和配置。
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.fixture(scope="session")
def project_root_path():
    """提供项目根目录路径"""
    return project_root


@pytest.fixture
def mock_zzz_context():
    """提供模拟的 ZContext 实例"""
    from zzz_od.context.zzz_context import ZContext

    # 创建一个模拟的 ZContext
    mock_ctx = Mock(spec=ZContext)

    # 设置必要的属性
    mock_ctx.controller = Mock()
    mock_ctx.screen_loader = Mock()
    mock_ctx.ocr = Mock()
    mock_ctx.world_patrol_service = Mock()
    mock_ctx.compendium_service = Mock()
    mock_ctx.lost_void = Mock()
    mock_ctx.logger = Mock()
    mock_ctx.run_context = Mock()

    # 设置默认行为
    mock_ctx.run_context.start_running = Mock()
    mock_ctx.logger.error = Mock()

    return mock_ctx


@pytest.fixture
def sample_operation_results():
    """提供示例操作结果"""
    from one_dragon.base.operation.operation_round_result import OperationRoundResult

    return {
        'success': OperationRoundResult(success=True, status="操作成功"),
        'failure': OperationRoundResult(success=False, status="操作失败"),
        'custom_status': OperationRoundResult(success=True, status="自定义状态消息"),
        'charge_status': OperationRoundResult(success=True, status="剩余电量 85%"),
    }


@pytest.fixture
def back_to_world_test_data():
    """提供 back_to_world 测试数据"""
    return {
        'standard_apps': [
            'EmailApp', 'ScratchCardApp', 'RandomPlayApp',
            'NotoriousHuntApp', 'LifeOnLineApp', 'CityFundApp', 'CoffeeApp'
        ],
        'parameterizable_apps': {
            'ChargePlanApp': 'f"剩余电量 {self.charge_power}"'
        },
        'special_apps': [
            'TransportByCompendium', 'LostVoidLottery', 'LostVoidRouteChange'
        ],
        'custom_status_examples': [
            "剩余电量 85%",
            "任务完成",
            "返回成功",
            "操作结束"
        ]
    }


# 测试标记定义
def pytest_configure(config):
    """配置 pytest 标记"""
    config.addinivalue_line(
        "markers", "baseline: 标记基准测试"
    )
    config.addinivalue_line(
        "markers", "integration: 标记集成测试"
    )
    config.addinivalue_line(
        "markers", "property_test: 标记属性基于测试"
    )
    config.addinivalue_line(
        "markers", "refactor: 标记重构相关测试"
    )


# 测试收集钩子
def pytest_collection_modifyitems(config, items):
    """修改测试收集行为"""
    # 为没有标记的测试添加默认标记
    for item in items:
        if not any(item.iter_markers()):
            item.add_marker(pytest.mark.unit)