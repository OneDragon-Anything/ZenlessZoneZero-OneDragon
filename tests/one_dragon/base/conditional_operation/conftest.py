"""测试夹具配置"""
import pytest
from unittest.mock import Mock

from one_dragon.base.conditional_operation.state_recorder import StateRecorder
from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.conditional_operation.scene_handler import SceneHandler
from one_dragon.base.conditional_operation.state_handler_template import StateHandlerTemplate
from one_dragon.base.conditional_operation.operation_template import OperationTemplate


@pytest.fixture
def mock_state_recorder():
    """创建模拟状态记录器"""
    mock_recorder = Mock(spec=StateRecorder)
    mock_recorder.state_name = 'test_state'
    mock_recorder.mutex_list = None
    mock_recorder.last_record_time = -1
    mock_recorder.last_value = None
    mock_recorder.update_state_record = Mock()
    mock_recorder.clear_state_record = Mock()
    mock_recorder.dispose = Mock()
    return mock_recorder


@pytest.fixture
def mock_atomic_op():
    """创建模拟原子操作"""
    mock_op = Mock(spec=AtomicOp)
    mock_op.op_name = 'test_op'
    mock_op.async_op = False
    mock_op.execute = Mock()
    mock_op.stop = Mock()
    mock_op.dispose = Mock()
    return mock_op


@pytest.fixture
def mock_op_getter(mock_atomic_op):
    """模拟操作获取器"""
    def _op_getter(op_def: OperationDef) -> AtomicOp:
        mock_op = Mock(spec=AtomicOp)
        mock_op.op_name = op_def.op_name or 'test_op'
        mock_op.async_op = getattr(op_def, 'async_op', False)
        mock_op.execute = Mock()
        mock_op.stop = Mock()
        mock_op.dispose = Mock()
        return mock_op
    return _op_getter


@pytest.fixture
def mock_scene_handler_getter():
    """模拟场景处理器模板获取器"""
    def _getter(template_name: str) -> StateHandlerTemplate:
        return None
    return _getter


@pytest.fixture
def mock_operation_template_getter():
    """模拟操作模板获取器"""
    def _getter(template_name: str) -> OperationTemplate:
        return None
    return _getter