from dataclasses import dataclass
from typing import Dict, Optional

APP_ID = "shiyu_defense"
APP_NAME = "式舆防卫战"
NEED_NOTIFY = True


@dataclass
class MultiRoomNodeConfig:
    """多间模式节点配置"""
    room_count: int  # 房间数量
    screen_template: str  # 屏幕模板名称
    node_area: str  # 节点点击区域名称


# 多间模式节点配置字典
# key: 节点索引, value: 节点配置
MULTI_ROOM_NODES: Dict[int, MultiRoomNodeConfig] = {
    5: MultiRoomNodeConfig(
        room_count=3,
        screen_template='新式舆防卫战',
        node_area='节点-05'
    ),
    # 未来可以添加更多节点
    # 6: MultiRoomNodeConfig(
    #     room_count=3,
    #     screen_template='新式舆防卫战',
    #     node_area='节点-06'
    # ),
}


def is_multi_room_node(node_idx: int) -> bool:
    """判断节点是否为多间模式"""
    return node_idx in MULTI_ROOM_NODES


def get_multi_room_config(node_idx: int) -> Optional[MultiRoomNodeConfig]:
    """获取多间模式节点配置"""
    return MULTI_ROOM_NODES.get(node_idx)
