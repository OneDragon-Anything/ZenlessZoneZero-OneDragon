import os
from functools import cached_property

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.utils import os_utils


class WorldPatrolEntry:

    def __init__(self, entry_name: str, entry_id: str):
        self.entry_name: str = entry_name
        self.entry_id: str = entry_id


class WorldPatrolArea:

    def __init__(
            self,
            entry: WorldPatrolEntry,
            area_name: str,
            area_id: str,
            is_hollow: bool = False,
    ):
        self.entry: WorldPatrolEntry = entry
        self.area_name: str = area_name
        self.area_id: str = area_id
        self.is_hollow: bool = is_hollow

        self.parent_area: "WorldPatrolArea | None" = None
        self.sub_area_list: "list[WorldPatrolArea] | None" = None

    @cached_property
    def full_id(self) -> str:
        if self.parent_area is None:
            return self.area_id
        else:
            return f'{self.parent_area.full_id}_{self.area_id}'

    @cached_property
    def full_name(self) -> str:
        if self.parent_area is None:
            return self.area_name
        else:
            return f'{self.parent_area.full_name}_{self.area_name}'


class WorldPatrolLargeMapIcon:

    def __init__(
            self,
            icon_name: str,
            template_id: str,
            lm_pos: list[int],
            tp_pos: list[int] | None,
    ):
        self.icon_name: str = icon_name
        self.template_id: str = template_id
        self.lm_pos: Point = Point(lm_pos[0], lm_pos[1])  # 图标中心点在大地图上的坐标
        self.tp_pos: Point = self.lm_pos if tp_pos is None else Point(tp_pos[0], tp_pos[1])  # 传送落地后的坐标

    def to_dict(self) -> dict:
        return {
            'icon_name': self.icon_name,
            'template_id': self.template_id,
            'lm_pos': [self.lm_pos.x, self.lm_pos.y],
            'tp_pos': [self.tp_pos.x, self.tp_pos.y],
        }


class WorldPatrolLargeMap:

    def __init__(
            self,
            area_full_id: str,
            road_mask: MatLike,
            icon_list: list[WorldPatrolLargeMapIcon],
    ):
        self.area_full_id: str = area_full_id
        self.road_mask: MatLike = road_mask
        self.icon_list: list[WorldPatrolLargeMapIcon] = icon_list

    def to_dict(self) -> dict:
        return {
            'area_full_id': self.area_full_id,
            'icon_list': [i.to_dict() for i in self.icon_list],
        }


def world_patrol_dir():
    return os_utils.get_path_under_work_dir('assets', 'game_data', 'world_patrol')


def entry_dir(entry: WorldPatrolEntry):
    return os_utils.get_path_under_work_dir('assets', 'game_data', 'world_patrol', entry.entry_id)


def area_dir(area: WorldPatrolArea):
    return os_utils.get_path_under_work_dir('assets', 'game_data', 'world_patrol', area.entry.entry_id, area.full_id)


def road_mask_path(area: WorldPatrolArea):
    return os.path.join(area_dir(area), 'road_mask.png')


def icon_yaml_path(area: WorldPatrolArea):
    return os.path.join(area_dir(area), 'icon.yml')
