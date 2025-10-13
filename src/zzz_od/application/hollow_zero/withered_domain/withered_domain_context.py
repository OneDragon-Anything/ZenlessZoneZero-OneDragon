from __future__ import annotations

import random
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING, List, Optional

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.application import application_const
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.withered_domain import withered_domain_const
from zzz_od.application.hollow_zero.withered_domain.withered_domain_config import (
    WitheredDomainConfig,
)
from zzz_od.game_data.agent import Agent, AgentEnum
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroEntry
from zzz_od.hollow_zero.hollow_level_info import HollowLevelInfo
from zzz_od.hollow_zero.hollow_map import hollow_map_utils, hollow_pathfinding
from zzz_od.hollow_zero.hollow_map.hollow_zero_map import (
    HollowZeroMap,
    HollowZeroMapNode,
)
from zzz_od.hollow_zero.hollow_map.hollow_zero_map_service import HollowZeroMapService
from zzz_od.hollow_zero.hollow_zero_challenge_config import (
    HollowZeroChallengeConfig,
    HollowZeroChallengePathFinding,
)
from zzz_od.hollow_zero.hollow_zero_data_service import HallowZeroDataService

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext

_withered_domain_context_executor = ThreadPoolExecutor(thread_name_prefix='withered_domain_context_executor', max_workers=16)


class WitheredDomainContext:

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx

        self.challenge_config: Optional[HollowZeroChallengeConfig] = None

        self.agent_list: Optional[List[Agent]] = None

        self.data_service: HallowZeroDataService = HallowZeroDataService()
        self.level_info: HollowLevelInfo = HollowLevelInfo()

        self.map_service: HollowZeroMapService = HollowZeroMapService(ctx)

        self.map_results: List[HollowZeroMap] = []  # 识别的地图结果
        self._visited_nodes: List[HollowZeroMapNode] = []  # 已经去过的点
        self.last_target_node: Optional[HollowZeroMapNode] = None  # 上一次想前往的节点
        self._last_current_node: Optional[HollowZeroMapNode] = None  # 上一次当前所在的点
        self.speed_up_clicked: bool = False  # 是否已经点击加速
        self.invalid_map_times: int = 0  # 识别不到正确地图的次数

    def init_before_run(self) -> None:
        """
        应用开始前的初始化
        """
        self.data_service.reload()
        config: Optional[WitheredDomainConfig] = self.ctx.run_context.get_config(
            app_id=withered_domain_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        if config is None or config.challenge_config is None:
            self.challenge_config = HollowZeroChallengeConfig('', is_mock=True)
        else:
            self.challenge_config = HollowZeroChallengeConfig(config.challenge_config)

    def _match_agent_in(self, img: MatLike, possible_agents: Optional[List[Agent]] = None) -> Optional[Agent]:
        """
        在候选列表中匹配角色
        :return:
        """
        prefix = 'avatar_'
        if possible_agents is None:
            possible_agents = [agent_enum.value for agent_enum in AgentEnum]
        for agent in possible_agents:
            if agent is None:
                continue
            for template_id in agent.template_id_list:
                mrl = self.ctx.tm.match_template(img, 'hollow', prefix + template_id, threshold=0.8)
                if mrl.max is not None:
                    return agent

        return None

    def get_next_to_move(self, current_map: HollowZeroMap) -> Optional[HollowZeroMapNode]:
        """
        获取下一步的需要点击的节点
        :param current_map:
        :return:
        """
        if not current_map.is_valid_map:  # 有可能是[当前]节点被鼠标或者[进入商店]遮挡住了
            self.invalid_map_times += 1
            if self.invalid_map_times >= 5:  # 移动后 由于鼠标的遮挡 容易识别不到 因此多次识别不到才使用兜底逻辑
                # 没有 [当前] 节点 随机走向一个空白节点
                for node in current_map.nodes:
                    if node.entry.entry_name == '空白已通行':
                        node.path_last_node = node
                        node.path_first_node = node
                        node.path_first_need_step_node = node
                        node.path_step_cnt = 999
                        node.path_node_cnt = 1
                        log.info(f"优先级 [空白已通行]")
                        self.invalid_map_times = 0
                        return node
            # 没有识别到[当前]节点的话 就不需要寻路移动了
            return None
        else:
            self.invalid_map_times = 0

        hollow_pathfinding.search_map(current_map, set(self._get_avoid()), self._visited_nodes)

        # 优先考虑 一步可达时前往
        target = hollow_pathfinding.get_route_in_1_step(current_map, self._visited_nodes,
                                                       target_entry_list=self._get_go_in_1_step())
        target = self.try_target_node(current_map, target)
        if target is not None:
            log.info(f"优先级 [一步]")
            return target

        go_priority_list = self._get_waypoint()

        for to_go in go_priority_list:
            target = hollow_pathfinding.get_route_by_entry(current_map, to_go, self._visited_nodes)
            target = self.try_target_node(current_map, target)
            if target is None:
                continue
            log.info(f"优先级 [途经]")
            return target

        # 是一定能走到的出口
        must_go_list = [
            '守门人',
            '传送点',
            '不宜久留'
        ]

        for to_go in must_go_list:
            target = hollow_pathfinding.get_route_by_entry(current_map, to_go, self._visited_nodes)
            target = self.try_target_node(current_map, target)
            if target is not None:
                log.info(f"优先级 [终点]")
                return target

            # 如果之前走过，但走不到 说明可能中间有格子识别错了 这种情况就一格一格地走
            target = hollow_pathfinding.get_route_by_entry(current_map, to_go, [])
            target = self.try_target_node(current_map, target)
            if target is not None:
                log.info(f"优先级 [终点]")
                target.path_go_way = 0
                return target

        # 随便找个一步可达的格子
        target = hollow_pathfinding.get_route_in_1_step(current_map, self._visited_nodes,
                                                        target_entry_list=self.data_service.get_no_battle_list())
        target = self.try_target_node(current_map, target)
        if target is not None:
            log.info(f"优先级 [随机一步]")
            return target

        # 没有匹配到特殊点的时候 按副本类型走特定方向
        direction = 'w'
        if self.level_info.level >= 2 and self.level_info.phase == 1:
            direction = 'w'
        elif self.level_info.mission_type_name == '施工废墟':
            direction = 'd'
        elif self.level_info.mission_type_name == '巨厦遗骸':
            direction = 'd'

        target = hollow_pathfinding.get_route_by_direction(current_map, direction)
        target = self.try_target_node(current_map, target)
        if target is not None:
            log.info(f"优先级 [方向]")
            return target

        # 兜底 走一步能到的
        target = hollow_pathfinding.get_route_in_1_step(current_map, self._visited_nodes)
        target = self.try_target_node(current_map, target)
        if target is not None:
            log.info(f"优先级 [兜底]")
            return target

        # 最终兜底 在[当前]节点四周随便移动一格
        if current_map.current_idx is not None:
            current_node = current_map.nodes[current_map.current_idx]
            if hollow_map_utils.is_same_node(self._last_current_node, current_node):
                arr = ['w', 's', 'a', 'd']
                arr.remove(direction)
                direction = arr[random.randint(0, len(arr) - 1)]
            self._last_current_node = current_node

            # 伪造一个节点前往
            if direction == 'w':
                to_go = current_node.pos.center - Point(0, current_node.pos.height)
            elif direction == 's':
                to_go = current_node.pos.center + Point(0, current_node.pos.height)
            elif direction == 'a':
                to_go = current_node.pos.center - Point(current_node.pos.width, 0)
            else:
                to_go = current_node.pos.center + Point(current_node.pos.width, 0)

            fake_node = HollowZeroMapNode(
                pos=Rect(to_go.x, to_go.y, to_go.x, to_go.y),
                entry=HollowZeroEntry('0000-fake'),
            )
            fake_node.path_first_node = fake_node
            fake_node.path_first_need_step_node = fake_node
            fake_node.path_step_cnt = 999
            fake_node.path_node_cnt = 1
            log.info(f"优先级 [随机相邻]")
            return fake_node

    def try_target_node(self, current_map: HollowZeroMap, target: HollowZeroMapNode) -> Optional[HollowZeroMapNode]:
        """
        找到目标点后 针对一些可能识别错误的场景进行修正
        判断是否需要前往
        @param current_map: 当前地图
        @param target: 目标点
        @return: 需要前往的目标点
        """
        if target is None:
            return None
        # 两次想要前往同一个节点
        if (self.last_target_node is not None
                and hollow_map_utils.is_same_node(self.last_target_node, target)):
            # 第一步需要点击的节点都一样 可能是被卡着过不去了
            last_node_to_move = self.last_target_node.next_node_to_move
            curr_node_to_move = target.next_node_to_move
            if hollow_map_utils.is_same_node(last_node_to_move, curr_node_to_move):
                # 可能识别错了 导致点击的第一个位置不对 这里改为强行点击相邻节点
                target.path_go_way = 0
                if (
                        target.entry.entry_name in ['零号银行', '业绩考察点']  # 目标前往的点
                        and curr_node_to_move.entry.entry_name in ['门扉禁闭-财富', '门扉禁闭-善战', '门扉禁闭-侵蚀']  # 下一步前往的格子是门 门的类型有可能识别错
                ):
                    # 代表上一次点了之后 这次依然要点同样的位置 也就是无法通行 标记为已经去过了
                    self.update_context_after_move(current_map, target, update_current=False)
                    return None

        self.last_target_node = target
        return target

    def update_context_after_move(self, current_map: HollowZeroMap, node: HollowZeroMapNode,
                                  update_current: bool = True) -> None:
        """
        点击后 更新
        :param current_map: 当前地图
        :param node: 前往的节点
        :param update_current: 是否更新当前地图
        :return:
        """
        visited = None
        for v in self._visited_nodes:
            if hollow_map_utils.is_same_node(node, v):
                visited = v
                break

        if visited is not None:
            visited.visited_times += 1
        else:
            # 由于node是从某个map中来的 移动之后 会被更新为[当前]
            # 因此需要额外创建一个节点用于记录
            visited = HollowZeroMapNode(node.pos, node.entry)
            visited.visited_times = 1
            self._visited_nodes.append(visited)

        # 部分格子后摇时间长 第一次点击时候未必能进行移动 因此这个更新可能不准确
        if update_current:
            self.update_map_current_node(current_map, node)

        # node的类型已经被改了 只能用visited来判断
        if visited.entry.is_tp:
            self._visited_nodes.clear()

            if visited.entry.entry_name == '传送点':
                if self.level_info is not None:
                    self.level_info.to_next_phase()
                self.map_service.clear_map_result()

    def update_map_current_node(self, current_map: HollowZeroMap, node: HollowZeroMapNode) -> None:
        """
        更新地图的当前节点
        :param current_map: 地图
        :param node: 当前点击前往的节点
        :return:
        """
        next_current_node: HollowZeroMapNode = node
        if node.entry.entry_name == '门扉禁闭-善战':  # 这个节点不能直接前往 会停在前一个节点
            next_current_node = node.path_last_node
        elif node.entry.entry_name in ['轨道-上', '轨道-下', '轨道-左', '轨道-右']:  # 轨道的移动 会到下一个节点
            idx = hollow_map_utils.get_node_index(current_map, node)  # 找到节点下标
            if idx is not None and idx in current_map.edges and len(current_map.edges[idx]) > 0:
                # 按节点下标 找到边对应的下一个节点
                next_current_node = current_map.nodes[current_map.edges[idx][0]]

        next_current_node_idx: int = -1
        for i in range(len(current_map.nodes)):
            if hollow_map_utils.is_same_node(current_map.nodes[i], next_current_node):
                next_current_node_idx = i
                break

        if next_current_node_idx == -1:
            return

        # 将之前的[当前]节点改为空白
        if current_map.current_idx is not None:
            # 只有识别到[当前]节点的时候才需要更改
            current_node = current_map.nodes[current_map.current_idx]
            current_node.entry = self.data_service.name_2_entry['空白已通行']
            # 设置一个较低的置信度 就算移动失败 也可以使用下一次的识别结果来更新
            current_node.confidence = 0.6

        # 将移动到的节点改为[当前]节点
        next_current_node.entry = self.data_service.name_2_entry['当前']
        next_current_node.confidence = 0.6
        current_map.current_idx = next_current_node_idx

    def update_to_next_level(self) -> None:
        """
        前往下一层了 更新信息
        """
        self._visited_nodes.clear()
        if self.level_info is not None:
            self.level_info.to_next_level()
        self.last_target_node = None
        self.map_service.clear_map_result()

    def init_level_info(self, mission_type_name: str, mission_name: str,
                        level: int = 1, phase: int = 1) -> None:
        """
        重新开始空洞时 初始化空洞的信息
        """
        self.level_info = HollowLevelInfo(mission_type_name, mission_name, level, phase)

    def update_agent_list_after_support(self, new_agent: Agent, pos: int) -> None:
        """
        呼叫支援后 更新角色列表
        :param new_agent: 加入的代理人
        :param pos: 位置 1~3
        :return:
        """
        if self.agent_list is None:
            return
        idx = pos - 1
        if idx < 0 or idx >= len(self.agent_list):
            return
        if self.agent_list[idx] is None:  # 接替的位置为空 直接赋值
            self.agent_list[idx] = new_agent
        else:
            none_idx: int = -1
            for i in range(len(self.agent_list)):
                if self.agent_list[i] is None:
                    none_idx = i
                    break

            if none_idx == -1:  # 原来就是满人 直接替换赋值
                self.agent_list[idx] = new_agent
            else:  # 原来不是满人 新加入的按位置赋值 原位置的角色移动到空位
                self.agent_list[none_idx] = self.agent_list[idx]
                self.agent_list[idx] = new_agent

    def had_been_entry(self, entry_name: str) -> bool:
        """
        是否曾经到达过某种类型的格子
        :param entry_name:
        :return:
        """
        for visited in self._visited_nodes:
            if visited.entry.entry_name == entry_name and visited.gt_max_visited_times:
                return True
        return False

    def _get_go_in_1_step(self) -> List[str]:
        """
        一步可达时前往
        :return:
        """
        if self.challenge_config.path_finding == HollowZeroChallengePathFinding.DEFAULT.value.value:
            return self.data_service.get_default_go_in_1_step_entry_list()
        elif self.challenge_config.path_finding == HollowZeroChallengePathFinding.ONLY_BOSS.value.value:
            return self.data_service.get_only_boss_go_in_1_step_entry_list()
        elif self.challenge_config.path_finding == HollowZeroChallengePathFinding.CUSTOM.value.value:
            return self.challenge_config.go_in_1_step
        else:
            return []

    def _get_waypoint(self) -> List[str]:
        """
        途经点
        :return:
        """
        if self.challenge_config.path_finding == HollowZeroChallengePathFinding.DEFAULT.value.value:
            return self.data_service.get_default_waypoint_entry_list()
        elif self.challenge_config.path_finding == HollowZeroChallengePathFinding.ONLY_BOSS.value.value:
            return self.data_service.get_only_boss_waypoint_entry_list()
        elif self.challenge_config.path_finding == HollowZeroChallengePathFinding.CUSTOM.value.value:
            return self.challenge_config.waypoint
        else:
            return []

    def _get_avoid(self) -> List[str]:
        """
        避免途经点
        :return:
        """
        if self.challenge_config.path_finding == HollowZeroChallengePathFinding.DEFAULT.value.value:
            return self.data_service.get_default_avoid_entry_list()
        elif self.challenge_config.path_finding == HollowZeroChallengePathFinding.ONLY_BOSS.value.value:
            return self.data_service.get_default_avoid_entry_list()
        elif self.challenge_config.path_finding == HollowZeroChallengePathFinding.CUSTOM.value.value:
            return self.challenge_config.avoid
        else:
            return []

    def check_info_before_move(self, screen: MatLike, current_map: HollowZeroMap):
        self.check_agent_list(screen, skip_if_checked=True)  # 平时可以不识别
        self._check_mission_level(screen, current_map)

    def _check_mission_level(self, screen: MatLike, current_map: HollowZeroMap) -> None:
        """
        如果之前没有初始化好副本信息 靠当前画面识别 断点继续时有用
        :param screen:
        :param current_map: 当前地图信息
        :return:
        """
        level_info = self.level_info
        if level_info.level == -1:  # 没有楼层信息 先识别
            area = self.ctx.screen_loader.get_area('零号空洞-事件', '当前层数')
            part = cv2_utils.crop_image_only(screen, area.rect)
            ocr_result = self.ctx.ocr.run_ocr_single_line(part)
            digit = str_utils.get_positive_digits(ocr_result, err=-1)
            level_info.level = digit

        if level_info.phase == -1:  # 没有阶段信息
            if level_info.level in [2, 3]:  # 2 3层 可以先尝试识别
                if current_map.contains_entry('传送点'):
                    level_info.phase = 1
                else:
                    level_info.phase = 2
            else:  # 1层固定只有1阶段
                level_info.phase = 1

        # 旧都列车
        if level_info.mission_type_name is None:
            if level_info.level in [2, 3] and level_info.phase == 1:
                if current_map.contains_entry('假面研究者'):
                    level_info.mission_type_name = '旧都列车'

        # 施工废墟
        if level_info.mission_type_name is None:
            if current_map.contains_entry('投机客') or current_map.contains_entry('门扉禁闭-财富'):
                level_info.mission_type_name = '施工废墟'

    def check_agent_list(self, screen: MatLike, skip_if_checked: bool = False) -> Optional[List[Agent]]:
        """
        识别空洞画面里的角色列表
        """
        if skip_if_checked and self.agent_list is not None:
            return self.agent_list

        check: bool = False
        if self.agent_list is not None:
            check = self._check_agent_list_in_parallel(screen, self.agent_list)
        if not check:  # 靠原来的识别不到 尝试全部识别
            self._check_agent_list_in_parallel(screen, None)

        return self.agent_list

    def _check_agent_list_in_parallel(self, screen: MatLike, possible_agents: Optional[List[Agent]] = None) -> bool:
        check_agent_area = [
            self.ctx.screen_loader.get_area('零号空洞-事件', ('角色-%d' % i))
            for i in range(1, 4)
        ]
        area_img = [
            cv2_utils.crop_image_only(screen, i.rect)
            for i in check_agent_area
        ]

        result_agent_list: List[Optional[Agent]] = []
        future_list: List[Future] = []

        for img in area_img:
            future_list.append(_withered_domain_context_executor.submit(self._match_agent_in, img, possible_agents))

        any_not_none: bool = False
        for future in future_list:
            try:
                result = future.result()
                result_agent_list.append(result)
                if result is not None:
                    any_not_none = True
            except Exception:
                log.error('识别角色头像失败', exc_info=True)
                result_agent_list.append(None)

        if any_not_none:  # 由于有空格存在 任意一个识别到就算ok
            self.agent_list = result_agent_list
            return True
        else:
            return False

    def init_before_hollow_start(self, mission_type_name: str, mission_name: str,
                                 level: int = 1, phase: int = 1) -> None:
        """
        进入空洞时 进行对应的初始化
        :return:
        """
        self.map_service.init_event_yolo()
        self.init_level_info(mission_type_name, mission_name, level, phase)
        self.agent_list = None

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        @return:
        """
        _withered_domain_context_executor.shutdown(wait=False, cancel_futures=True)
