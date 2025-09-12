"""场景处理器测试"""
import pytest
from unittest.mock import Mock

from one_dragon.base.conditional_operation.scene_handler import SceneHandler
from one_dragon.base.conditional_operation.state_handler import StateHandler
from one_dragon.base.conditional_operation.operation_task import OperationTask


class TestSceneHandler:
    
    @pytest.fixture
    def mock_state_handler(self):
        """创建模拟状态处理器"""
        mock_handler = Mock(spec=StateHandler)
        mock_handler.get_operations = Mock(return_value=None)
        mock_handler.get_usage_states = Mock(return_value={'test_state'})
        mock_handler.dispose = Mock()
        return mock_handler
    
    @pytest.fixture
    def scene_handler(self, mock_state_handler):
        """创建场景处理器实例"""
        return SceneHandler(
            interval_seconds=0.1,
            state_handlers=[mock_state_handler],
            priority=10
        )
    
    def test_init(self, scene_handler, mock_state_handler):
        """测试初始化"""
        assert scene_handler.interval_seconds == 0.1
        assert scene_handler.state_handlers == [mock_state_handler]
        assert scene_handler.priority == 10
    
    def test_init_default_priority(self, mock_state_handler):
        """测试默认优先级初始化"""
        handler = SceneHandler(
            interval_seconds=0.1,
            state_handlers=[mock_state_handler]
        )
        assert handler.priority is None
    
    def test_get_operations_match(self, scene_handler, mock_state_handler):
        """测试获取操作 - 有匹配"""
        mock_task = Mock(spec=OperationTask)
        mock_state_handler.get_operations.return_value = mock_task
        
        task = scene_handler.get_operations(100.0)
        
        assert task == mock_task
        # 验证优先级被设置
        mock_task.set_priority.assert_called_once_with(10)
    
    def test_get_operations_no_match(self, scene_handler, mock_state_handler):
        """测试获取操作 - 无匹配"""
        mock_state_handler.get_operations.return_value = None
        
        task = scene_handler.get_operations(100.0)
        
        assert task is None
    
    def test_get_operations_multiple_handlers(self, mock_state_handler):
        """测试多个状态处理器的操作获取"""
        # 创建第二个状态处理器
        mock_handler2 = Mock(spec=StateHandler)
        mock_handler2.get_operations = Mock(return_value=None)
        mock_handler2.get_usage_states = Mock(return_value={'test_state2'})
        mock_handler2.dispose = Mock()
        
        handler = SceneHandler(
            interval_seconds=0.1,
            state_handlers=[mock_state_handler, mock_handler2],
            priority=10
        )
        
        # 第一个处理器无匹配，第二个处理器有匹配
        mock_task = Mock(spec=OperationTask)
        mock_state_handler.get_operations.return_value = None
        mock_handler2.get_operations.return_value = mock_task
        
        task = handler.get_operations(100.0)
        
        assert task == mock_task
        mock_task.set_priority.assert_called_once_with(10)
    
    def test_get_usage_states(self, scene_handler, mock_state_handler):
        """测试获取使用状态"""
        states = scene_handler.get_usage_states()
        assert 'test_state' in states
    
    def test_get_usage_states_multiple_handlers(self, mock_state_handler):
        """测试多个处理器的使用状态获取"""
        # 创建第二个状态处理器
        mock_handler2 = Mock(spec=StateHandler)
        mock_handler2.get_usage_states = Mock(return_value={'test_state2'})
        
        handler = SceneHandler(
            interval_seconds=0.1,
            state_handlers=[mock_state_handler, mock_handler2]
        )
        
        states = handler.get_usage_states()
        assert 'test_state' in states
        assert 'test_state2' in states
    
    def test_dispose(self, scene_handler, mock_state_handler):
        """测试销毁"""
        scene_handler.dispose()
        
        # 验证状态处理器的dispose方法被调用
        mock_state_handler.dispose.assert_called_once()
    
    def test_dispose_multiple_handlers(self, mock_state_handler):
        """测试多个处理器的销毁"""
        # 创建第二个状态处理器
        mock_handler2 = Mock(spec=StateHandler)
        mock_handler2.dispose = Mock()
        
        handler = SceneHandler(
            interval_seconds=0.1,
            state_handlers=[mock_state_handler, mock_handler2]
        )
        
        handler.dispose()
        
        # 验证所有状态处理器的dispose方法被调用
        mock_state_handler.dispose.assert_called_once()
        mock_handler2.dispose.assert_called_once()