from enum import StrEnum
from functools import cached_property

from one_dragon.base.geometry.point import Point
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolArea


class WorldPatrolOpType(StrEnum):

    MOVE = 'move'


class WorldPatrolOperation:

    def __init__(self, op_type: str, data: list[str]):
        self.op_type: str = op_type
        self.data: list[str] = data

    def to_dict(self) -> dict:
        return {
            'op_type': str(self.op_type),
            'data': self.data
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'WorldPatrolOperation':
        return cls(data['op_type'], data['data'])


class WorldPatrolRoute:

    def __init__(
            self,
            tp_area: WorldPatrolArea,
            tp_name: str,  # 对应 map_icon_01 的 icon_name
            idx: int = 0,  # 唯一标识
            op_list: list[WorldPatrolOperation] = None,
    ):
        self.tp_area: WorldPatrolArea = tp_area
        self.tp_name: str = tp_name
        self.idx: int = idx
        self.op_list: list[WorldPatrolOperation] = op_list or []

    def add_move_operation(self, pos: Point):
        """添加移动操作"""
        move_op = WorldPatrolOperation(
            op_type=WorldPatrolOpType.MOVE,
            data=[str(pos.x), str(pos.y)]
        )
        self.op_list.append(move_op)

    def to_dict(self) -> dict:
        return {
            'tp_area_id': self.tp_area.full_id,
            'tp_name': self.tp_name,
            'idx': self.idx,
            'op_list': [op.to_dict() for op in self.op_list]
        }

    @classmethod
    def from_dict(cls, data: dict, area: WorldPatrolArea) -> 'WorldPatrolRoute':
        op_list = [WorldPatrolOperation.from_dict(op_data) for op_data in data.get('op_list', [])]
        return cls(
            tp_area=area,
            tp_name=data['tp_name'],
            idx=data.get('idx', 0),
            op_list=op_list
        )

    @cached_property
    def full_id(self) -> str:
        return f'{self.tp_area.full_id}_{self.idx}'
