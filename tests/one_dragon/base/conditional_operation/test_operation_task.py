"""操作任务测试"""
import pytest
import time
from unittest.mock import Mock, patch
from concurrent.futures import Future

from one_dragon.base.conditional_operation.operation_task import OperationTask
from one_dragon.base.conditional_operation.atomic_op import AtomicOp


class TestOperationTask:
    
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
    def operation_task(self, mock_atomic_op):
        """创建操作任务实例"""
        return OperationTask([mock_atomic_op])
    
    def test_init(self, operation_task, mock_atomic_op):
        """测试初始化"""
        assert operation_task.op_list == [mock_atomic_op]
        assert operation_task.running is False
        assert operation_task.trigger is None
        assert operation_task.is_trigger is False
        assert operation_task.priority is None
        assert operation_task.expr_list == []
        assert operation_task.debug_name_list == []
    
    def test_debug_name_display(self, operation_task):
        """测试调试名称显示"""
        # 测试空列表
        assert operation_task.debug_name_display == '/'
        
        # 添加调试名称
        operation_task.add_expr('[test_state, 0, 1]', 'test_debug')
        assert operation_task.debug_name_display == 'test_debug'
        
        # 添加多个调试名称
        operation_task.add_expr('[test_state2, 0, 1]', 'test_debug2')
        assert operation_task.debug_name_display == 'test_debug ← test_debug2'
        
        # 测试空名称处理
        operation_task.add_expr('[test_state3, 0, 1]', None)
        assert operation_task.debug_name_display == 'test_debug ← test_debug2 ← [ ]'
    
    def test_add_expr(self, operation_task):
        """测试添加表达式"""
        operation_task.add_expr('[test_state, 0, 1]', 'test_debug')
        assert operation_task.expr_list == ['[test_state, 0, 1]']
        assert operation_task.debug_name_list == ['test_debug']
    
    def test_set_priority(self, operation_task):
        """测试设置优先级"""
        operation_task.set_priority(10)
        assert operation_task.priority == 10
        
        operation_task.set_priority(None)
        assert operation_task.priority is None
    
    def test_set_trigger(self, operation_task):
        """测试设置触发器"""
        operation_task.set_trigger('test_trigger')
        assert operation_task.trigger == 'test_trigger'
        assert operation_task.is_trigger is True
        
        operation_task.set_trigger(None)
        assert operation_task.trigger is None
        assert operation_task.is_trigger is False
    
    def test_expr_display(self, operation_task):
        """测试表达式显示"""
        # 测试空列表
        assert operation_task.expr_display == '/'
        
        # 添加表达式和调试名称
        operation_task.add_expr('[test_state, 0, 1]', 'test_debug')
        assert operation_task.expr_display == 'test_debug'
        
        # 添加多个表达式
        operation_task.add_expr('[test_state2, 0, 1]', 'test_debug2')
        assert operation_task.expr_display == 'test_debug ← test_debug2'
    
    def test_priority_display(self, operation_task):
        """测试优先级显示"""
        assert operation_task.priority_display == '无优先级'
        
        operation_task.set_priority(10)
        assert operation_task.priority_display == '10'
    
    def test_trigger_display(self, operation_task):
        """测试触发器显示"""
        assert operation_task.trigger_display == '主循环'
        
        operation_task.set_trigger('test_trigger')
        assert operation_task.trigger_display == 'test_trigger'
    
    def test_run_async(self, operation_task):
        """测试异步运行"""
        with patch('one_dragon.base.conditional_operation.operation_task._od_op_task_executor') as mock_executor:
            mock_future = Mock(spec=Future)
            mock_executor.submit.return_value = mock_future
            mock_future.add_done_callback = Mock()
            
            future = operation_task.run_async()
            
            # 验证任务被提交到执行器
            mock_executor.submit.assert_called_once_with(operation_task._run)
            mock_future.add_done_callback.assert_called_once()
            assert future == mock_future
            assert operation_task.running is True
    
    def test_stop_not_running(self, operation_task):
        """测试停止未运行的任务"""
        operation_task.running = False
        result = operation_task.stop()
        assert result is True  # 已经完成所有指令
        assert operation_task.running is False
    
    def test_stop_running(self, operation_task, mock_atomic_op):
        """测试停止运行中的任务"""
        operation_task.running = True
        operation_task._current_op = mock_atomic_op
        
        result = operation_task.stop()
        
        assert result is False  # 未完成所有指令
        assert operation_task.running is False
        mock_atomic_op.stop.assert_called_once()
    
    def test_stop_running_async_op(self, operation_task, mock_atomic_op):
        """测试停止运行中的异步操作"""
        operation_task.running = True
        operation_task._current_op = mock_atomic_op
        operation_task._async_ops = [mock_atomic_op]
        
        result = operation_task.stop()
        
        assert result is False  # 未完成所有指令
        assert operation_task.running is False
        # 验证所有异步操作都被停止
        assert mock_atomic_op.stop.call_count == 2  # _current_op.stop() + _async_ops中的stop()
    
    def test_set_interrupt_cal_tree(self, operation_task):
        """测试设置中断计算树"""
        mock_cal_tree = Mock()
        operation_task.set_interrupt_cal_tree(mock_cal_tree)
        assert operation_task.interrupt_cal_tree == mock_cal_tree