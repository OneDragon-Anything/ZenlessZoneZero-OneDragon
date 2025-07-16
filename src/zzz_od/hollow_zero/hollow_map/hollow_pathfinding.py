from cv2.typing import MatLike
from typing import Optional, List

from one_dragon.base.geometry.point import Point
from one_dragon.utils import cal_utils
from zzz_od.hollow_zero.hollow_map.hollow_map_utils import is_same_node
from zzz_od.hollow_zero.hollow_map.hollow_zero_map import HollowZeroMapNode, HollowZeroMap


def search_map(current_map: HollowZeroMap, avoid_entry_list: set[str], visited_nodes: List[HollowZeroMapNode]) -> None:
    """
    对当前地图进行搜索 获取前往每个节点的路径
    :param current_map: 识别到的地图信息
    :param: avoid_entry_list: 避免途经点
    :param: visited_nodes: 已经去过的节点 这些在后续再经过时不需要步数
    :return:
    """
    if current_map is None:
        return

    current_map.init_path_related()
    if not current_map.is_valid_map:
        return

    # 先避开部分节点进行搜索 例如战斗的节点
    result_1 = _bfs_search_map(current_map, [current_map.current_idx], avoid_entry_list, visited_nodes)

    # 可能存在部分节点 一定要经过[避免途经点]才能到达
    # 因此 在上述搜索结果上 继续搜索剩余节点的路径
    start_idx_list = []
    for idx in range(len(current_map.nodes)):
        node = current_map.nodes[idx]
        if node.path_step_cnt >= 0:
            start_idx_list.append(idx)

    result_2 = _bfs_search_map(current_map, start_idx_list, None, visited_nodes)

    return result_2


def _bfs_search_map(
        current_map: HollowZeroMap,
        start_idx_list: List[int],
        avoid_entry_list: Optional[set[str]] = None,
        visited_nodes: List[HollowZeroMapNode] = None
) -> None:
    """
    使用宽度搜索 找到达地图上每一个节点的最短路径
    :param current_map: 识别到的地图信息
    :param start_idx_list: 起始的节点下标列表：在第1次搜索时，只有当前节点；第2次搜索时，会包含第1次搜索的路径结果
    :param avoid_entry_list: 避免途经点
    :param: visited_nodes: 已经去过的节点 这些在后续再经过时不需要步数
    :return:
    """
    bfs_queue: List[int] = []  # 当前层的节点下标
    searched: set[int] = set()  # 已经搜索过的节点下标
    for idx in start_idx_list:
        bfs_queue.append(idx)
        searched.add(idx)

    # 宽度搜索 每层先搜索不需要移动步数的；再搜索需要移动步数的
    while len(bfs_queue) > 0:
        next_bfs_queue: List[int] = []  # 下一层
        bfs_idx = 0  # 遍历当前层的节点
        while bfs_idx < len(bfs_queue):  # 注意当前层bfs_queue会不断加入不需要步数的节点 因此用这个while
            current_idx = bfs_queue[bfs_idx]
            current_node = current_map.nodes[current_idx]
            searched.add(current_idx)
            bfs_idx += 1  # 标记这个节点已经处理 下一次循环需要处理下一个节点的

            if current_idx not in current_map.edges:  # 这个节点没有边 即没有可以移动的节点
                continue

            for next_idx in current_map.edges[current_idx]:  # 遍历这个节点的边 找到可以移动的节点
                if next_idx in searched:  # 这个可以移动的节点 已经被搜索过
                    continue

                next_node = current_map.nodes[next_idx]
                next_entry = next_node.entry

                if not next_entry.can_go:  # 无法移动
                    continue
                if avoid_entry_list is not None and next_entry.entry_name in avoid_entry_list:  # 避免途经点
                    continue

                need_step = next_entry.need_step  # 前往这个节点是否需要步数

                # 已经去过 且还是存在的节点 还是需要先路过
                # 否则 依赖直接点击终点 游戏内的自动寻路有几率选择另一条更短但无法通行的路 例如是危机节点
                # 这时候就会卡死
                # 参考 https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/issues/382
                # 已经去过的节点 在 hollow_runner 中判断，不再触发对应的事件指令
                # if (next_entry.entry_name == '邦布商人'  # 当前只有商人不会消失
                #         and visited_nodes is not None
                #         and had_been_visited(next_node, visited_nodes)):  # 已经去过的节点 不需要步数
                #     need_step = 0

                # 根据节点类型 计算前往下一个节点的步数
                next_step_cnt = current_node.path_step_cnt + need_step
                # 判断这条路径上 第一个需要步数的节点是哪个 即需要点击的节点
                if next_step_cnt <= 1 and next_entry.need_step > 0:
                    first_need_step_node = next_node
                else:
                    first_need_step_node = current_node.path_first_need_step_node

                # 设置下一个节点的寻路信息
                next_node.path_first_node = next_node if current_node.path_first_node is None else current_node.path_first_node
                next_node.path_first_need_step_node = first_need_step_node
                next_node.path_last_node = current_node
                next_node.path_step_cnt = next_step_cnt
                next_node.path_node_cnt = current_node.path_node_cnt + 1
                # 构建前往下一个节点的路径

                if next_step_cnt == current_node.path_step_cnt:  # 相同步数 就加入当前层 继续搜索
                    if next_idx in bfs_queue:  # 已经在当前队列
                        pass
                    elif next_idx in next_bfs_queue:  # 在下一层的队列 移动
                        next_bfs_queue.remove(next_idx)
                        bfs_queue.append(next_idx)
                    else:  # 都不在 放入当前的队列
                        bfs_queue.append(next_idx)
                else:  # 步数增加的 就加入下一层 等待后续搜索
                    if next_idx not in next_bfs_queue:
                        next_bfs_queue.append(next_idx)

        bfs_queue = next_bfs_queue


def get_route_in_1_step(current_map: HollowZeroMap,
                        visited_nodes: List[HollowZeroMapNode],
                        target_entry_list: Optional[List[str]] = None) -> Optional[HollowZeroMapNode]:
    """
    获取1步能到的节点的路径
    :param current_map: 当前的地图
    :param visited_nodes: 已经去过的节点 就不会再去了
    :param target_entry_list: 传入时 只考虑前往这些限定格子类型
    :return:
    """
    target: Optional[HollowZeroMapNode] = None
    for node in current_map.nodes:
        if node.path_step_cnt != 1:  # 筛选只需要1步前往的路径
            continue

        entry = node.entry  # 目标节点的类型
        if target_entry_list is not None and entry.entry_name not in target_entry_list:  # 不符合目标类型
            continue

        if had_been_visited(node, visited_nodes):  # 曾经尝试去过了
            continue

        if target is None or target.path_node_cnt > node.path_node_cnt:  # 有多个候选时 优先选择经过格子数量最少的
            target = node

    return target


def get_route_by_entry(current_map: HollowZeroMap,
                       entry_name: str,
                       visited_nodes: List[HollowZeroMapNode]) -> Optional[HollowZeroMapNode]:
    """
    找一条最短的 能到达目标类型格子的 路径
    :param current_map: 当前的地图
    :param entry_name: 需要前往的格子类型
    :param visited_nodes: 已经尝试去过的格子
    :return:
    """
    target: Optional[HollowZeroMapNode] = None
    for node in current_map.nodes:
        if node.path_step_cnt == -1:  # 不可前往的
            continue
        entry = node.entry
        if entry is None or entry.entry_name != entry_name:
            continue

        if had_been_visited(node, visited_nodes):
            continue

        # 有多个候选时 优先选择步数最少的
        # 步数一致时 优选选择经过格子数量最少的
        if (target is None
                or target.path_step_cnt > node.path_step_cnt
                or (target.path_step_cnt == node.path_step_cnt and target.path_node_cnt > node.path_node_cnt)):
            target = node

    return target


def get_route_by_direction(current_map: HollowZeroMap, direction: str) -> Optional[HollowZeroMapNode]:
    """
    找一条最远的 符合目标方向的 路径
    主要用于兜底情况 按副本类型找一个方向前进
    :param current_map: 当前地图
    :param direction: 方向
    :return:
    """
    target: Optional[HollowZeroMapNode] = None
    for node in current_map.nodes:
        if node.path_step_cnt == -1:  # 不可前往的
            continue
        if node.entry.entry_name in ['当前', '空白已通行', '空白未通行']:
            continue

        # 根据各个方向 找到最远的格子
        if target is None:
            target = node
        elif direction == 'w' and target.pos.y1 > node.pos.y1:
            target = node
        elif direction == 's' and target.pos.y2 < node.pos.y2:
            target = node
        elif direction == 'a' and target.pos.x1 > node.pos.x1:
            target = node
        elif direction == 'd' and target.pos.x2 < node.pos.x2:
            target = node

    return target


def had_been_visited(current: HollowZeroMapNode, visited_nodes: List[HollowZeroMapNode]) -> bool:
    """
    判断节点是否已经尝试前往过了
    部分节点允许多次尝试前往 (例如 业绩考察点) 避免各种奇怪的情况错过
    """
    for visited in visited_nodes:
        if visited.gt_max_visited_times and is_same_node(current, visited):
            return True
    return False


def draw_map(screen: MatLike, current_map: HollowZeroMap,
             next_node: Optional[HollowZeroMapNode] = None, to_click: Optional[Point] = None) -> MatLike:
    """
    在图上画出地图
    :param screen:
    :param current_map:
    :return:
    """
    import cv2
    to_draw = screen.copy()

    for node in current_map.nodes:
        cv2.rectangle(to_draw, (node.pos.x1, node.pos.y1), (node.pos.x2, node.pos.y2), (255, 0, 0), 2)

    for i, j_list in current_map.edges.items():
        for j in j_list:
            if j > i:
                node_1 = current_map.nodes[i]
                node_2 = current_map.nodes[j]
                cv2.line(to_draw, node_1.pos.center.tuple(), node_2.pos.center.tuple(),
                         (0, 255, 0), 2)

    for node in current_map.nodes:
        # 在对应坐标是显示idx
        msg = f'{node.entry.entry_id} : {node.path_step_cnt}'
        cv2.putText(to_draw, msg, (node.pos.left_top + Point(0, 20)).tuple(), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 0, 255), 2)

    if next_node is not None:
        cv2.circle(to_draw, next_node.pos.center.tuple(), 20, (0, 0, 255), 2)
    if to_click is not None:
        cv2.circle(to_draw,to_click.tuple(), 10, (0, 0, 255), 2)

    return to_draw
