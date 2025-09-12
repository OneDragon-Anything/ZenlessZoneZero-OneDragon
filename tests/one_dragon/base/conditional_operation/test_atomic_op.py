"""原子操作测试"""
import pytest
from unittest.mock import Mock

from one_dragon.base.conditional_operation.atomic_op import AtomicOp


class TestAtomicOp:
    
    def test_init(self):
        """测试初始化"""
        op = AtomicOp('test_op', async_op=True)
        assert op.op_name == 'test_op'
        assert op.async_op is True
    
    def test_init_default_async(self):
        """测试默认异步标志"""
        op = AtomicOp('test_op')
        assert op.op_name == 'test_op'
        assert op.async_op is False
    
    def test_execute(self):
        """测试执行方法"""
        op = AtomicOp('test_op')
        # execute方法应该可以被调用，即使没有具体实现
        op.execute()  # 不应该抛出异常
    
    def test_dispose(self):
        """测试销毁方法"""
        op = AtomicOp('test_op')
        # dispose方法应该可以被调用，即使没有具体实现
        op.dispose()  # 不应该抛出异常
    
    def test_stop(self):
        """测试停止方法"""
        op = AtomicOp('test_op')
        # stop方法应该可以被调用，即使没有具体实现
        op.stop()  # 不应该抛出异常