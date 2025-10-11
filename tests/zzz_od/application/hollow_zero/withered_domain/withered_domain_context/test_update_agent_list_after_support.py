"""
测试 update_agent_list_after_support 函数的各种场景
"""

import pytest
from unittest.mock import Mock

from zzz_od.application.hollow_zero.withered_domain.withered_domain_context import (
    WitheredDomainContext,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum


class TestUpdateAgentListAfterSupport:
    @pytest.fixture
    def mock_zzz_context(self):
        """创建模拟的ZContext"""
        mock_ctx = Mock(spec=ZContext)
        return mock_ctx

    @pytest.fixture
    def withered_domain_context(self, mock_zzz_context):
        """创建WitheredDomainContext实例"""
        return WitheredDomainContext(mock_zzz_context)

    def test_add_agent_to_empty_position(self, withered_domain_context):
        """测试将代理人添加到空位置"""
        withered_domain_context.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]

        withered_domain_context.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 2
        )

        assert withered_domain_context.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert withered_domain_context.agent_list[1] == AgentEnum.QINGYI.value
        assert withered_domain_context.agent_list[2] is None

    def test_replace_agent_at_position_1_with_empty_slot_available(
        self, withered_domain_context
    ):
        """测试在1号位替换代理人有空位可用的情况"""
        withered_domain_context.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]

        withered_domain_context.update_agent_list_after_support(
            AgentEnum.NICOLE.value, 1
        )

        assert withered_domain_context.agent_list[0] == AgentEnum.NICOLE.value
        assert withered_domain_context.agent_list[1] == AgentEnum.ZHU_YUAN.value
        assert withered_domain_context.agent_list[2] is None

    def test_add_agent_to_position_3_with_empty_slot(self, withered_domain_context):
        """测试将代理人添加到3号位（有空位）"""
        withered_domain_context.agent_list = [
            AgentEnum.ZHU_YUAN.value,
            AgentEnum.QINGYI.value,
            None,
        ]

        withered_domain_context.update_agent_list_after_support(
            AgentEnum.NICOLE.value, 3
        )

        assert withered_domain_context.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert withered_domain_context.agent_list[1] == AgentEnum.QINGYI.value
        assert withered_domain_context.agent_list[2] == AgentEnum.NICOLE.value

    def test_replace_agent_at_position_2_with_empty_slot_available(
        self, withered_domain_context
    ):
        """测试在2号位替换代理人有空位可用的情况"""
        withered_domain_context.agent_list = [
            AgentEnum.ZHU_YUAN.value,
            AgentEnum.NICOLE.value,
            None,
        ]

        withered_domain_context.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 2
        )

        assert withered_domain_context.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert withered_domain_context.agent_list[1] == AgentEnum.QINGYI.value
        assert withered_domain_context.agent_list[2] == AgentEnum.NICOLE.value

    def test_replace_agent_at_position_2_with_no_empty_slots(
        self, withered_domain_context
    ):
        """测试在2号位替换代理人没有空位的情况"""
        withered_domain_context.agent_list = [
            AgentEnum.ZHU_YUAN.value,
            AgentEnum.LYCAON.value,
            AgentEnum.NICOLE.value,
        ]

        withered_domain_context.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 2
        )

        assert withered_domain_context.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert withered_domain_context.agent_list[1] == AgentEnum.QINGYI.value
        assert withered_domain_context.agent_list[2] == AgentEnum.NICOLE.value

    def test_none_agent_list_no_change(self, withered_domain_context):
        """测试agent_list为None时无变化"""
        withered_domain_context.agent_list = None

        withered_domain_context.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 2
        )

        assert withered_domain_context.agent_list is None

    def test_invalid_position_greater_than_list_length(self, withered_domain_context):
        """测试位置超出列表长度时无变化"""
        withered_domain_context.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]

        withered_domain_context.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 5
        )

        assert withered_domain_context.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert withered_domain_context.agent_list[1] is None
        assert withered_domain_context.agent_list[2] is None

    def test_multiple_empty_slots_replacement_logic(self, withered_domain_context):
        """测试多个空位时的替换逻辑"""
        withered_domain_context.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]

        # 替换1号位，原有角色应该移动到第一个空位（2号位）
        withered_domain_context.update_agent_list_after_support(
            AgentEnum.NICOLE.value, 1
        )

        assert withered_domain_context.agent_list[0] == AgentEnum.NICOLE.value
        assert withered_domain_context.agent_list[1] == AgentEnum.ZHU_YUAN.value
        assert withered_domain_context.agent_list[2] is None

    def test_full_team_replacement_middle_position(self, withered_domain_context):
        """测试满编队伍时替换中间位置"""
        withered_domain_context.agent_list = [
            AgentEnum.ANBY.value,
            AgentEnum.BILLY.value,
            AgentEnum.NICOLE.value,
        ]

        withered_domain_context.update_agent_list_after_support(
            AgentEnum.ZHU_YUAN.value, 2
        )

        assert withered_domain_context.agent_list[0] == AgentEnum.ANBY.value
        assert withered_domain_context.agent_list[1] == AgentEnum.ZHU_YUAN.value
        assert withered_domain_context.agent_list[2] == AgentEnum.NICOLE.value

    def test_edge_case_position_zero(self, withered_domain_context):
        """测试位置为0的边界情况"""
        withered_domain_context.agent_list = [AgentEnum.ZHU_YUAN.value, None, None]

        withered_domain_context.update_agent_list_after_support(
            AgentEnum.QINGYI.value, 0
        )

        # 位置0会导致idx=-1，访问最后一个元素。因为位置为空，直接赋值
        assert withered_domain_context.agent_list[0] == AgentEnum.ZHU_YUAN.value
        assert withered_domain_context.agent_list[1] is None
        assert withered_domain_context.agent_list[2] is None
