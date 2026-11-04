from dataclasses import dataclass, field

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.screen.template_loader import TemplateLoader
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)

# Tab 菜单地图页里 MAP 一栏的范围 1080p 左边 LEGEND 是图例 不在范围内
MAP_RECT: tuple[int, int, int, int] = (460, 235, 1050, 1045)

# 地图图标模板 assets/template/lost_void/map_icon_* -> 区域类型名称
ICON_TEMPLATE_MAP: dict[str, str] = {
    'map_icon_combat_resonium': LostVoidRegionType.COMBAT_RESONIUM.value.value,
    'map_icon_combat_gear': LostVoidRegionType.COMBAT_GEAR.value.value,
    'map_icon_combat_gear_skull': LostVoidRegionType.COMBAT_GEAR.value.value,  # 右上角骷髅角标 = 环境战吼 类型不变
    'map_icon_combat_coin': LostVoidRegionType.COMBAT_COIN.value.value,
    'map_icon_challenge_flawless': LostVoidRegionType.CHANLLENGE_FLAWLESS.value.value,
    'map_icon_challenge_time_trial': LostVoidRegionType.CHANLLENGE_TIME_TRAIL.value.value,
    'map_icon_challenge_enemy_trial': LostVoidRegionType.CHANLLENGE_ENEMY_TRAIL.value.value,
    'map_icon_encounter': LostVoidRegionType.ENCOUNTER.value.value,
    'map_icon_price_difference': LostVoidRegionType.PRICE_DIFFERENCE.value.value,
    'map_icon_rest': LostVoidRegionType.REST.value.value,
    'map_icon_bangboo_store': LostVoidRegionType.BANGBOO_STORE.value.value,
}

BIG_SCALE_LIST: list[float] = [0.9, 0.95, 1.0, 1.05, 1.1]  # 一个节点只有一个图标时 图标和模板一样大
SMALL_SCALE_LIST: list[float] = [0.5, 0.55, 0.6, 0.65]  # 一个节点叠了几个小图标时 小图标约为模板的 0.6
BIG_MATCH_THRESHOLD: float = 0.6
SMALL_MATCH_THRESHOLD: float = 0.7

# 节点右上角环境角标(骷髅 / 毒雾)的位置 相对节点中心 白色圆块直径约 20
BADGE_OFFSET: tuple[int, int] = (22, -20)
BADGE_RADIUS: int = 12
BADGE_MIN_WHITE: int = 60  # 圆里白色像素至少这么多才算有角标
PASS_BY_DIST: int = 17  # 线头延长线离节点中心超过这个距离(大节点按半径一半)算从节点旁边经过 实测连到的线不超过 14 经过的线 20 以上


@dataclass
class LostVoidMapNode:

    idx: int  # 按从下往上、从左往右排的编号
    center: tuple[int, int]  # 屏幕坐标
    radius: int  # 节点图标大约的半径
    bright: bool  # 图标是亮的 = 还能走到 暗的 = 走过或已经走不到
    region_type_list: list[str] = field(default_factory=list)  # 只识别亮的节点 叠了几个图标时有多个
    is_current: bool = False  # 当前位置 外面有发光圆圈
    is_boss: bool = False  # 最上面的 THRONE 本层终点 进去是道中危机
    row: int = 0  # 从下往上第几行 最下面的起点是第 0 行
    next_list: list[int] = field(default_factory=list)  # 往上直接相连的节点编号


@dataclass
class LostVoidMap:

    node_list: list[LostVoidMapNode]
    current: LostVoidMapNode | None

    def get_node(self, idx: int) -> LostVoidMapNode:
        return self.node_list[idx]

    def get_reachable_list(self) -> list[LostVoidMapNode]:
        """
        从当前位置往上能走到的节点 不含当前位置 按编号排序
        """
        if self.current is None:
            return []
        visited: set[int] = set()
        queue: list[int] = list(self.current.next_list)
        while len(queue) > 0:
            idx = queue.pop(0)
            if idx in visited:
                continue
            visited.add(idx)
            queue.extend(self.node_list[idx].next_list)
        return [self.node_list[i] for i in sorted(visited)]

    @staticmethod
    def type_text(node: LostVoidMapNode) -> str:
        if node.is_boss:
            return f'THRONE 本层终点 {node.region_type_list[0]}'
        if len(node.region_type_list) == 0:
            return '未识别'
        if len(node.region_type_list) == 1:
            return node.region_type_list[0]
        return f'混合节点（{"、".join(node.region_type_list)}）'

    def describe(self) -> str:
        """
        写进日志的文字地图 只列当前位置和往上能走到的节点
        """
        if self.current is None:
            return '未识别到当前位置'

        def join_idx(idx_list: list[int]) -> str:
            return '、'.join(f'节点{i}' for i in idx_list) if len(idx_list) > 0 else '无'

        line_list: list[str] = [
            f'当前位置：节点{self.current.idx}（{self.type_text(self.current)}），第{self.current.row}行',
            f'当前位置往上直接连到：{join_idx(self.current.next_list)}',
            '从当前位置往上能走到的节点（行号从下往上数，最下面的起点是第0行）：',
        ]
        for node in self.get_reachable_list():
            if node.is_boss:
                line_list.append(f'- 节点{node.idx}｜第{node.row}行｜{self.type_text(node)}')
            else:
                line_list.append(f'- 节点{node.idx}｜第{node.row}行｜{self.type_text(node)}｜往上连到：{join_idx(node.next_list)}')
        return '\n'.join(line_list)

    def find_best_route(self, region_type_priority: list[str], blocked_type_list: list[str]) -> list[int]:
        """
        按区域优先级找从当前位置往上最好的路线
        比较方法：先比路线上最优先那种区域的个数 多的更好；一样多再比第二优先的 依次类推；全一样取先找到的
        混合节点按里面最优先的类型算 不在优先级里的类型不算数
        :param region_type_priority: 区域类型优先级 排前面的更优先
        :param blocked_type_list: 当前房间寻路会忽略的入口类型 第一步不走全是这些类型的节点
        :return: 依次要进入的节点编号 没识别到当前位置或往上没有连线时为空
        """
        if self.current is None:
            return []

        def get_score(route: list[int]) -> tuple[int, ...]:
            cnt_list = [0] * len(region_type_priority)
            for idx in route:
                rank_list = [region_type_priority.index(t) for t in self.node_list[idx].region_type_list
                             if t in region_type_priority]
                if len(rank_list) > 0:
                    cnt_list[min(rank_list)] += 1
            return tuple(cnt_list)

        best_route: list[int] = []
        best_score: tuple[int, ...] | None = None
        stack: list[list[int]] = [
            [i] for i in reversed(self.current.next_list)
            if not (len(self.node_list[i].region_type_list) > 0
                    and all(t in blocked_type_list for t in self.node_list[i].region_type_list))
        ]
        while len(stack) > 0:
            route = stack.pop()
            next_list = self.node_list[route[-1]].next_list
            if len(next_list) > 0:
                stack.extend(route + [i] for i in reversed(next_list))
                continue
            score = get_score(route)
            if best_score is None or score > best_score:
                best_route, best_score = route, score
        return best_route


class LostVoidMapReader:
    """
    识别 Tab 地图页 得到节点类型和连接关系
    地图从下往上走 节点只有图标没有文字 节点之间用灰色虚线相连
    - 节点：彩色图标 亮的是还能走到的 暗的是走过或走不到的
    - 当前位置：外面有一个发光圆圈 在起点时圈里是白色的挚交会谈图标
    - 终点：最上面紫色的 THRONE
    """

    def __init__(self, template_loader: TemplateLoader):
        self.template_list: list[tuple[str, MatLike, MatLike]] = []  # (模板id, 模板 RGB, 掩码)
        for template_id in ICON_TEMPLATE_MAP:
            template = template_loader.get_template('lost_void', template_id)
            if template is None or template.raw is None:
                continue
            mask = template.mask if template.mask is not None else np.full(template.raw.shape[:2], 255, np.uint8)
            if mask.ndim == 3:
                mask = mask[:, :, 0]
            self.template_list.append((template_id, template.raw[:, :, :3], mask))

    def read(self, screen: MatLike) -> LostVoidMap:
        """
        :param screen: Tab 菜单地图页截图 RGB
        """
        x0, y0, x1, y1 = MAP_RECT
        part = screen[y0:y1, x0:x1]
        hsv = cv2.cvtColor(part, cv2.COLOR_RGB2HSV)
        color_mask = ((hsv[:, :, 1] > 90) & (hsv[:, :, 2] > 45)).astype(np.uint8)

        ring_center, boss_rect = self._find_ring_and_boss(color_mask)

        node_list: list[LostVoidMapNode] = []
        if boss_rect is not None:
            bx1, by1, bx2, by2 = boss_rect
            node_list.append(LostVoidMapNode(idx=-1, center=((bx1 + bx2) // 2, (by1 + by2) // 2),
                                             radius=max(bx2 - bx1, by2 - by1) // 2, bright=True, is_boss=True,
                                             region_type_list=[LostVoidRegionType.ELITE.value.value]))
        node_list.extend(self._find_icon_node_list(part, hsv, color_mask))
        node_list.extend(self._find_white_top_node(hsv, node_list, boss_rect))

        # 圆圈里的就是当前位置 在起点时圈里是白色图标 识别不到彩色节点 直接补一个
        current: LostVoidMapNode | None = None
        if ring_center is not None:
            for node in node_list:
                if abs(node.center[0] - ring_center[0]) < 30 and abs(node.center[1] - ring_center[1]) < 30:
                    current = node
                    break
            if current is None:
                current = LostVoidMapNode(idx=-1, center=ring_center, radius=40, bright=True,
                                          region_type_list=[LostVoidRegionType.FRIENDLY_TALK.value.value])
                node_list.append(current)
            current.is_current = True
            current.radius = max(current.radius, 55)  # 圆圈比图标大 连线从圆圈外开始

        # 先分行 再按从下往上、从左往右编号
        node_list.sort(key=lambda n: -n.center[1])
        self._set_row(node_list)
        node_list.sort(key=lambda n: (n.row, n.center[0]))
        for idx, node in enumerate(node_list):
            node.idx = idx

        for node in node_list:
            if node.bright and not node.is_boss and len(node.region_type_list) == 0:
                template_id_list = self._match_icon(part, node)
                for template_id in template_id_list:
                    if ICON_TEMPLATE_MAP[template_id] not in node.region_type_list:
                        node.region_type_list.append(ICON_TEMPLATE_MAP[template_id])

        self._find_edge(hsv, node_list, boss_rect)

        # 换回屏幕坐标
        for node in node_list:
            node.center = (node.center[0] + x0, node.center[1] + y0)

        return LostVoidMap(node_list=node_list, current=current)

    @staticmethod
    def _find_ring_and_boss(color_mask: MatLike) -> tuple[tuple[int, int] | None, tuple[int, int, int, int] | None]:
        """
        找当前位置的发光圆圈和最上面的 THRONE 找到后从掩码里去掉 不当作普通节点
        :return: 圆圈中心, THRONE 范围 x1 y1 x2 y2
        """
        ring_center: tuple[int, int] | None = None
        boss_rect: list[int] | None = None
        n, lab, stats, centroids = cv2.connectedComponentsWithStats(color_mask)
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            if 90 <= w <= 130 and 90 <= h <= 130:
                ring_center = (x + w // 2, y + h // 2)
                color_mask[lab == i] = 0
            elif area > 1500 and y < 150:
                # THRONE 后面紫色的 X 会拆成几块
                if boss_rect is None:
                    boss_rect = [x, y, x + w, y + h]
                else:
                    boss_rect = [min(boss_rect[0], x), min(boss_rect[1], y),
                                 max(boss_rect[2], x + w), max(boss_rect[3], y + h)]

        if boss_rect is not None:
            # THRONE 文字等小块挨着紫色的 X 也并进来
            for i in range(1, n):
                x, y, w, h, _ = stats[i]
                if (x < boss_rect[2] + 10 and x + w > boss_rect[0] - 10
                        and y < boss_rect[3] + 10 and y + h > boss_rect[1] - 10):
                    boss_rect = [min(boss_rect[0], x), min(boss_rect[1], y),
                                 max(boss_rect[2], x + w), max(boss_rect[3], y + h)]
            boss_rect = [boss_rect[0] - 10, max(0, boss_rect[1] - 10), boss_rect[2] + 10, boss_rect[3] + 10]
            color_mask[:boss_rect[3], boss_rect[0]:boss_rect[2]] = 0
            return ring_center, (boss_rect[0], boss_rect[1], boss_rect[2], boss_rect[3])
        return ring_center, None

    @staticmethod
    def _find_icon_node_list(part: MatLike, hsv: MatLike, color_mask: MatLike) -> list[LostVoidMapNode]:
        """
        彩色图标扩大后连在一起的算一个节点 叠了几个小图标的混合节点也会连成一个
        """
        merged = cv2.dilate(color_mask, np.ones((25, 25), np.uint8))
        n, lab, stats, _ = cv2.connectedComponentsWithStats(merged)
        node_list: list[LostVoidMapNode] = []
        for i in range(1, n):
            x, y, w, h, _ = stats[i]
            in_node = (lab == i) & (color_mask > 0)
            if np.count_nonzero(in_node) < 150:  # 零散的小色块
                continue
            # 走过的节点右下角有绿色对勾 算亮度时去掉
            hue = hsv[:, :, 0][in_node]
            value = hsv[:, :, 2][in_node]
            not_check = (hue < 55) | (hue > 75)
            bright = np.median(value[not_check]) > 180 if np.any(not_check) else False
            ys, xs = np.where(in_node)
            cx = (int(xs.min()) + int(xs.max())) // 2
            cy = (int(ys.min()) + int(ys.max())) // 2
            radius = max(int(xs.max()) - int(xs.min()), int(ys.max()) - int(ys.min())) // 2
            node_list.append(LostVoidMapNode(idx=-1, center=(cx, cy), radius=radius, bright=bool(bright)))
        return node_list

    @staticmethod
    def _get_gray_mask(hsv: MatLike) -> MatLike:
        """
        灰白色的部分 虚线、白色的挚交会谈图标、节点右上角的环境角标都在里面
        """
        return ((hsv[:, :, 1] < 70) & (hsv[:, :, 2] >= 100) & (hsv[:, :, 2] <= 215)).astype(np.uint8)

    @staticmethod
    def _find_white_top_node(hsv: MatLike, node_list: list[LostVoidMapNode],
                             boss_rect: tuple[int, int, int, int] | None) -> list[LostVoidMapNode]:
        """
        第三层 THRONE 下面是最后一个挚交会谈 图标是白色的 彩色掩码找不到 按灰白色块找
        只在最上面一行彩色节点和 THRONE 之间找 虚线一段只有几十个像素 图标的块大得多
        """
        icon_list = [i for i in node_list if not i.is_boss]
        if boss_rect is None or len(icon_list) == 0:
            return []
        top_y = min(i.center[1] for i in icon_list)

        rect: list[int] | None = None
        n, _, stats, _ = cv2.connectedComponentsWithStats(LostVoidMapReader._get_gray_mask(hsv))
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            if area < 150 or y < boss_rect[3] or y + h > top_y - 60:
                continue
            if rect is None:
                rect = [x, y, x + w, y + h]
            else:
                rect = [min(rect[0], x), min(rect[1], y), max(rect[2], x + w), max(rect[3], y + h)]
        if rect is None:
            return []
        return [LostVoidMapNode(idx=-1, center=((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2),
                                radius=max(rect[2] - rect[0], rect[3] - rect[1]) // 2, bright=True,
                                region_type_list=[LostVoidRegionType.FRIENDLY_TALK.value.value])]

    @staticmethod
    def _set_row(node_list: list[LostVoidMapNode]) -> None:
        """
        按高度分行 高度差 40 以内算同一行 最下面的起点是第 0 行
        起点走过后只剩绿色对勾 也会识别成一个暗的节点
        """
        row = 0
        last_y: int | None = None
        for node in node_list:  # 已经按高度从下往上排好
            if last_y is not None and last_y - node.center[1] > 40:
                row += 1
            node.row = row
            last_y = node.center[1]

    def _match_icon(self, part: MatLike, node: LostVoidMapNode) -> list[str]:
        """
        模板匹配识别节点图标 先按单个大图标匹配 匹配不上再按几个小图标匹配
        :return: 匹配到的模板id
        """
        cx, cy = node.center
        r = node.radius + 12
        x1, y1 = max(0, cx - r), max(0, cy - r)
        crop = part[y1:cy + r, x1:cx + r]

        best_score: float = 0
        best_id: str | None = None
        for template_id, raw, mask in self.template_list:
            for scale in BIG_SCALE_LIST:
                score, _ = self._match(crop, raw, mask, scale)
                if score > best_score:
                    best_score, best_id = score, template_id
        if best_id is not None and best_score >= BIG_MATCH_THRESHOLD:
            return [best_id]

        # 混合节点 每个模板取所有超过阈值的位置 再去掉重叠的
        found: list[tuple[float, str, tuple[int, int, int, int]]] = []
        for template_id, raw, mask in self.template_list:
            for scale in SMALL_SCALE_LIST:
                result, size = self._match_all(crop, raw, mask, scale)
                if result is None:
                    continue
                ys, xs = np.where(result >= SMALL_MATCH_THRESHOLD)
                for x, y in zip(xs, ys, strict=True):
                    found.append((float(result[y, x]), template_id, (int(x), int(y), int(x) + size[0], int(y) + size[1])))
        found.sort(key=lambda t: -t[0])
        kept: list[tuple[float, str, tuple[int, int, int, int]]] = []
        for item in found:
            if all(self._iou(item[2], k[2]) < 0.3 for k in kept):
                kept.append(item)
        kept.sort(key=lambda t: (t[2][1] // 20, t[2][0]))  # 从上往下、从左往右
        id_list: list[str] = []
        for _, template_id, _ in kept:
            if template_id not in id_list:
                id_list.append(template_id)
        return id_list

    @staticmethod
    def _resize(raw: MatLike, mask: MatLike, scale: float) -> tuple[MatLike, MatLike]:
        size = (max(1, round(raw.shape[1] * scale)), max(1, round(raw.shape[0] * scale)))
        return cv2.resize(raw, size, interpolation=cv2.INTER_AREA), cv2.resize(mask, size, interpolation=cv2.INTER_NEAREST)

    def _match_all(self, crop: MatLike, raw: MatLike, mask: MatLike,
                   scale: float) -> tuple[MatLike | None, tuple[int, int]]:
        t_raw, t_mask = self._resize(raw, mask, scale)
        if t_raw.shape[0] > crop.shape[0] or t_raw.shape[1] > crop.shape[1]:
            return None, (0, 0)
        result = cv2.matchTemplate(crop, t_raw, cv2.TM_CCOEFF_NORMED, mask=t_mask)
        return np.nan_to_num(result, nan=0, posinf=0, neginf=0), (t_raw.shape[1], t_raw.shape[0])

    def _match(self, crop: MatLike, raw: MatLike, mask: MatLike, scale: float) -> tuple[float, tuple[int, int]]:
        result, _ = self._match_all(crop, raw, mask, scale)
        if result is None:
            return 0, (0, 0)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        return float(max_val), max_loc

    @staticmethod
    def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        w = min(a[2], b[2]) - max(a[0], b[0])
        h = min(a[3], b[3]) - max(a[1], b[1])
        if w <= 0 or h <= 0:
            return 0
        inter = w * h
        return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)

    @staticmethod
    def _find_edge(hsv: MatLike, node_list: list[LostVoidMapNode], boss_rect: tuple[int, int, int, int] | None) -> None:
        """
        找节点之间的虚线 虚线由一段段灰色短线组成 两段之间空隙约 20 像素 连线可能是弯的
        1. 把距离近、方向一致的短线串成一整条线
        2. 线两头的短线往外延伸 指向哪个节点 就是连到哪个节点
        """
        dash_mask = LostVoidMapReader._get_gray_mask(hsv)
        white_mask = ((hsv[:, :, 1] < 60) & (hsv[:, :, 2] > 215)).astype(np.uint8)
        for node in node_list:
            if node.is_boss:
                continue
            # 节点图标周围的灰色描边不是虚线
            cv2.circle(dash_mask, node.center, node.radius + 6, 0, -1)
            # 右上角的环境角标(骷髅 / 毒雾)是白色圆块 灰色的边缘会混进虚线 把往右上方的线头带偏
            badge = (node.center[0] + BADGE_OFFSET[0], node.center[1] + BADGE_OFFSET[1])
            badge_area = np.zeros_like(white_mask)
            cv2.circle(badge_area, badge, BADGE_RADIUS, 1, -1)
            if np.count_nonzero(white_mask & badge_area) >= BADGE_MIN_WHITE:
                cv2.circle(dash_mask, badge, BADGE_RADIUS + 4, 0, -1)
        if boss_rect is not None:
            cv2.rectangle(dash_mask, (boss_rect[0], 0), (boss_rect[2], boss_rect[3]), 0, -1)

        # 每段短线的中心和方向
        center_list: list[np.ndarray] = []
        direction_list: list[np.ndarray] = []
        n, lab, stats, centroids = cv2.connectedComponentsWithStats(dash_mask)
        for i in range(1, n):
            if not 15 <= stats[i][4] <= 150:
                continue
            ys, xs = np.where(lab == i)
            pts = np.stack([xs, ys], axis=1).astype(np.float32)
            pts -= pts.mean(axis=0)
            _, _, vt = np.linalg.svd(pts, full_matrices=False)
            center_list.append(np.array(centroids[i], dtype=np.float32))
            direction_list.append(vt[0])

        def aligned(v: np.ndarray, d: np.ndarray, max_angle: float) -> bool:
            norm = np.linalg.norm(v)
            if norm == 0:
                return False
            return abs(float(np.dot(v / norm, d))) > np.cos(np.deg2rad(max_angle))

        # 串成线 两段短线离得近 且连线方向和两段短线的方向都一致
        # 每段短线往前、往后各只接一段 选最顺的 两段互相选中才连上
        # 两条线挨得很近时(比如从同一个节点出发 夹角只有十几度)不会串到一起
        dash_cnt = len(center_list)
        pick_list: list[list[int | None]] = [[None, None] for _ in range(dash_cnt)]
        for i in range(dash_cnt):
            best_cost: list[float] = [0, 0]
            for j in range(dash_cnt):
                if j == i:
                    continue
                v = center_list[j] - center_list[i]
                dist = float(np.linalg.norm(v))
                if dist > 50 or not (aligned(v, direction_list[i], 30) and aligned(v, direction_list[j], 30)):
                    continue
                side = 0 if float(np.dot(v, direction_list[i])) > 0 else 1
                cost = dist / abs(float(np.dot(v / dist, direction_list[i])))  # 越近、越顺着短线方向越好
                if pick_list[i][side] is None or cost < best_cost[side]:
                    pick_list[i][side], best_cost[side] = j, cost
        neighbor_list: list[list[int]] = [[] for _ in range(dash_cnt)]
        for i in range(dash_cnt):
            for j in pick_list[i]:
                if j is not None and i in pick_list[j] and j not in neighbor_list[i]:
                    neighbor_list[i].append(j)
                    neighbor_list[j].append(i)

        group_idx: list[int] = [-1] * dash_cnt
        group_list: list[list[int]] = []
        for i in range(dash_cnt):
            if group_idx[i] != -1:
                continue
            group: list[int] = []
            stack = [i]
            group_idx[i] = len(group_list)
            while len(stack) > 0:
                k = stack.pop()
                group.append(k)
                for j in neighbor_list[k]:
                    if group_idx[j] == -1:
                        group_idx[j] = len(group_list)
                        stack.append(j)
            group_list.append(group)

        def find_end_node(dash: int, outward: np.ndarray, exclude: int | None) -> int | None:
            """
            线头的短线往外延伸指向的节点
            """
            c = center_list[dash]
            best: int | None = None
            best_dist: float = 0
            for node in node_list:
                if node.idx == exclude:
                    continue
                if node.is_boss and boss_rect is not None:
                    # THRONE 很大 线头朝上 且在它下方附近就算连上
                    if not (outward[1] < -0.3
                            and boss_rect[0] - 40 <= c[0] <= boss_rect[2] + 40
                            and c[1] <= boss_rect[3] + 45):
                        continue
                    dist = float(c[1] - boss_rect[3])
                else:
                    v = np.array(node.center, dtype=np.float32) - c
                    dist = float(np.linalg.norm(v))
                    if dist > node.radius + 50 or float(np.dot(v / dist, outward)) < np.cos(np.deg2rad(35)):
                        continue
                    # 线头延长线离节点中心太远 是从节点旁边经过的线 不是连到它
                    # 起点走过后只剩对勾 识别的中心和圆圈中心对不上 不判断
                    if node.row > 0 and abs(float(v[0] * outward[1] - v[1] * outward[0])) > max(PASS_BY_DIST, node.radius // 2):
                        continue
                if best is None or dist < best_dist:
                    best, best_dist = node.idx, dist
            return best

        def add_edge(a: int | None, b: int | None) -> None:
            if a is None or b is None or a == b:
                return
            na, nb = node_list[a], node_list[b]
            if na.row == nb.row:  # 地图只往上走 同一行的节点之间没有连线
                return
            lower, upper = (na, nb) if na.center[1] > nb.center[1] else (nb, na)
            if upper.idx not in lower.next_list:
                lower.next_list.append(upper.idx)

        # 每条线两头: (短线, 往外的方向, 指向的节点)
        line_end_list: list[list[tuple[int, np.ndarray, int | None]]] = []
        for group in group_list:
            if len(group) == 1:
                d = direction_list[group[0]]
                end_list = [(group[0], d), (group[0], -d)]
            else:
                # 线头 = 只连着一段的短线 往外的方向 = 从相邻短线指向它
                end_list = []
                for k in group:
                    if len(neighbor_list[k]) == 1:
                        v = center_list[k] - center_list[neighbor_list[k][0]]
                        end_list.append((k, v / np.linalg.norm(v)))
            if len(end_list) != 2:
                continue
            a = find_end_node(end_list[0][0], end_list[0][1], None)
            b = find_end_node(end_list[1][0], end_list[1][1], a)
            line_end_list.append([(end_list[0][0], end_list[0][1], a), (end_list[1][0], end_list[1][1], b)])
            add_edge(a, b)

        # 线从别的节点旁边经过时 被节点周围擦掉的部分断成两截 两截都有一头没连上节点
        # 没连上的两头离得不远、方向相对 就接成一条 连接两截另一头的节点
        joined_set: set[tuple[int, int]] = set()  # (第几条线, 哪一头) 已经接上的
        for i, ends_i in enumerate(line_end_list):
            for ei in range(2):
                ki, oi, node_i = ends_i[ei]
                if node_i is not None:
                    continue
                for j in range(i + 1, len(line_end_list)):
                    for ej in range(2):
                        kj, oj, node_j = line_end_list[j][ej]
                        if node_j is not None:
                            continue
                        v = center_list[kj] - center_list[ki]
                        if (np.linalg.norm(v) <= 120 and float(np.dot(v, oi)) > 0
                                and aligned(v, oi, 25) and float(np.dot(oi, oj)) < -np.cos(np.deg2rad(25))):
                            add_edge(ends_i[1 - ei][2], line_end_list[j][1 - ej][2])
                            joined_set.update([(i, ei), (j, ej)])

        # 后一截整个落在节点周围被擦掉的范围里(比如终点是当前位置 圆圈很大)时 接不上
        # 就顺着线头方向往更远处找 线头延长线正对着的节点
        for i, ends_i in enumerate(line_end_list):
            for ei in range(2):
                ki, oi, node_i = ends_i[ei]
                if node_i is not None or (i, ei) in joined_set or ends_i[1 - ei][2] is None:
                    continue
                c = center_list[ki]
                best: int | None = None
                best_dist: float = 0
                for node in node_list:
                    if node.is_boss:
                        continue
                    v = np.array(node.center, dtype=np.float32) - c
                    dist = float(np.linalg.norm(v))
                    if (dist == 0 or dist > node.radius + 160
                            or float(np.dot(v / dist, oi)) < np.cos(np.deg2rad(35))
                            or abs(float(v[0] * oi[1] - v[1] * oi[0])) > max(PASS_BY_DIST, node.radius // 2)):
                        continue
                    if best is None or dist < best_dist:
                        best, best_dist = node.idx, dist
                add_edge(ends_i[1 - ei][2], best)

        for node in node_list:
            node.next_list.sort()
