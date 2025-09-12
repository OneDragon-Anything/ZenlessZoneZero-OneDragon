"""工具函数测试"""
import pytest
from unittest.mock import Mock

from one_dragon.base.conditional_operation.utils import (
    construct_scene_handler, construct_state_handler, get_ops_from_data
)
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.conditional_operation.state_cal_tree import StateCalNode, StateCalNodeType
from one_dragon.base.conditional_operation.state_recorder import StateRecorder
from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.state_handler_template import StateHandlerTemplate
from one_dragon.base.conditional_operation.operation_template import OperationTemplate


class TestUtils:
    
    @pytest.fixture
    def mock_state_getter(self):
        """创建模拟状态获取器"""
        mock_recorder = Mock(spec=StateRecorder)
        mock_recorder.state_name = 'test_state'
        mock_recorder.last_record_time = 100.0
        mock_recorder.last_value = 1
        
        def _getter(state_name):
            if state_name == 'test_state':
                return mock_recorder
            return None
        return _getter
    
    @pytest.fixture
    def mock_op_getter(self):
        """创建模拟操作获取器"""
        def _getter(op_def: OperationDef) -> AtomicOp:
            mock_op = Mock(spec=AtomicOp)
            mock_op.op_name = op_def.op_name or 'test_op'
            mock_op.async_op = getattr(op_def, 'async_op', False)
            mock_op.execute = Mock()
            mock_op.stop = Mock()
            mock_op.dispose = Mock()
            return mock_op
        return _getter
    
    @pytest.fixture
    def mock_scene_handler_getter(self):
        """创建模拟场景处理器模板获取器"""
        def _getter(template_name: str) -> StateHandlerTemplate:
            return None
        return _getter
    
    @pytest.fixture
    def mock_operation_template_getter(self):
        """创建模拟操作模板获取器"""
        def _getter(template_name: str) -> OperationTemplate:
            return None
        return _getter
    
    def test_construct_scene_handler(self, mock_state_getter, mock_op_getter, 
                                   mock_scene_handler_getter, mock_operation_template_getter):
        """测试构造场景处理器"""
        scene_data = {
            'interval': 0.1,
            'priority': 10,
            'handlers': [
                {
                    'states': '[test_state, 0, 1]',
                    'operations': [
                        {'op_name': 'test_op'}
                    ]
                }
            ]
        }
        
        with pytest.MonkeyPatch().context() as m:
            # Mock construct_state_cal_tree函数
            mock_node = Mock(spec=StateCalNode)
            mock_node.node_type = StateCalNodeType.STATE
            m.setattr(
                'one_dragon.base.conditional_operation.utils.construct_state_cal_tree',
                Mock(return_value=mock_node)
            )
            
            handler = construct_scene_handler(
                scene_data,
                mock_state_getter,
                mock_op_getter,
                mock_scene_handler_getter,
                mock_operation_template_getter
            )
            
            assert handler.interval_seconds == 0.1
            assert handler.priority == 10
            assert len(handler.state_handlers) == 1
    
    def test_construct_state_handler_basic(self, mock_state_getter, mock_op_getter, 
                                         mock_scene_handler_getter, mock_operation_template_getter):
        """测试构造基本状态处理器"""
        state_data = {
            'states': '[test_state, 0, 1]',
            'operations': [
                {'op_name': 'test_op'}
            ]
        }
        
        with pytest.MonkeyPatch().context() as m:
            # Mock construct_state_cal_tree函数
            mock_node = Mock(spec=StateCalNode)
            mock_node.node_type = StateCalNodeType.STATE
            m.setattr(
                'one_dragon.base.conditional_operation.utils.construct_state_cal_tree',
                Mock(return_value=mock_node)
            )
            
            handler = construct_state_handler(
                state_data,
                mock_state_getter,
                mock_op_getter,
                mock_scene_handler_getter,
                mock_operation_template_getter,
                set()
            )
            
            assert handler.expr == '[test_state, 0, 1]'
            assert handler.operations is not None
            assert len(handler.operations) == 1
    
    def test_construct_state_handler_with_debug_name(self, mock_state_getter, mock_op_getter, 
                                                   mock_scene_handler_getter, mock_operation_template_getter):
        """测试带调试名称的状态处理器构造"""
        state_data = {
            'states': '[test_state, 0, 1]',
            'debug_name': 'test_debug',
            'operations': [
                {'op_name': 'test_op'}
            ]
        }
        
        with pytest.MonkeyPatch().context() as m:
            # Mock construct_state_cal_tree函数
            mock_node = Mock(spec=StateCalNode)
            mock_node.node_type = StateCalNodeType.STATE
            m.setattr(
                'one_dragon.base.conditional_operation.utils.construct_state_cal_tree',
                Mock(return_value=mock_node)
            )
            
            handler = construct_state_handler(
                state_data,
                mock_state_getter,
                mock_op_getter,
                mock_scene_handler_getter,
                mock_operation_template_getter,
                set()
            )
            
            assert handler.debug_name == '[#test_debug]'
    
    def test_construct_state_handler_with_sub_handlers(self, mock_state_getter, mock_op_getter, 
                                                     mock_scene_handler_getter, mock_operation_template_getter):
        """测试带子处理器的状态处理器构造"""
        state_data = {
            'states': '[test_state, 0, 1]',
            'sub_handlers': [
                {
                    'states': '[test_state, 0, 1]',
                    'operations': [
                        {'op_name': 'test_op'}
                    ]
                }
            ]
        }
        
        with pytest.MonkeyPatch().context() as m:
            # Mock construct_state_cal_tree函数
            mock_node = Mock(spec=StateCalNode)
            mock_node.node_type = StateCalNodeType.STATE
            m.setattr(
                'one_dragon.base.conditional_operation.utils.construct_state_cal_tree',
                Mock(return_value=mock_node)
            )
            
            handler = construct_state_handler(
                state_data,
                mock_state_getter,
                mock_op_getter,
                mock_scene_handler_getter,
                mock_operation_template_getter,
                set()
            )
            
            assert handler.sub_handlers is not None
            assert len(handler.sub_handlers) == 1
    
    def test_construct_state_handler_missing_states(self, mock_state_getter, mock_op_getter, 
                                                  mock_scene_handler_getter, mock_operation_template_getter):
        """测试缺少状态表达式的状态处理器构造"""
        state_data = {
            'operations': [
                {'op_name': 'test_op'}
            ]
        }
        
        with pytest.raises(ValueError, match="未有状态表达式字段"):
            construct_state_handler(
                state_data,
                mock_state_getter,
                mock_op_getter,
                mock_scene_handler_getter,
                mock_operation_template_getter,
                set()
            )
    
    def test_construct_state_handler_empty_operations(self, mock_state_getter, mock_op_getter, 
                                                    mock_scene_handler_getter, mock_operation_template_getter):
        """测试空操作列表的状态处理器构造"""
        state_data = {
            'states': '[test_state, 0, 1]',
            'operations': []
        }
        
        with pytest.MonkeyPatch().context() as m:
            # Mock construct_state_cal_tree函数
            mock_node = Mock(spec=StateCalNode)
            mock_node.node_type = StateCalNodeType.STATE
            m.setattr(
                'one_dragon.base.conditional_operation.utils.construct_state_cal_tree',
                Mock(return_value=mock_node)
            )
            
            with pytest.raises(ValueError, match="状态.*下指令为空"):
                construct_state_handler(
                    state_data,
                    mock_state_getter,
                    mock_op_getter,
                    mock_scene_handler_getter,
                    mock_operation_template_getter,
                    set()
                )
    
    def test_get_ops_from_data_basic(self, mock_op_getter, mock_operation_template_getter):
        """测试从数据获取操作 - 基本情况"""
        operation_data_list = [
            {'op_name': 'test_op1'},
            {'op_name': 'test_op2'}
        ]
        
        ops = get_ops_from_data(
            operation_data_list,
            mock_op_getter,
            mock_operation_template_getter,
            set()
        )
        
        assert len(ops) == 2
        assert all(isinstance(op, Mock) for op in ops)
    
    def test_get_ops_from_data_with_template(self, mock_op_getter, mock_operation_template_getter):
        """测试从数据获取操作 - 使用模板"""
        # Mock操作模板获取器返回一个模板
        mock_template = Mock(spec=OperationTemplate)
        mock_template.get = Mock(return_value=[
            {'op_name': 'template_op1'},
            {'op_name': 'template_op2'}
        ])
        
        def _template_getter(template_name: str) -> OperationTemplate:
            if template_name == 'test_template':
                return mock_template
            return None
        
        operation_data_list = [
            {'operation_template': 'test_template'}
        ]
        
        ops = get_ops_from_data(
            operation_data_list,
            mock_op_getter,
            _template_getter,
            set()
        )
        
        assert len(ops) == 2
        # 验证模板被正确使用
        mock_template.get.assert_called_once_with('operations', [])