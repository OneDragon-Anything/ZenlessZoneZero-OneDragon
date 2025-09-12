"""状态处理器测试"""
import pytest
from unittest.mock import Mock

from one_dragon.base.conditional_operation.state_handler import StateHandler
from one_dragon.base.conditional_operation.state_cal_tree import StateCalNode, StateCalNodeType
from one_dragon.base.conditional_operation.operation_task import OperationTask
from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.state_recorder import StateRecorder


class TestStateHandler:
    
    @pytest.fixture
    def mock_state_cal_tree(self):
        """创建模拟状态计算树"""
        mock_tree = Mock(spec=StateCalNode)
        mock_tree.node_type = StateCalNodeType.STATE
        mock_tree.in_time_range = Mock(return_value=True)
        mock_tree.get_usage_states = Mock(return_value={'test_state'})
        mock_tree.dispose = Mock()
        return mock_tree
    
    @pytest.fixture
    def mock_atomic_op(self):
        """创建模拟原子操作"""
        mock_op = Mock(spec=AtomicOp)
        mock_op.op_name = 'test_op'
        mock_op.async_op = False
        mock_op.execute = Mock()
        mock_op.stop = Mock()
        mock_op.dispose = Mock()
        return mock_op
    
    @pytest.fixture
    def state_handler(self, mock_state_cal_tree, mock_atomic_op):
        """创建状态处理器实例"""
        return StateHandler(
            expr='[test_state, 0, 1]',
            state_cal_tree=mock_state_cal_tree,
            operations=[mock_atomic_op]
        )
    
    def test_init(self, state_handler, mock_state_cal_tree, mock_atomic_op):
        """测试初始化"""
        assert state_handler.expr == '[test_state, 0, 1]'
        assert state_handler.state_cal_tree == mock_state_cal_tree
        assert state_handler.operations == [mock_atomic_op]
        assert state_handler.sub_handlers is None
        assert state_handler.interrupt_cal_tree is None
    
    def test_init_with_debug_name(self, mock_state_cal_tree, mock_atomic_op):
        """测试带调试名称的初始化"""
        handler = StateHandler(
            expr='[test_state, 0, 1]',
            state_cal_tree=mock_state_cal_tree,
            operations=[mock_atomic_op],
            debug_name='test_debug'
        )
        assert handler.debug_name == 'test_debug'
    
    def test_get_operations_match(self, state_handler, mock_state_cal_tree, mock_atomic_op):
        """测试获取操作 - 条件匹配"""
        mock_state_cal_tree.in_time_range.return_value = True
        
        task = state_handler.get_operations(100.0)
        
        assert task is not None
        assert isinstance(task, OperationTask)
        assert task.op_list == [mock_atomic_op]
    
    def test_get_operations_no_match(self, state_handler, mock_state_cal_tree):
        """测试获取操作 - 条件不匹配"""
        mock_state_cal_tree.in_time_range.return_value = False
        
        task = state_handler.get_operations(100.0)
        
        assert task is None
    
    def test_get_operations_with_sub_handlers(self, mock_state_cal_tree, mock_atomic_op):
        """测试带子处理器的操作获取"""
        # 创建子处理器
        mock_sub_tree = Mock(spec=StateCalNode)
        mock_sub_tree.node_type = StateCalNodeType.STATE
        mock_sub_tree.in_time_range = Mock(return_value=True)
        mock_sub_tree.get_usage_states = Mock(return_value={'sub_state'})
        mock_sub_tree.dispose = Mock()
        
        mock_sub_handler = Mock()
        mock_sub_handler.get_operations = Mock(return_value=Mock(spec=OperationTask))
        
        handler = StateHandler(
            expr='[test_state, 0, 1]',
            state_cal_tree=mock_state_cal_tree,
            sub_handlers=[mock_sub_handler]
        )
        
        mock_state_cal_tree.in_time_range.return_value = True
        
        task = handler.get_operations(100.0)
        
        # 验证子处理器被调用
        mock_sub_handler.get_operations.assert_called_once_with(100.0)
        assert task is not None
    
    def test_get_operations_with_sub_handlers_no_match(self, mock_state_cal_tree, mock_atomic_op):
        """测试带子处理器的操作获取 - 子处理器无匹配"""
        # 创建子处理器
        mock_sub_handler = Mock()
        mock_sub_handler.get_operations = Mock(return_value=None)
        
        handler = StateHandler(
            expr='[test_state, 0, 1]',
            state_cal_tree=mock_state_cal_tree,
            sub_handlers=[mock_sub_handler]
        )
        
        mock_state_cal_tree.in_time_range.return_value = True
        
        task = handler.get_operations(100.0)
        
        # 验证子处理器被调用
        mock_sub_handler.get_operations.assert_called_once_with(100.0)
        assert task is None
    
    def test_get_usage_states(self, state_handler, mock_state_cal_tree):
        """测试获取使用状态"""
        states = state_handler.get_usage_states()
        assert 'test_state' in states
    
    def test_get_usage_states_with_sub_handlers(self, mock_state_cal_tree, mock_atomic_op):
        """测试带子处理器的使用状态获取"""
        # 创建子处理器
        mock_sub_tree = Mock(spec=StateCalNode)
        mock_sub_tree.get_usage_states = Mock(return_value={'sub_state'})
        
        mock_sub_handler = Mock()
        mock_sub_handler.get_usage_states = Mock(return_value={'sub_handler_state'})
        
        handler = StateHandler(
            expr='[test_state, 0, 1]',
            state_cal_tree=mock_state_cal_tree,
            sub_handlers=[mock_sub_handler]
        )
        
        states = handler.get_usage_states()
        assert 'test_state' in states
        assert 'sub_handler_state' in states
    
    def test_dispose(self, state_handler, mock_state_cal_tree, mock_atomic_op):
        """测试销毁"""
        state_handler.dispose()
        
        # 验证相关对象的dispose方法被调用
        mock_state_cal_tree.dispose.assert_called_once()
        mock_atomic_op.dispose.assert_called_once()
    
    def test_dispose_with_sub_handlers(self, mock_state_cal_tree, mock_atomic_op):
        """测试带子处理器的销毁"""
        mock_sub_handler = Mock()
        mock_sub_handler.dispose = Mock()
        
        handler = StateHandler(
            expr='[test_state, 0, 1]',
            state_cal_tree=mock_state_cal_tree,
            sub_handlers=[mock_sub_handler]
        )
        
        handler.dispose()
        
        # 验证子处理器的dispose方法被调用
        mock_sub_handler.dispose.assert_called_once()