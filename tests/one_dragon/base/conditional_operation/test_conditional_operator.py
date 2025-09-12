"""条件操作器测试"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import Future

from one_dragon.base.conditional_operation.conditional_operator import ConditionalOperator
from one_dragon.base.conditional_operation.state_recorder import StateRecord, StateRecorder
from one_dragon.base.conditional_operation.operation_task import OperationTask
from one_dragon.base.conditional_operation.atomic_op import AtomicOp


class TestConditionalOperator:
    
    @pytest.fixture
    def conditional_operator(self):
        """创建条件操作器实例"""
        operator = ConditionalOperator("test", "test_template", is_mock=True)
        # Mock get_state_recorder方法
        operator.get_state_recorder = Mock(return_value=Mock(spec=StateRecorder))
        yield operator
        # 测试结束后清理
        if operator.is_running:
            operator.stop_running()
        operator.dispose()
    
    def test_init_success(self, conditional_operator, mock_op_getter, 
                         mock_scene_handler_getter, mock_operation_template_getter):
        """测试初始化成功"""
        # 准备测试数据
        conditional_operator.update('scenes', [
            {
                'interval': 0.1,
                'handlers': [
                    {
                        'states': '[test_state, 0, 1]',
                        'operations': [
                            {'op_name': 'test_op'}
                        ]
                    }
                ]
            }
        ])
        
        # 执行初始化
        conditional_operator.init(
            mock_op_getter, 
            mock_scene_handler_getter, 
            mock_operation_template_getter
        )
        
        # 验证初始化成功
        assert conditional_operator._inited is True
        assert conditional_operator.normal_scene_handler is not None
    
    def test_init_with_trigger_scene(self, conditional_operator, mock_op_getter, 
                                   mock_scene_handler_getter, mock_operation_template_getter):
        """测试带触发场景的初始化"""
        conditional_operator.update('scenes', [
            {
                'triggers': ['trigger_state'],
                'interval': 0.1,
                'handlers': [
                    {
                        'states': '[test_state, 0, 1]',
                        'operations': [
                            {'op_name': 'test_op'}
                        ]
                    }
                ]
            }
        ])
        
        conditional_operator.init(
            mock_op_getter, 
            mock_scene_handler_getter, 
            mock_operation_template_getter
        )
        
        assert conditional_operator._inited is True
        assert 'trigger_state' in conditional_operator.trigger_scene_handler
    
    def test_init_duplicate_trigger_state_error(self, conditional_operator, mock_op_getter, 
                                              mock_scene_handler_getter, mock_operation_template_getter):
        """测试重复触发状态初始化错误"""
        conditional_operator.update('scenes', [
            {
                'triggers': ['duplicate_state'],
                'interval': 0.1,
                'handlers': [
                    {
                        'states': '[test_state1, 0, 1]',
                        'operations': [
                            {'op_name': 'test_op1'}
                        ]
                    }
                ]
            },
            {
                'triggers': ['duplicate_state'],  # 重复的触发状态
                'interval': 0.1,
                'handlers': [
                    {
                        'states': '[test_state2, 0, 1]',
                        'operations': [
                            {'op_name': 'test_op2'}
                        ]
                    }
                ]
            }
        ])
        
        # Mock get_state_recorder方法返回有效的StateRecorder
        def mock_get_state_recorder(state_name):
            mock_state_recorder = Mock(spec=StateRecorder)
            mock_state_recorder.state_name = state_name
            return mock_state_recorder
            
        conditional_operator.get_state_recorder = Mock(side_effect=mock_get_state_recorder)
        
        with pytest.raises(ValueError, match="状态监听 .* 出现在多个场景中"):
            conditional_operator.init(
                mock_op_getter, 
                mock_scene_handler_getter, 
                mock_operation_template_getter
            )
    
    def test_start_running_async_success(self, conditional_operator, mock_op_getter, 
                                       mock_scene_handler_getter, mock_operation_template_getter):
        """测试成功启动异步运行"""
        conditional_operator.update('scenes', [
            {
                'interval': 0.1,
                'handlers': [
                    {
                        'states': '[test_state, 0, 1]',
                        'operations': [
                            {'op_name': 'test_op'}
                        ]
                    }
                ]
            }
        ])
        
        conditional_operator.init(
            mock_op_getter, 
            mock_scene_handler_getter, 
            mock_operation_template_getter
        )
        
        result = conditional_operator.start_running_async()
        assert result is True
        assert conditional_operator.is_running is True
    
    def test_start_running_async_not_inited(self, conditional_operator):
        """测试未初始化时启动运行"""
        result = conditional_operator.start_running_async()
        assert result is False
        assert conditional_operator.is_running is False
    
    def test_start_running_async_already_running(self, conditional_operator, mock_op_getter, 
                                               mock_scene_handler_getter, mock_operation_template_getter):
        """测试重复启动运行"""
        conditional_operator.update('scenes', [
            {
                'interval': 0.1,
                'handlers': [
                    {
                        'states': '[test_state, 0, 1]',
                        'operations': [
                            {'op_name': 'test_op'}
                        ]
                    }
                ]
            }
        ])
        
        conditional_operator.init(
            mock_op_getter, 
            mock_scene_handler_getter, 
            mock_operation_template_getter
        )
        
        # 第一次启动
        result1 = conditional_operator.start_running_async()
        # 第二次启动
        result2 = conditional_operator.start_running_async()
        
        assert result1 is True
        assert result2 is False
        assert conditional_operator.is_running is True
    
    def test_stop_running(self, conditional_operator, mock_op_getter, 
                         mock_scene_handler_getter, mock_operation_template_getter):
        """测试停止运行"""
        conditional_operator.update('scenes', [
            {
                'interval': 0.1,
                'handlers': [
                    {
                        'states': '[test_state, 0, 1]',
                        'operations': [
                            {'op_name': 'test_op'}
                        ]
                    }
                ]
            }
        ])
        
        conditional_operator.init(
            mock_op_getter, 
            mock_scene_handler_getter, 
            mock_operation_template_getter
        )
        
        conditional_operator.start_running_async()
        assert conditional_operator.is_running is True
        
        conditional_operator.stop_running()
        assert conditional_operator.is_running is False
    
    def test_update_state(self, conditional_operator, mock_op_getter, 
                         mock_scene_handler_getter, mock_operation_template_getter):
        """测试状态更新"""
        # Mock状态记录器获取方法
        mock_state_recorder = Mock(spec=StateRecorder)
        mock_state_recorder.state_name = 'test_state'
        mock_state_recorder.mutex_list = None
        mock_state_recorder.last_record_time = -1
        mock_state_recorder.last_value = None
        mock_state_recorder.update_state_record = Mock()
        mock_state_recorder.clear_state_record = Mock()
        mock_state_recorder.dispose = Mock()
        
        with patch.object(conditional_operator, 'get_state_recorder', 
                         return_value=mock_state_recorder):
            state_record = StateRecord('test_state', time.time(), value=1)
            conditional_operator.update_state(state_record)
            
            # 验证状态记录器被调用
            mock_state_recorder.update_state_record.assert_called_once()
    
    def test_update_state_clear(self, conditional_operator, mock_op_getter, 
                               mock_scene_handler_getter, mock_operation_template_getter):
        """测试状态清除"""
        # Mock状态记录器获取方法
        mock_state_recorder = Mock(spec=StateRecorder)
        mock_state_recorder.state_name = 'test_state'
        mock_state_recorder.mutex_list = None
        mock_state_recorder.last_record_time = 100
        mock_state_recorder.last_value = 1
        mock_state_recorder.update_state_record = Mock()
        mock_state_recorder.clear_state_record = Mock()
        mock_state_recorder.dispose = Mock()
        
        with patch.object(conditional_operator, 'get_state_recorder', 
                         return_value=mock_state_recorder):
            state_record = StateRecord('test_state', time.time(), is_clear=True)
            conditional_operator.update_state(state_record)
            
            # 验证清除方法被调用
            mock_state_recorder.clear_state_record.assert_called_once()
    
    def test_batch_update_states(self, conditional_operator, mock_op_getter, 
                               mock_scene_handler_getter, mock_operation_template_getter):
        """测试批量状态更新"""
        mock_state_recorder1 = Mock(spec=StateRecorder)
        mock_state_recorder1.state_name = 'test_state1'
        mock_state_recorder1.mutex_list = None
        mock_state_recorder1.last_record_time = -1
        mock_state_recorder1.last_value = None
        mock_state_recorder1.update_state_record = Mock()
        mock_state_recorder1.clear_state_record = Mock()
        
        mock_state_recorder2 = Mock(spec=StateRecorder)
        mock_state_recorder2.state_name = 'test_state2'
        mock_state_recorder2.mutex_list = None
        mock_state_recorder2.last_record_time = -1
        mock_state_recorder2.last_value = None
        mock_state_recorder2.update_state_record = Mock()
        mock_state_recorder2.clear_state_record = Mock()
        
        def mock_get_state_recorder(state_name):
            if state_name == 'test_state1':
                return mock_state_recorder1
            elif state_name == 'test_state2':
                return mock_state_recorder2
            return None
        
        with patch.object(conditional_operator, 'get_state_recorder', 
                         side_effect=mock_get_state_recorder):
            state_records = [
                StateRecord('test_state1', time.time(), value=1),
                StateRecord('test_state2', time.time(), value=2)
            ]
            
            conditional_operator.batch_update_states(state_records)
            
            # 验证状态记录器被调用
            mock_state_recorder1.update_state_record.assert_called_once()
            mock_state_recorder2.update_state_record.assert_called_once()
    
    def test_dispose(self, conditional_operator, mock_op_getter, 
                    mock_scene_handler_getter, mock_operation_template_getter):
        """测试销毁"""
        conditional_operator.update('scenes', [
            {
                'interval': 0.1,
                'handlers': [
                    {
                        'states': '[test_state, 0, 1]',
                        'operations': [
                            {'op_name': 'test_op'}
                        ]
                    }
                ]
            }
        ])
        
        conditional_operator.init(
            mock_op_getter, 
            mock_scene_handler_getter, 
            mock_operation_template_getter
        )
        
        # Mock场景处理器的dispose方法
        if conditional_operator.normal_scene_handler:
            conditional_operator.normal_scene_handler.dispose = Mock()
        
        conditional_operator.dispose()
        
        # 验证场景处理器的dispose被调用
        if conditional_operator.normal_scene_handler and hasattr(conditional_operator.normal_scene_handler, 'dispose'):
            conditional_operator.normal_scene_handler.dispose.assert_called_once()
    
    def test_get_usage_states(self, conditional_operator, mock_op_getter, 
                             mock_scene_handler_getter, mock_operation_template_getter):
        """测试获取使用状态"""
        conditional_operator.update('scenes', [
            {
                'triggers': ['trigger_state'],
                'interval': 0.1,
                'handlers': [
                    {
                        'states': '[test_state, 0, 1]',
                        'operations': [
                            {'op_name': 'test_op'}
                        ]
                    }
                ]
            }
        ])
        
        # Mock get_state_recorder方法返回有效的StateRecorder
        mock_state_recorder = Mock(spec=StateRecorder)
        mock_state_recorder.state_name = 'test_state'
        conditional_operator.get_state_recorder = Mock(return_value=mock_state_recorder)
        
        conditional_operator.init(
            mock_op_getter, 
            mock_scene_handler_getter, 
            mock_operation_template_getter
        )
        
        usage_states = conditional_operator.get_usage_states()
        assert 'trigger_state' in usage_states
        assert 'test_state' in usage_states
    
    def test_normal_scene_loop(self, conditional_operator, mock_op_getter, 
                              mock_scene_handler_getter, mock_operation_template_getter):
        """测试主循环执行"""
        conditional_operator.update('scenes', [
            {
                'interval': 0.01,  # 短间隔便于测试
                'handlers': [
                    {
                        'states': '[test_state, 0, 1]',
                        'operations': [
                            {'op_name': 'test_op'}
                        ]
                    }
                ]
            }
        ])
        
        conditional_operator.init(
            mock_op_getter, 
            mock_scene_handler_getter, 
            mock_operation_template_getter
        )
        
        # 启动运行
        conditional_operator.start_running_async()
        assert conditional_operator.is_running is True
        
        # 等待一小段时间
        time.sleep(0.05)
        
        # 停止运行
        conditional_operator.stop_running()
        assert conditional_operator.is_running is False