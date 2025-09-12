"""状态计算树测试"""
import pytest
from unittest.mock import Mock

from one_dragon.base.conditional_operation.state_cal_tree import (
    StateCalNode, StateCalNodeType, StateCalOpType, construct_state_cal_tree
)
from one_dragon.base.conditional_operation.state_recorder import StateRecorder


class TestStateCalTree:
    
    @pytest.fixture
    def mock_state_recorder(self):
        """创建模拟状态记录器"""
        mock_recorder = Mock(spec=StateRecorder)
        mock_recorder.state_name = 'test_state'
        mock_recorder.last_record_time = 100.0  # 设置一个时间戳
        mock_recorder.last_value = 1
        return mock_recorder
    
    def test_construct_simple_state(self, mock_state_recorder):
        """测试构造简单状态表达式"""
        def state_getter(state_name):
            return mock_state_recorder
        
        # 测试基本状态表达式
        node = construct_state_cal_tree('[test_state, 0, 1]', state_getter)
        assert node.node_type == StateCalNodeType.STATE
        assert node.state_recorder == mock_state_recorder
        assert node.state_time_range_min == 0
        assert node.state_time_range_max == 1
    
    def test_construct_state_with_value_range(self, mock_state_recorder):
        """测试带数值范围的状态表达式"""
        def state_getter(state_name):
            return mock_state_recorder
        
        # 测试带数值范围的状态表达式
        node = construct_state_cal_tree('[test_state, 0, 1]{0, 1}', state_getter)
        assert node.node_type == StateCalNodeType.STATE
        assert node.state_recorder == mock_state_recorder
        assert node.state_time_range_min == 0
        assert node.state_time_range_max == 1
        assert node.state_value_range_min == 0
        assert node.state_value_range_max == 1
    
    def test_construct_and_operation(self, mock_state_recorder):
        """测试AND逻辑运算"""
        def state_getter(state_name):
            return mock_state_recorder
        
        # 测试AND运算
        node = construct_state_cal_tree('[test_state, 0, 1] & [test_state, 0, 1]', state_getter)
        assert node.node_type == StateCalNodeType.OP
        assert node.op_type == StateCalOpType.AND
        assert node.left_child.node_type == StateCalNodeType.STATE
        assert node.right_child.node_type == StateCalNodeType.STATE
    
    def test_construct_or_operation(self, mock_state_recorder):
        """测试OR逻辑运算"""
        def state_getter(state_name):
            return mock_state_recorder
        
        # 测试OR运算
        node = construct_state_cal_tree('[test_state, 0, 1] | [test_state, 0, 1]', state_getter)
        assert node.node_type == StateCalNodeType.OP
        assert node.op_type == StateCalOpType.OR
        assert node.left_child.node_type == StateCalNodeType.STATE
        assert node.right_child.node_type == StateCalNodeType.STATE
    
    def test_construct_not_operation(self, mock_state_recorder):
        """测试NOT逻辑运算"""
        def state_getter(state_name):
            return mock_state_recorder
        
        # 测试NOT运算
        node = construct_state_cal_tree('![test_state, 0, 1]', state_getter)
        assert node.node_type == StateCalNodeType.OP
        assert node.op_type == StateCalOpType.NOT
        assert node.left_child.node_type == StateCalNodeType.STATE
    
    def test_construct_with_parentheses(self, mock_state_recorder):
        """测试括号优先级"""
        def state_getter(state_name):
            return mock_state_recorder
        
        # 测试括号优先级
        node = construct_state_cal_tree('([test_state, 0, 1] & [test_state, 0, 1]) | [test_state, 0, 1]', state_getter)
        assert node.node_type == StateCalNodeType.OP
        assert node.op_type == StateCalOpType.OR
        assert node.left_child.op_type == StateCalOpType.AND
        assert node.right_child.node_type == StateCalNodeType.STATE
    
    def test_construct_empty_expression(self):
        """测试空表达式"""
        def state_getter(state_name):
            return None
        
        # 测试空表达式
        node = construct_state_cal_tree('', state_getter)
        assert node.node_type == StateCalNodeType.TRUE
    
    def test_construct_invalid_syntax_missing_bracket(self, mock_state_recorder):
        """测试无效语法 - 缺少右括号"""
        def state_getter(state_name):
            return mock_state_recorder
        
        with pytest.raises(ValueError, match="找不到对应的右中括号"):
            construct_state_cal_tree('[test_state, 0, 1', state_getter)
    
    def test_construct_invalid_syntax_missing_parentheses(self, mock_state_recorder):
        """测试无效语法 - 缺少右括号"""
        def state_getter(state_name):
            return mock_state_recorder
        
        # 这个表达式有多个状态但没有运算符连接
        with pytest.raises(ValueError):
            construct_state_cal_tree('[test_state1, 0, 1][test_state2, 0, 1]', state_getter)
    
    def test_in_time_range_basic_state(self, mock_state_recorder):
        """测试基本状态时间范围判断"""
        node = StateCalNode(
            node_type=StateCalNodeType.STATE,
            state_recorder=mock_state_recorder,
            state_time_range_min=0,
            state_time_range_max=2
        )
        
        # 模拟当前时间
        mock_state_recorder.last_record_time = 100.0
        
        # 测试在时间范围内
        assert node.in_time_range(101.0) is True  # 差值1.0，在[0,2]范围内
        
        # 测试超出时间范围
        assert node.in_time_range(103.0) is False  # 差值3.0，超出[0,2]范围
    
    def test_in_time_range_with_value_range(self, mock_state_recorder):
        """测试带数值范围的状态判断"""
        node = StateCalNode(
            node_type=StateCalNodeType.STATE,
            state_recorder=mock_state_recorder,
            state_time_range_min=0,
            state_time_range_max=2,
            state_value_range_min=0,
            state_value_range_max=2
        )
        
        # 模拟当前状态
        mock_state_recorder.last_record_time = 100.0
        mock_state_recorder.last_value = 1
        
        # 测试在时间和数值范围内
        assert node.in_time_range(101.0) is True  # 差值1.0，在[0,2]范围内，值1在[0,2]范围内
        
        # 测试数值超出范围
        mock_state_recorder.last_value = 3
        assert node.in_time_range(101.0) is False  # 差值1.0在范围内，但值3超出[0,2]范围
    
    def test_in_time_range_and_operation(self, mock_state_recorder):
        """测试AND运算的时间范围判断"""
        left_node = StateCalNode(
            node_type=StateCalNodeType.STATE,
            state_recorder=mock_state_recorder,
            state_time_range_min=0,
            state_time_range_max=2
        )
        
        right_node = StateCalNode(
            node_type=StateCalNodeType.STATE,
            state_recorder=mock_state_recorder,
            state_time_range_min=0,
            state_time_range_max=2
        )
        
        and_node = StateCalNode(
            node_type=StateCalNodeType.OP,
            op_type=StateCalOpType.AND,
            left_child=left_node,
            right_child=right_node
        )
        
        # 模拟状态时间
        mock_state_recorder.last_record_time = 100.0
        
        # 两个条件都满足
        assert and_node.in_time_range(101.0) is True
        
        # 只有一个条件满足
        assert and_node.in_time_range(103.0) is False
    
    def test_in_time_range_or_operation(self, mock_state_recorder):
        """测试OR运算的时间范围判断"""
        left_node = StateCalNode(
            node_type=StateCalNodeType.STATE,
            state_recorder=mock_state_recorder,
            state_time_range_min=0,
            state_time_range_max=1
        )
        
        right_node = StateCalNode(
            node_type=StateCalNodeType.STATE,
            state_recorder=mock_state_recorder,
            state_time_range_min=2,
            state_time_range_max=3
        )
        
        or_node = StateCalNode(
            node_type=StateCalNodeType.OP,
            op_type=StateCalOpType.OR,
            left_child=left_node,
            right_child=right_node
        )
        
        # 模拟状态时间
        mock_state_recorder.last_record_time = 100.0
        
        # 第一个条件满足
        assert or_node.in_time_range(100.5) is True
        
        # 第二个条件满足
        assert or_node.in_time_range(102.5) is True
        
        # 两个条件都不满足
        assert or_node.in_time_range(101.5) is False
    
    def test_in_time_range_not_operation(self, mock_state_recorder):
        """测试NOT运算的时间范围判断"""
        child_node = StateCalNode(
            node_type=StateCalNodeType.STATE,
            state_recorder=mock_state_recorder,
            state_time_range_min=0,
            state_time_range_max=1
        )
        
        not_node = StateCalNode(
            node_type=StateCalNodeType.OP,
            op_type=StateCalOpType.NOT,
            left_child=child_node
        )
        
        # 模拟状态时间
        mock_state_recorder.last_record_time = 100.0
        
        # 原条件满足，NOT后应为False
        assert not_node.in_time_range(100.5) is False
        
        # 原条件不满足，NOT后应为True
        assert not_node.in_time_range(101.5) is True
    
    def test_get_usage_states(self, mock_state_recorder):
        """测试获取使用状态"""
        node = StateCalNode(
            node_type=StateCalNodeType.STATE,
            state_recorder=mock_state_recorder
        )
        
        states = node.get_usage_states()
        assert mock_state_recorder.state_name in states
    
    def test_get_usage_states_complex(self, mock_state_recorder):
        """测试复杂表达式的使用状态获取"""
        left_node = StateCalNode(
            node_type=StateCalNodeType.STATE,
            state_recorder=mock_state_recorder
        )
        
        right_node = StateCalNode(
            node_type=StateCalNodeType.STATE,
            state_recorder=mock_state_recorder
        )
        
        and_node = StateCalNode(
            node_type=StateCalNodeType.OP,
            op_type=StateCalOpType.AND,
            left_child=left_node,
            right_child=right_node
        )
        
        states = and_node.get_usage_states()
        assert mock_state_recorder.state_name in states