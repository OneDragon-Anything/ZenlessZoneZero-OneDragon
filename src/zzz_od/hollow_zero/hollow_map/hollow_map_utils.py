from typing import List, Optional

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cal_utils
from one_dragon.yolo.detect_utils import DetectFrameResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroEntry
from zzz_od.hollow_zero.hollow_map.hollow_zero_map import HollowZeroMap, HollowZeroMapNode


def construct_map_from_yolo_result(
        ctx: ZContext,
        detect_result: DetectFrameResult,
        name_2_entry: dict[str, HollowZeroEntry]
) -> Optional[HollowZeroMap]:
    """
    根据识别结果构造地图
    """
    nodes: List[HollowZeroMapNode] = []
    unknown = name_2_entry['未知']

    for result in detect_result.results:
        entry_name = result.detect_class.class_name[5:]
        if entry_name in name_2_entry:
            entry = name_2_entry[entry_name]
        else:
            entry = unknown

        width = result.x2 - result.x1
        height = result.y2 - result.y1
        if entry.is_base:
            pos = Rect(result.x1, result.y2 - width, result.x2, result.y2)
        else:
            pos = Rect(result.x1, result.y1, result.x2, result.y2 + height // 3)

        # 判断与已有的节点是否重复
        to_merge: Optional[HollowZeroMapNode] = None
        for existed in nodes:
            min_dis = min(pos.height, pos.width, existed.pos.height, existed.pos.width) // 2
            if cal_utils.distance_between(pos.center, existed.pos.center) < min_dis:
                to_merge = existed
                break

        if to_merge is not None:
            if to_merge.entry.is_base and not entry.is_base:  # 旧的是底座 那么将新的类型赋值上去
                to_merge.entry = entry
                to_merge.pos.y1 = pos.y1  # 使用具体类型的坐标
            elif not to_merge.entry.is_base and entry.is_base:  # 旧的是格子类型 那么把底座的范围赋值上去
                to_merge.pos.x1 = pos.x1
                to_merge.pos.x2 = pos.x2
                to_merge.pos.y2 = pos.y2
            else:
                pass
        else:
            node = HollowZeroMapNode(pos, entry,
                                     check_time=detect_result.run_time,
                                     confidence=result.score)
            nodes.append(node)

    for node in nodes:
        if node.entry.is_base:  # 只识别到底座的 赋值为未知
            node.entry = unknown

    if len(nodes) > 0:  # 有识别到节点才认为是有地图
        return construct_map_from_nodes(ctx, nodes, detect_result.run_time)
    else:
        return None


def construct_map_from_nodes(
        ctx: ZContext,
        nodes: List[HollowZeroMapNode],
        check_time: float
) -> HollowZeroMap:
    current_idx: Optional[int] = None
    for i in range(len(nodes)):
        if nodes[i].entry.entry_name == '当前':
            if current_idx is not None:
                # 当出现多个[当前]节点时 说明上一次移动可能失败了 导致内存中有一个错误的节点
                # 此时 只保留最新识别到的结果
                if nodes[current_idx].check_time < nodes[i].check_time:
                    # 将错误的[当前]节点 设置为未知 且0置信度 等待后续被识别结果覆盖
                    nodes[current_idx].entry = ctx.withered_domain.data_service.name_2_entry['未知']
                    nodes[current_idx].confidence = 0
                    current_idx = i
            else:
                current_idx = i

    edges: dict[int, List[int]] = {}

    for i in range(len(nodes)):
        node_1 = nodes[i]
        if (node_1.pos.x1 < 0
                or node_1.pos.y1 < 0
                or node_1.pos.x2 >= ctx.project_config.screen_standard_width
                or node_1.pos.y2 >= ctx.project_config.screen_standard_height
        ):
            continue

        for j in range(len(nodes)):
            node_2 = nodes[j]
            if (node_2.pos.x1 < 0
                    or node_2.pos.y1 < 0
                    or node_2.pos.x2 >= ctx.project_config.screen_standard_width
                    or node_2.pos.y2 >= ctx.project_config.screen_standard_height
            ):
                continue

            if not node_1.entry.can_go or not node_2.entry.can_go:
                continue

            if _at_left(node_1, node_2):  # 1在2左边
                if node_2.entry.entry_name in ['轨道-左']:
                    pass
                elif node_1.entry.entry_name in ['轨道-上', '轨道-下', '轨道-左']:
                    pass
                else:
                    _add_directed_edge(edges, i, j)
            elif _at_right(node_1, node_2):  # 1在2右边
                if node_2.entry.entry_name in ['轨道-右']:
                    pass
                elif node_1.entry.entry_name in ['轨道-上', '轨道-下', '轨道-右']:
                    pass
                else:
                    _add_directed_edge(edges, i, j)
            elif _above(node_1, node_2):  # 1在2上边
                if node_2.entry.entry_name in ['轨道-上']:
                    pass
                elif node_1.entry.entry_name in ['轨道-左', '轨道-右', '轨道-上']:
                    pass
                else:
                    _add_directed_edge(edges, i, j)
            elif _under(node_1, node_2):  # 1在2下边
                if node_2.entry.entry_name in ['轨道-下']:
                    pass
                elif node_1.entry.entry_name in ['轨道-左', '轨道-右', '轨道-下']:
                    pass
                else:
                    _add_directed_edge(edges, i, j)

    return HollowZeroMap(nodes, current_idx, edges, check_time=check_time)


def _at_left(node_1: HollowZeroMapNode, node_2: HollowZeroMapNode) -> bool:
    """
    1在2左边
    :param node_1:
    :param node_2:
    :return:
    """
    min_width = min(node_1.pos.width,  node_2.pos.width) // 4
    return abs(node_1.pos.x2 - node_2.pos.x1) <= min_width and _is_same_row(node_1, node_2)


def _at_right(node_1: HollowZeroMapNode, node_2: HollowZeroMapNode) -> bool:
    """
    1在2右边
    :param node_1:
    :param node_2:
    :return:
    """
    min_width = min(node_1.pos.width,  node_2.pos.width) // 4
    return abs(node_1.pos.x1 - node_2.pos.x2) <= min_width and _is_same_row(node_1, node_2)


def _above(node_1: HollowZeroMapNode, node_2: HollowZeroMapNode) -> bool:
    """
    1在2上边
    :param node_1:
    :param node_2:
    :return:
    """
    min_height = min(node_1.pos.height,  node_2.pos.height) // 4
    return abs(node_1.pos.y2 - node_2.pos.y1) <= min_height and _is_same_col(node_1, node_2)


def _under(node_1: HollowZeroMapNode, node_2: HollowZeroMapNode) -> bool:
    """
    1在2上边
    :param node_1:
    :param node_2:
    :return:
    """
    min_height = min(node_1.pos.height,  node_2.pos.height) // 4
    return abs(node_1.pos.y1 - node_2.pos.y2) <= min_height and _is_same_col(node_1, node_2)


def _is_same_row(node_1: HollowZeroMapNode, node_2: HollowZeroMapNode) -> bool:
    min_height = min(node_1.pos.height,  node_2.pos.height) // 3
    y1_close = abs(node_1.pos.y1 - node_2.pos.y1) <= min_height
    y2_close = abs(node_1.pos.y2 - node_2.pos.y2) <= min_height
    return y1_close or y2_close


def _is_same_col(node_1: HollowZeroMapNode, node_2: HollowZeroMapNode) -> bool:
    min_width = min(node_1.pos.width,  node_2.pos.width) // 3
    x1_close = abs(node_1.pos.x1 - node_2.pos.x1) <= min_width
    x2_close = abs(node_1.pos.x2 - node_2.pos.x2) <= min_width
    return x1_close or x2_close


def _add_edge(edges: dict[int, List[int]], x: int, y: int) -> None:
    _add_directed_edge(edges, x, y)
    _add_directed_edge(edges, y, x)


def _add_directed_edge(edges: dict[int, List[int]], x: int, y: int) -> None:
    if x not in edges:
        edges[x] = [y]
    else:
        edges[x].append(y)


def is_same_map(map_1: HollowZeroMap, map_2: HollowZeroMap) -> bool:
    """
    判断两个地图是否同一个地图
    通常情况下，两个地图的差异是在一步移动之后产生的，因此大部分节点都应该一致
    当相同节点数量 >= 1/2 地图节点时，认为地图一致
    :param map_1: 地图1
    :param map_2: 地图2
    :return:
    """
    node_cnt_1 = len(map_1.nodes)
    node_cnt_2 = len(map_2.nodes)

    if node_cnt_1 == 0 and node_cnt_2 == 0:
        return True
    elif node_cnt_1 == 0 or node_cnt_2 == 0:
        return False

    same_node_cnt = 0
    for node_1 in map_1.nodes:
        for node_2 in map_2.nodes:
            if is_same_node(node_1, node_2):
                same_node_cnt += 1
                break

    # 极端情况下 是在3个格子的情况下移动 剩下2个格子
    # 如果移动后有在内存将格子更新为当前 则本次识别的2个格子的应该跟之前的一样 因此至少有50%格子一致
    # 必须要两个地图都有50%格子在另一张地图上 因为进入盲盒区域后 可能区域里只有少量格子 但跟外层的地图刚好重合
    return same_node_cnt >= node_cnt_1 * 0.5 and same_node_cnt >= node_cnt_2 * 0.5


def merge_map(ctx: ZContext, map_list: List[HollowZeroMap]):
    """
    将多个地图合并成一个
    """
    nodes: List[HollowZeroMapNode] = []
    max_check_time: Optional[float] = None

    # 每个地图的节点取出来后去重合并
    for m in map_list:
        for node in m.nodes:
            to_merge: Optional[HollowZeroMapNode] = None
            for existed in nodes:
                if is_same_node_pos(node, existed):
                    to_merge = existed
                    break

            if to_merge is not None:
                if to_merge.entry.is_base:  # 旧的是底座 那么将新的类型赋值上去
                    to_merge.entry = node.entry
                elif node.entry.is_base:  # 旧的是格子类型 新的是底座 将底座范围赋值上去
                    to_merge.pos = node.pos
                elif to_merge.entry.entry_name == '未知' and node.entry.entry_name != '未知':  # 新旧都是格子类型 旧的是未知 将新的类型赋值上去
                    to_merge.entry = node.entry
                elif to_merge.entry.entry_name != '未知' and node.entry.entry_name == '未知':  # 新旧都是格子类型 新的是未知 保持不变
                    pass
                elif to_merge.confidence > 0.95 and node.confidence > 0.95:
                    if to_merge.check_time < node.check_time:  # 两者置信度都很高 保留时间最新的结果
                        to_merge.entry = node.entry
                elif to_merge.confidence < node.confidence:  # 新旧都是格子类型 旧的识别置信度低 将新的类型赋值上去
                    to_merge.entry = node.entry
                elif to_merge.check_time < node.check_time:  # 新旧都是格子类型 新的识别时间更晚 将新的类型赋值上去
                    to_merge.entry = node.entry
            else:
                nodes.append(node)

        if max_check_time is None or m.check_time > max_check_time:
            max_check_time = m.check_time

    return construct_map_from_nodes(ctx, nodes, max_check_time)


def is_same_node_pos(x: HollowZeroMapNode, y: HollowZeroMapNode) -> bool:
    """
    判断两个节点的坐标是否一致
    """
    if x is None or y is None:
        return False
    min_dis = min(x.pos.height, x.pos.width, y.pos.height, y.pos.width) // 2
    return cal_utils.distance_between(x.pos.center, y.pos.center) < min_dis


def is_same_node(x: HollowZeroMapNode, y: HollowZeroMapNode) -> bool:
    """
    判断两个节点是否同一个节点
    """
    if x is None or y is None:
        return False
    return x.entry.entry_name == y.entry.entry_name and is_same_node_pos(x, y)


def get_node_index(current_map: HollowZeroMap, node: HollowZeroMapNode) -> int:
    """
    获取某个节点 在地图上的下标
    @param current_map: 地图
    @param node: 节点
    @return: 下标
    """
    for i in range(len(current_map.nodes)):
        if is_same_node(current_map.nodes[i], node):
            return i
