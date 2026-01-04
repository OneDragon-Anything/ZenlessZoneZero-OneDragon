import os

import cv2
import numpy as np
import yaml
from cv2.typing import MatLike

from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.screen.screen_utils import find_template_coord_in_area
from one_dragon.utils import os_utils, cv2_utils, cal_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.world_patrol.mini_map_wrapper import MiniMapWrapper
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolArea, WorldPatrolEntry, WorldPatrolLargeMap, \
    road_mask_path, icon_yaml_path, WorldPatrolLargeMapIcon
from zzz_od.application.world_patrol.world_patrol_route import WorldPatrolRoute, WorldPatrolOpType
from zzz_od.application.world_patrol.world_patrol_route_list import WorldPatrolRouteList
from zzz_od.context.zzz_context import ZContext


def area_route_dir(area: WorldPatrolArea):
    return os_utils.get_path_under_work_dir('config', 'world_patrol_route', 'system',
                                            area.entry.entry_id, area.full_id)


def route_list_dir():
    return os_utils.get_path_under_work_dir('config', 'world_patrol_route_list')


class WorldPatrolService:

    # 小地图相对于"地图"按钮的偏移量（通过观察得出）
    # 小地图坐标 = "地图"坐标 - DELTA
    MINI_MAP_DELTA = (169, 151)

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx

        self.entry_list: list[WorldPatrolEntry] = []
        self.area_list: list[WorldPatrolArea] = []
        self.large_map_list: list[WorldPatrolLargeMap] = []
        self.route_list: list[WorldPatrolRoute] = []

        # 缓存小地图区域
        self._mini_map_rect: Rect | None = None

    def cut_mini_map(self, screen: MatLike) -> MiniMapWrapper:
        """
        截取小地图 - 动态计算裁剪区域

        通过模板匹配"地图"按钮 - delta 值生成准确的裁剪区域

        Args:
            screen: 游戏画面

        Returns:
            MiniMapWrapper: 小地图图片
        """
        # 如果缓存存在，直接使用
        if self._mini_map_rect is not None:
            rgb = cv2_utils.crop_image_only(screen, self._mini_map_rect)
            return MiniMapWrapper(rgb)

        # 获取小地图的默认宽高（从配置中获取）
        default_area = self.ctx.screen_loader.get_area('大世界', '小地图')
        mini_map_width = default_area.rect.width
        mini_map_height = default_area.rect.height

        # 使用模板匹配定位"地图"
        map_result = find_template_coord_in_area(self.ctx, screen, '大世界', '地图')

        if map_result is not None:
            # 通过匹配坐标 - delta 值计算小地图区域（注意是减法！）
            mini_map_x = map_result.x - self.MINI_MAP_DELTA[0]
            mini_map_y = map_result.y - self.MINI_MAP_DELTA[1]

            # 生成裁剪区域
            self._mini_map_rect = Rect(
                mini_map_x,
                mini_map_y,
                mini_map_x + mini_map_width,
                mini_map_y + mini_map_height
            )

            log.info(f'[小地图] 刷新小地图坐标缓存: ({self._mini_map_rect.x1}, {self._mini_map_rect.y1}) - ({self._mini_map_rect.x2}, {self._mini_map_rect.y2})')

            # 使用计算出的区域裁剪
            rgb = cv2_utils.crop_image_only(screen, self._mini_map_rect)
            return MiniMapWrapper(rgb)
        else:
            # 模板匹配失败，降级使用固定区域（不缓存）
            rgb = cv2_utils.crop_image_only(screen, default_area.rect)
            return MiniMapWrapper(rgb)

    def load_data(self):
        self.load_area()
        self.load_area_map()

    def load_area(self):
        self.entry_list = []
        self.area_list = []

        file_path = os.path.join(
            os_utils.get_path_under_work_dir('assets', 'game_data'),
            'map_area_all.yml'
        )
        op = YamlOperator(file_path)
        full_list = op.data.get('full_list', [])
        for entry_data in full_list:
            entry = WorldPatrolEntry(entry_data['entry_name'], entry_data['entry_id'])
            self.entry_list.append(entry)
            for area_data in entry_data.get('area_list', []):
                area = WorldPatrolArea(
                    entry,
                    area_data['area_name'],
                    area_data['area_id'],
                    is_hollow=area_data.get('is_hollow', False),
                )

                if 'sub_area_list' in area_data:
                    area.sub_area_list = []
                    for sub_area_data in area_data['sub_area_list']:
                        sub_area = WorldPatrolArea(
                            entry,
                            sub_area_data['area_name'],
                            sub_area_data['area_id'],
                            is_hollow=area.is_hollow,
                        )
                        sub_area.parent_area = area
                        area.sub_area_list.append(sub_area)
                        self.area_list.append(sub_area)

                self.area_list.append(area)

    def load_area_map(self):
        self.large_map_list = []
        for area in self.area_list:
            road_mask = cv2_utils.read_image(road_mask_path(area))
            if road_mask is None:
                continue
            if road_mask.ndim == 3:
                road_mask = cv2.cvtColor(road_mask, cv2.COLOR_RGB2GRAY)

            icon_data = YamlOperator(icon_yaml_path(area)).data
            icon_list: list[WorldPatrolLargeMapIcon] = []
            for i in icon_data:
                icon_list.append(WorldPatrolLargeMapIcon(
                    icon_name=i.get('icon_name', ''),
                    template_id=i.get('template_id', ''),
                    lm_pos=i.get('lm_pos', None),
                    tp_pos=i.get('tp_pos', None),
                ))

            lm = WorldPatrolLargeMap(area.full_id, road_mask, icon_list)
            self.large_map_list.append(lm)

    def get_area_list_by_entry(self, entry: WorldPatrolEntry) -> list[WorldPatrolArea]:
        return [i for i in self.area_list if i.entry.entry_id == entry.entry_id]

    def get_large_map_by_area_full_id(self, area_full_id: str) -> WorldPatrolLargeMap | None:
        for i in self.large_map_list:
            if i.area_full_id == area_full_id:
                return i
        return None

    def save_world_patrol_large_map(self, area: WorldPatrolArea, large_map: WorldPatrolLargeMap) -> bool:
        """
        保存一个区域的地图

        Args:
            area: 区域
            large_map: 地图

        Returns:
            bool: 是否保存成功
        """
        if area is None or large_map is None:
            log.error('area or large_map is None')
            return False
        if area.full_id != large_map.area_full_id:
            log.error('area full ids are not same')
            return False

        cv2_utils.save_image(large_map.road_mask, road_mask_path(area))

        op = YamlOperator(icon_yaml_path(area))
        op.data = [i.to_dict() for i in large_map.icon_list]
        op.save()

        log.info(f'保存区域地图成功: {area.full_id}')
        self.load_area_map()
        return True

    def delete_world_patrol_large_map(self, area: WorldPatrolArea) -> bool:
        """
        删除一个区域的地图

        Args:
            area: 区域

        Returns:
            bool: 是否删除成功
        """
        target = None
        for i in self.large_map_list:
            if i.area_full_id == area.full_id:
                target = i
                break

        if target is None:
            return False

        self.large_map_list.remove(target)

        if os.path.exists(road_mask_path(area)):
            os.remove(road_mask_path(area))

        if os.path.exists(icon_yaml_path(area)):
            os.remove(icon_yaml_path(area))
        return True

    def get_world_patrol_routes(self) -> list[WorldPatrolRoute]:
        """获取所有路线"""
        routes = []
        for area in self.area_list:
            routes.extend(self.get_world_patrol_routes_by_area(area))
        return routes

    def get_world_patrol_routes_by_area(self, area: WorldPatrolArea) -> list[WorldPatrolRoute]:
        """获取指定区域的所有路线"""
        routes = []
        route_dir = area_route_dir(area)

        if not os.path.exists(route_dir):
            return routes

        # 遍历路线文件夹中的所有yml文件
        for filename in os.listdir(route_dir):
            if filename.endswith('.yml'):
                try:
                    file_path = os.path.join(route_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                    route = WorldPatrolRoute.from_dict(data, area)
                    routes.append(route)
                except Exception as e:
                    log.error(f'加载路线文件失败: {filename}, 错误: {e}')

        # 按idx排序
        routes.sort(key=lambda r: r.idx)
        return routes

    def save_world_patrol_route(self, route: WorldPatrolRoute) -> bool:
        """保存世界巡逻路线"""
        try:
            route_dir = area_route_dir(route.tp_area)
            os.makedirs(route_dir, exist_ok=True)

            filename = f'{route.idx:02d}.yml'
            file_path = os.path.join(route_dir, filename)

            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(route.to_dict(), f, default_flow_style=False, allow_unicode=True)

            log.info(f'保存路线成功: {route.tp_area.full_name} - {route.tp_name} ({filename})')
            return True
        except Exception as e:
            log.error(f'保存路线失败: {e}')
            return False

    def get_next_route_idx(self, area: WorldPatrolArea) -> int:
        """获取指定区域的下一个路线索引"""
        routes = self.get_world_patrol_routes_by_area(area)
        if not routes:
            return 1
        return max(route.idx for route in routes) + 1

    def delete_world_patrol_route(self, route: WorldPatrolRoute) -> bool:
        """删除世界巡逻路线"""
        try:
            route_dir = area_route_dir(route.tp_area)
            filename = f'{route.idx:02d}.yml'
            file_path = os.path.join(route_dir, filename)

            if os.path.exists(file_path):
                os.remove(file_path)
                log.info(f'删除路线成功: {route.tp_area.full_name} - {route.tp_name} ({filename})')
                return True
            else:
                log.error(f'路线文件不存在: {filename}')
                return False

        except Exception as e:
            log.error(f'删除路线失败: {e}')
            return False

    def get_world_patrol_route_lists(self) -> list[WorldPatrolRouteList]:
        """获取所有路线列表"""
        route_lists = []
        list_dir = route_list_dir()

        if not os.path.exists(list_dir):
            return route_lists

        for filename in os.listdir(list_dir):
            if filename.endswith('.yml'):
                try:
                    file_path = os.path.join(list_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                    route_list = WorldPatrolRouteList.from_dict(data)
                    route_lists.append(route_list)
                except Exception as e:
                    log.error(f'加载路线列表失败: {filename}, 错误: {e}')

        return route_lists

    def save_world_patrol_route_list(self, route_list: WorldPatrolRouteList) -> bool:
        """保存路线列表"""
        try:
            list_dir = route_list_dir()
            os.makedirs(list_dir, exist_ok=True)

            filename = f'{route_list.name}.yml'
            file_path = os.path.join(list_dir, filename)

            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(route_list.to_dict(), f, default_flow_style=False, allow_unicode=True)

            log.info(f'保存路线列表成功: {route_list.name} ({route_list.list_type})')
            return True
        except Exception as e:
            log.error(f'保存路线列表失败: {e}')
            return False

    def delete_world_patrol_route_list(self, route_list: WorldPatrolRouteList) -> bool:
        """删除路线列表"""
        try:
            list_dir = route_list_dir()
            filename = f'{route_list.name}.yml'
            file_path = os.path.join(list_dir, filename)

            if os.path.exists(file_path):
                os.remove(file_path)
                log.info(f'删除路线列表成功: {route_list.name}')
                return True
            else:
                log.error(f'路线列表文件不存在: {filename}')
                return False

        except Exception as e:
            log.error(f'删除路线列表失败: {e}')
            return False

    def get_route_large_map(self, route: WorldPatrolRoute) -> WorldPatrolLargeMap | None:
        """
        获取路线对应的大地图

        Args:
            route: 路线

        Returns:
            WorldPatrolLargeMap: 大地图
        """
        for lm in self.large_map_list:
            if lm.area_full_id == route.tp_area.full_id:
                return lm
        return None

    def get_route_tp_icon(self, route: WorldPatrolRoute) -> WorldPatrolLargeMapIcon | None:
        """
        获取路线的传送点

        Args:
            route: 路线

        Returns:
            WorldPatrolLargeMapIcon: 传送点
        """
        large_map = self.get_route_large_map(route)
        if large_map is None:
            return None

        tp_icon = None
        for icon in large_map.icon_list:
            if icon.icon_name == route.tp_name:
                tp_icon = icon
                break

        return tp_icon

    def get_route_pos_before_op_idx(self, route: WorldPatrolRoute, op_idx: int) -> Point | None:
        """
        获取路线 在某个指令之前一个的坐标

        Args:
            route: 路线
            op_idx: 指定的指令下标

        Returns:
            Point: 坐标
        """
        tp_icon = self.get_route_tp_icon(route)
        if tp_icon is None:
            return None
        current_pos = tp_icon.tp_pos
        for idx, op in enumerate(route.op_list):
            if idx >= op_idx:
                return current_pos
            if op.op_type in [
                WorldPatrolOpType.MOVE
            ]:
                current_pos = Point(int(op.data[0]), int(op.data[1]))
        return current_pos

    def get_route_last_pos(self, route: WorldPatrolRoute) -> Point | None:
        """
        获取路线的最后一个点坐标

        Args:
            route: 路线

        Returns:
            Point: 最后一个点坐标
        """
        return self.get_route_pos_before_op_idx(route, len(route.op_list) + 1)

    def cal_pos(
            self,
            large_map: WorldPatrolLargeMap,
            mini_map: MiniMapWrapper,
            lm_rect: Rect,
    ) -> Point | None:
        """
        计算当前小地图在大地图上的坐标

        Args:
            large_map: 大地图
            mini_map: 小地图
            lm_rect: 大地图上考虑的范围

        Returns:
            Point: 坐标
        """
        result = self.cal_pos_by_icon(large_map, mini_map, lm_rect)
        if result is not None:
            return result

        return self.cal_pos_by_road(large_map, mini_map, lm_rect)

    def cal_pos_by_icon(
            self,
            large_map: WorldPatrolLargeMap,
            mini_map: MiniMapWrapper,
            lm_rect: Rect,
    ) -> Point | None:
        """
        根据出现的图标 计算当前小地图在大地图上的坐标

        Args:
            large_map: 大地图
            mini_map: 小地图
            lm_rect: 大地图上考虑的范围

        Returns:
            Point: 坐标
        """
        x1 = lm_rect.x1
        x2 = lm_rect.x2
        y1 = lm_rect.y1
        y2 = lm_rect.y2

        # 找到大地图指定范围有哪些图标
        lm_icon_set: set[str] = set()
        for large_map_icon in large_map.icon_list:
            if large_map_icon.lm_pos.x < x1 or large_map_icon.lm_pos.x > x2:
                continue
            if large_map_icon.lm_pos.y < y1 or large_map_icon.lm_pos.y > y2:
                continue
            lm_icon_set.add(large_map_icon.template_id)

        if len(lm_icon_set) == 0:
            return None

        # 找到小地图能匹配哪些图标
        mm_icon_list: list[tuple[str, Point]] = []
        for icon_template_id in lm_icon_set:
            template = self.ctx.template_loader.get_template('map', icon_template_id)
            if template is None:
                break

            mrl = cv2_utils.match_template(
                source=mini_map.rgb,
                template=template.raw,
                mask=template.mask,
                threshold=0.7,
                only_best=False,
                ignore_inf=True
            )
            for mr in mrl:
                # 计算图标中心点坐标
                center_x = mr.left_top.x + template.raw.shape[1] // 2
                center_y = mr.left_top.y + template.raw.shape[0] // 2
                mm_icon_list.append((template.template_id, Point(center_x, center_y)))

        # 使用小坐标来匹配
        match_list: list[MatchResult] = []
        for large_map_icon in large_map.icon_list:
            if large_map_icon.lm_pos.x < x1 or large_map_icon.lm_pos.x > x2:
                continue
            if large_map_icon.lm_pos.y < y1 or large_map_icon.lm_pos.y > y2:
                continue
            for mini_map_icon_name, mini_map_icon_point in mm_icon_list:
                if mini_map_icon_name != large_map_icon.template_id:
                    continue
                new_point = large_map_icon.lm_pos - mini_map_icon_point
                new_mr = MatchResult(
                    1,
                    new_point.x,
                    new_point.y,
                    mini_map.road_mask.shape[1],
                    mini_map.road_mask.shape[0],
                )

                merged = False
                for old_mr in match_list:
                    if cal_utils.distance_between(new_mr.left_top, old_mr.left_top) < 10:
                        old_mr.confidence += 1
                        merged = True
                        break
                if not merged:
                    match_list.append(new_mr)

        if len(match_list) == 0:
            return None

        # 找置信度最高的结果
        match_list.sort(key=lambda x: x.confidence, reverse=True)
        max_confidence_list = [x for x in match_list if x.confidence == match_list[0].confidence]
        if len(max_confidence_list) == 1:
            return max_confidence_list[0].center

        # 多个候选结果时 比较和原图的相似度
        for mr in max_confidence_list:
            source_part = large_map.road_mask[
                          mr.left_top.y:mr.left_top.y + mini_map.road_mask.shape[0],
                          mr.left_top.x:mr.left_top.x + mini_map.road_mask.shape[1]
                          ]
            # 置信度=相同的数量
            same = cv2.bitwise_and(source_part, mini_map.road_mask)
            mr.confidence = float(np.sum(np.where(same > 0)))

        # 返回置信度最高的
        return max(max_confidence_list, key=lambda x: x.confidence).center

    def cal_pos_by_road(
            self,
            large_map: WorldPatrolLargeMap,
            mini_map: MiniMapWrapper,
            lm_rect: Rect,
    ) -> Point | None:
        """
        根据道路掩码 计算当前小地图在大地图上的坐标

        Args:
            large_map: 大地图
            mini_map: 小地图
            lm_rect: 大地图上考虑的范围

        Returns:
            Point: 坐标
        """
        source, rect = cv2_utils.crop_image(large_map.road_mask, lm_rect)
        template = mini_map.road_mask

        mrl = cv2_utils.match_template(
            source=source,
            template=template,
            threshold=0.1,
            ignore_inf=True,
        )

        if rect is not None:
            mrl.add_offset(rect.left_top)

        return None if mrl.max is None else mrl.max.center
