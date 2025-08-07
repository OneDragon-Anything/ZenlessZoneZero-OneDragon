from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolLargeMapIcon, WorldPatrolLargeMap


class LargeMapSnapshot(WorldPatrolLargeMap):

    def __init__(
            self,
            world_patrol_large_map: WorldPatrolLargeMap,
            pos_after_merge: Point,
    ):
        # Copy data from WorldPatrolLargeMap to avoid modifying original data
        area_full_id = world_patrol_large_map.area_full_id
        road_mask = world_patrol_large_map.road_mask.copy() if world_patrol_large_map.road_mask is not None else None
        icon_list = [
            WorldPatrolLargeMapIcon(
                icon_name=icon.icon_name,
                template_id=icon.template_id,
                lm_pos=[icon.lm_pos.x, icon.lm_pos.y],
                tp_pos=[icon.tp_pos.x, icon.tp_pos.y] if icon.tp_pos else None,
            )
            for icon in world_patrol_large_map.icon_list
        ]

        # Initialize parent class with copied data
        super().__init__(area_full_id, road_mask, icon_list)

        # Add the additional property for snapshot functionality
        self.pos_after_merge: Point = pos_after_merge


class MiniMapSnapshot:

    def __init__(self, road_mask: MatLike, icon_list: list[tuple[str, Point]]):
        self.road_mask: MatLike = road_mask
        self.icon_list: list[tuple[str, Point]] = icon_list