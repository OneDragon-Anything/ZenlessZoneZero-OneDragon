"""状态记录器测试"""
import pytest
from unittest.mock import Mock

from one_dragon.base.conditional_operation.state_recorder import StateRecorder, StateRecord


class TestStateRecorder:
    
    @pytest.fixture
    def state_recorder(self):
        """创建状态记录器实例"""
        return StateRecorder('test_state', ['mutex_state'])
    
    def test_init(self, state_recorder):
        """测试初始化"""
        assert state_recorder.state_name == 'test_state'
        assert state_recorder.mutex_list == ['mutex_state']
        assert state_recorder.last_record_time == -1
        assert state_recorder.last_value is None
    
    def test_init_no_mutex(self):
        """测试无互斥状态的初始化"""
        recorder = StateRecorder('test_state')
        assert recorder.state_name == 'test_state'
        assert recorder.mutex_list is None
        assert recorder.last_record_time == -1
        assert recorder.last_value is None
    
    def test_update_state_record_basic(self, state_recorder):
        """测试基本状态记录更新"""
        record = StateRecord('test_state', trigger_time=100.0, value=5)
        state_recorder.update_state_record(record)
        
        assert state_recorder.last_record_time == 100.0
        assert state_recorder.last_value == 5
    
    def test_update_state_record_with_value_add(self, state_recorder):
        """测试带值增加的状态记录更新"""
        # 先设置初始值
        state_recorder.last_value = 10
        record = StateRecord('test_state', trigger_time=100.0, value_to_add=5)
        state_recorder.update_state_record(record)
        
        assert state_recorder.last_record_time == 100.0
        assert state_recorder.last_value == 15  # 10 + 5
    
    def test_update_state_record_with_trigger_time_add(self, state_recorder):
        """测试带触发时间增加的状态记录更新"""
        # 先设置初始时间
        state_recorder.last_record_time = 100.0
        record = StateRecord('test_state', trigger_time=100.0, trigger_time_add=5.0)
        state_recorder.update_state_record(record)
        
        assert state_recorder.last_record_time == 95.0  # 100.0 - 5.0
        # 不改变值，但会初始化为0
        assert state_recorder.last_value == 0
    
    def test_update_state_record_with_trigger_time_add_not_exist(self, state_recorder):
        """测试状态不存在时的时间增加"""
        # 状态未触发过(-1)，时间增加应被忽略
        state_recorder.last_record_time = -1
        record = StateRecord('test_state', trigger_time=100.0, trigger_time_add=5.0)
        state_recorder.update_state_record(record)
        
        assert state_recorder.last_record_time == -1  # 应该保持不变
        # 不改变值，但会初始化为0
        assert state_recorder.last_value == 0
    
    def test_clear_state_record(self, state_recorder):
        """测试清除状态记录"""
        # 先设置状态
        state_recorder.last_record_time = 100.0
        state_recorder.last_value = 5
        
        state_recorder.clear_state_record()
        
        assert state_recorder.last_record_time == 0  # 清除后为0
        assert state_recorder.last_value is None
    
    def test_clear_state_record_not_exist(self, state_recorder):
        """测试清除不存在的状态记录"""
        # 状态未触发过(-1)
        state_recorder.clear_state_record()
        
        assert state_recorder.last_record_time == -1  # 应该保持不变
        assert state_recorder.last_value is None
    
    def test_dispose(self, state_recorder):
        """测试销毁"""
        state_recorder.dispose()
        
        assert state_recorder.state_name is None
        assert state_recorder.mutex_list is None
        assert state_recorder.last_value is None
        assert state_recorder.last_value is None


class TestStateRecord:
    
    def test_init_basic(self):
        """测试基本初始化"""
        record = StateRecord('test_state', trigger_time=100.0, value=5)
        assert record.state_name == 'test_state'
        assert record.trigger_time == 100.0
        assert record.value == 5
        assert record.value_add is None
        assert record.trigger_time_add is None
        assert record.is_clear is False
    
    def test_init_clear(self):
        """测试清除状态初始化"""
        record = StateRecord('test_state', is_clear=True)
        assert record.state_name == 'test_state'
        assert record.is_clear is True
        assert record.trigger_time == 0
        assert record.value is None
    
    def test_init_with_additions(self):
        """测试带增加值的初始化"""
        record = StateRecord(
            'test_state', 
            trigger_time=100.0, 
            value=5, 
            value_to_add=2, 
            trigger_time_add=1.0
        )
        assert record.state_name == 'test_state'
        assert record.trigger_time == 100.0
        assert record.value == 5
        assert record.value_add == 2
        assert record.trigger_time_add == 1.0
        assert record.is_clear is False
    
    def test_str_representation(self):
        """测试字符串表示"""
        record = StateRecord('test_state', trigger_time=100.0, value=5, value_to_add=2)
        result = str(record)
        # 字符串表示应该包含状态名称和值
        assert 'test_state' in result
        assert '100.00' in result
        assert '5' in result
        assert '2' in result