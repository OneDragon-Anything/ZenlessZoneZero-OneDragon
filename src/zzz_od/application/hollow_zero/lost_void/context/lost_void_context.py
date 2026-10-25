import os
import re
import time

from cv2.typing import MatLike

from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.base.operation.application import application_const
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.screen_utils import FindAreaResultEnum
from one_dragon.utils import cv2_utils, os_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon.yolo.detect_utils import DetectFrameResult
from zzz_od.application.hollow_zero.lost_void import lost_void_const
from zzz_od.application.hollow_zero.lost_void.context.lost_void_artifact import (
    LostVoidArtifact,
)
from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import (
    LostVoidDetector,
)
from zzz_od.application.hollow_zero.lost_void.context.lost_void_investigation_strategy import (
    LostVoidInvestigationStrategy,
)
from zzz_od.application.hollow_zero.lost_void.context.lost_void_map_reader import (
    LostVoidMap,
    LostVoidMapNode,
    LostVoidMapReader,
)
from zzz_od.application.hollow_zero.lost_void.context.lost_void_run_memory import (
    LostVoidRunMemory,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidChallengeConfig,
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_config import LostVoidConfig
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_artifact_pos import (
    LostVoidArtifactPos,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import (
    MoveTargetWrapper,
)
from zzz_od.auto_battle.auto_battle_dodge_context import YoloStateEventEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import CommonAgentStateEnum


class LostVoidContext:

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx

        self.detector: LostVoidDetector | None = None
        # 寻路转向比例 = 鼠标移动量 ÷ 目标在画面上横移的像素 原地转向后按实际转动平滑更新 跨移动保留
        # 只在挑战配置开启 smart_escape 时使用 初始值来自寻路采样 单次转向实测中位数约 0.6
        self.move_turn_ratio: float = 0.6
        self.challenge_config: LostVoidChallengeConfig | None = None

        self.all_artifact_list: list[LostVoidArtifact] = []  # 武备 + 鸣徽
        self.gear_by_name: dict[str, LostVoidArtifact] = {}  # key=名称 value=武备
        self.cate_2_artifact: dict[str, list[LostVoidArtifact]] = {}  # key=分类 value=藏品

        self.investigation_strategy_list: list[LostVoidInvestigationStrategy] = []  # 调查战略

        self.predefined_team_idx: int = -1  # 本次挑战所使用的预备编队
        self.priority_updated: bool = False  # 动态优先级是否已经更新
        self.dynamic_priority_list: list[str] = []  # 动态获取的优先级列表
        self.dynamic_abandon_list: list[str] = []  # 动态放弃组
        self.had_interacted_ophelia_on_current_level: bool = False  # 当前层是否已交互过奥菲莉亚
        self.gear_faction_list: list[str] = []  # 本局开局选到的通用武备派系 同派系抱团时记录
        self.planned_route: list[str] = []  # 按 Tab 地图规划的接下来依次进入的区域类型
        self.route_plan_pending: bool = True  # 去下层入口前要不要打开地图规划 进入新区域时路线已走完就要
        self.map_reader: LostVoidMapReader | None = None  # 识别 Tab 地图的节点和连线
        # 本局记录 本局结束后清除 运行前先用只在内存里的 init_before_run 时换成写文件的
        self.run_memory: LostVoidRunMemory = LostVoidRunMemory(0, is_mock=True)

    def init_before_run(self) -> None:
        self.priority_updated = False
        self.dynamic_priority_list = []
        self.dynamic_abandon_list = []
        self.had_interacted_ophelia_on_current_level = False
        self.planned_route = []
        self.route_plan_pending = True
        self.map_reader = LostVoidMapReader(self.ctx.template_loader)
        # 读取已有记录 程序中途重启后从大世界接着跑时还能用
        self.run_memory = LostVoidRunMemory(self.ctx.current_instance_idx)
        self.init_lost_void_det_model()
        self.load_artifact_data()
        self.load_challenge_config()
        self.load_investigation_strategy()

    def reset_for_new_challenge(self) -> None:
        """
        每局开始前清空上一局识别的派系、动态优先级、路线和本局记录 避免带入下一局
        """
        self.gear_faction_list = []
        self.priority_updated = False
        self.dynamic_priority_list = []
        self.dynamic_abandon_list = []
        self.planned_route = []  # 第一层在入口规划
        self.route_plan_pending = True
        self.run_memory.clear()

    def on_challenge_end(self) -> None:
        """
        本局结束(通关或失败退出) 清除本局记录
        """
        self.planned_route = []
        self.route_plan_pending = True
        self.run_memory.clear()

    def on_enter_region(self, region_type: str | None) -> None:
        """
        进入下一个区域时 记录区域并推进规划的路线
        :param region_type: 进入的区域类型 None 表示未知
        """
        if region_type is not None:
            self.run_memory.add_region(region_type)

        if len(self.planned_route) == 0:
            pass
        elif region_type == LostVoidRegionType.FRIENDLY_TALK.value.value:
            # 挚交会谈是新一层的开头 上一层的路线不再用
            self.planned_route = []
        elif region_type is not None and self.planned_route[0] == region_type:
            self.planned_route.pop(0)
        else:
            # 没按规划走 剩下的路线已经对不上
            log.info(f'路线规划 | 进入 {region_type} 与规划 {self.planned_route[0]} 不一致 清空路线')
            self.planned_route = []

        # 路线走完或清空了 这个区域的下层入口前重新规划
        self.route_plan_pending = len(self.planned_route) == 0

    def need_route_plan(self) -> bool:
        """
        去下层入口前是否要打开地图规划路线
        包括每层开头(入口、第 1、2 次挚交会谈)、没按规划走、规划的路线走完
        每个区域最多规划一次 规划结果为空(前面只剩 THRONE、识别失败)时不反复打开地图
        第 3 次挚交会谈后面直接是终结之役 不用规划
        """
        return (
            self.challenge_config is not None
            and self.challenge_config.route_plan_by_map
            and self.route_plan_pending
            and self.run_memory.friendly_talk_times < lost_void_const.LAST_FRIENDLY_TALK_TIMES
        )

    def plan_route_by_map(self, map_screen: MatLike, blocked_type_list: list[str]) -> None:
        """
        识别 Tab 地图的节点和连线 按配置的区域优先级规划本层接下来的路线 只在 need_route_plan 的时机调用
        :param map_screen: Tab 菜单的地图页截图
        :param blocked_type_list: 当前房间寻路会忽略的入口类型 第一步不走这些门
        """
        self.route_plan_pending = False
        self.planned_route = []
        lost_void_map = self.map_reader.read(map_screen)
        log.info(f'路线规划 | 识别到的地图\n{lost_void_map.describe()}')
        route = lost_void_map.find_best_route(self.challenge_config.region_type_priority, blocked_type_list)
        if len(route) == 0:
            log.warning('路线规划 | 没识别到当前位置或往上的连线 这个区域按配置的区域优先级选门')
            return

        route_text = ' → '.join(f'节点{i}({LostVoidMap.type_text(lost_void_map.get_node(i))})' for i in route)
        log.info(f'路线规划 | 规划路线 {route_text}')
        self.planned_route = self._route_to_region_type(lost_void_map, route, blocked_type_list)
        log.info(f'路线规划 | 寻路依次找的入口 {" → ".join(self.planned_route)}')

    @staticmethod
    def _route_to_region_type(lost_void_map: LostVoidMap, route: list[int], blocked_type_list: list[str]) -> list[str]:
        """
        规划的节点编号转成寻路要找的入口类型 遇到没识别出类型的节点就停在那里
        混合节点的门上有几个图标 选一个同一步其它门上没有的类型 避免走错门
        同一步还有别的门是同一种类型时 分不清进的是哪扇 路线停在这一步 进去后看地图重新规划
        第一步在当前房间 寻路会忽略的类型看不到 不选这些类型 也不算别的门
        """
        region_type_list: list[str] = []
        last: LostVoidMapNode = lost_void_map.current
        for step, idx in enumerate(route):
            node = lost_void_map.get_node(idx)
            ignore_set = set(blocked_type_list) if step == 0 else set()
            type_list = [t for t in node.region_type_list if t not in ignore_set]
            if len(type_list) == 0:
                break
            other_type_set = {
                t
                for i in last.next_list if i != idx
                for t in lost_void_map.get_node(i).region_type_list
                if t not in ignore_set
            }
            unique_type = next((t for t in type_list if t not in other_type_set), None)
            region_type_list.append(unique_type if unique_type is not None else type_list[0])
            if unique_type is None:
                break
            last = node
        return region_type_list

    def is_general_gear_category(self, category: str) -> bool:
        """
        判断武备分类是否为通用武备派系
        :param category: 武备分类
        """
        return any(self._is_category_match(category, i) for i in lost_void_const.GENERAL_GEAR_CATEGORY_LIST)

    def get_owned_gear_faction_list(self) -> list[str]:
        """
        本局已有通用武备的派系 开局武备排最前 再按拿到的顺序加上局内拿到的武备
        鸣徽只能升级同派系的武备 没有这个派系的武备时 拿该派系鸣徽对升级没用
        """
        faction_list = self.gear_faction_list.copy()
        for item in self.run_memory.artifact_list:
            if (item['is_gear']
                    and item['category'] in lost_void_const.GENERAL_GEAR_CATEGORY_LIST
                    and item['category'] not in faction_list):
                faction_list.append(item['category'])
        return faction_list

    def is_gear_faction_match(self, artifact_pos: LostVoidArtifactPos) -> bool:
        """
        判断藏品是否与本局已有的通用武备同派系
        :param artifact_pos: 识别到的藏品
        """
        if self.challenge_config is None or not self.challenge_config.same_faction_first:
            return False
        return any(self._is_priority_rule_match(artifact_pos, i) for i in self.get_owned_gear_faction_list())

    def load_artifact_data(self) -> None:
        """
        加载 武备、鸣徽 信息
        @return:
        """
        self.all_artifact_list = []
        self.gear_by_name = {}
        self.cate_2_artifact = {}
        file_path = os.path.join(
            os_utils.get_path_under_work_dir('assets', 'game_data', 'hollow_zero', 'lost_void'),
            'lost_void_artifact_data.yml'
        )
        yaml_op = YamlOperator(file_path)
        for yaml_item in yaml_op.data:
            artifact = LostVoidArtifact(**yaml_item)
            self.all_artifact_list.append(artifact)
            self.gear_by_name[artifact.name] = artifact
            if artifact.category not in self.cate_2_artifact:
                self.cate_2_artifact[artifact.category] = []
            self.cate_2_artifact[artifact.category].append(artifact)

    def load_investigation_strategy(self) -> None:
        """
        加载调查策略
        :return:
        """
        self.investigation_strategy_list = []
        file_path = os.path.join(
            os_utils.get_path_under_work_dir('assets', 'game_data', 'hollow_zero', 'lost_void'),
            'lost_void_investigation_strategy.yml'
        )
        yaml_op = YamlOperator(file_path)
        for yaml_item in yaml_op.data:
            artifact = LostVoidInvestigationStrategy(**yaml_item)
            self.investigation_strategy_list.append(artifact)

    def init_lost_void_det_model(self):
        use_gpu = self.ctx.model_config.lost_void_det_gpu
        if self.detector is None or self.detector.gpu != use_gpu:
            self.detector = LostVoidDetector(
                model_name=self.ctx.model_config.lost_void_det,
                backup_model_name=self.ctx.model_config.lost_void_det_backup,
                model_download_url=self.ctx.model_config.get_model_download_base_url(
                    'lost_void_det',
                ),
                gh_proxy=self.ctx.env_config.is_gh_proxy,
                gh_proxy_url=self.ctx.env_config.gh_proxy_url if self.ctx.env_config.is_gh_proxy else None,
                personal_proxy=self.ctx.env_config.personal_proxy if self.ctx.env_config.is_personal_proxy else None,
                gpu=use_gpu,
                debug_trace_bus=self.ctx.debug_trace_bus,
            )

    def get_auto_op_name(self) -> str:
        """
        获取所需使用的自动战斗配置文件名
        :return:
        """
        if self.predefined_team_idx == -1:
            if self.challenge_config is not None:
                return self.challenge_config.auto_battle
        else:
            from zzz_od.config.team_config import PredefinedTeamInfo
            team_info: PredefinedTeamInfo = self.ctx.team_config.get_team_by_idx(self.predefined_team_idx)
            if team_info is not None:
                return team_info.auto_battle

        return '全配队通用'

    def load_challenge_config(self) -> None:
        """
        加载挑战配置
        :return:
        """
        config: LostVoidConfig = self.ctx.run_context.get_config(
            app_id=lost_void_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.challenge_config = LostVoidChallengeConfig(config.challenge_config)

    def is_last_rest_area(self) -> bool:
        """
        当前是否第三层终结之役前的最后一个休息区(第 3 次挚交会谈)
        """
        memory = self.run_memory
        return (
            memory.current_region_type == LostVoidRegionType.FRIENDLY_TALK.value.value
            and memory.friendly_talk_times >= lost_void_const.LAST_FRIENDLY_TALK_TIMES
        )

    def in_normal_world(self, screen: MatLike) -> bool:
        """
        判断当前画面是否在大世界里
        @param screen: 游戏画面
        @return:
        """
        result = screen_utils.find_area(self.ctx, screen, '战斗画面', '按键-普通攻击')
        if result == FindAreaResultEnum.TRUE:
            return True

        result = screen_utils.find_area(self.ctx, screen, '战斗画面', '按键-交互')
        if result == FindAreaResultEnum.TRUE:
            return True

        result = screen_utils.find_area(self.ctx, screen, '迷失之地-大世界', '按键-交互-不可用')
        return result == FindAreaResultEnum.TRUE

    def is_boss_health_bar_present(self, screen: MatLike) -> bool:
        """判断当前画面是否已出现 BOSS 血条。"""
        result = screen_utils.find_area(self.ctx, screen, '迷失之地-大世界', '标识-BOSS血条')
        return result == FindAreaResultEnum.TRUE

    def detect_to_go(self, screen: MatLike, screenshot_time: float, ignore_list: list[str] | None = None) -> DetectFrameResult:
        """
        识别需要前往的内容
        @param screen: 游戏画面
        @param screenshot_time: 截图时间
        @param ignore_list: 需要忽略的类别
        @return:
        """
        if ignore_list is None or len(ignore_list) == 0:
            to_detect_labels = None
        else:
            to_detect_labels = []
            for det_class in self.detector.idx_2_class.values():
                label = det_class.class_name
                if label[5:] not in ignore_list:
                    to_detect_labels.append(label)

        return self.ctx.lost_void.detector.run(screen, run_time=screenshot_time,
                                               label_list=to_detect_labels)

    def check_battle_encounter(self, screen: MatLike, screenshot_time: float) -> bool:
        """
        判断是否进入了战斗
        1. 识别右上角文本提示
        2. 识别角色血量扣减
        3. 识别黄光红光
        @param screen: 游戏截图
        @param screenshot_time: 截图时间
        @return: 是否进入了战斗
        """
        auto_op = self.ctx.auto_battle_context.auto_op
        state_record_service = self.ctx.auto_battle_context.state_record_service
        if auto_op is not None:
            in_battle = self.ctx.auto_battle_context.is_normal_attack_btn_available(screen)
            if in_battle:
                self.ctx.auto_battle_context.agent_context.check_agent_related(screen, screenshot_time)
                state = state_record_service.get_state_recorder(CommonAgentStateEnum.LIFE_DEDUCTION_31.value.state_name)
                if state is not None and state.last_record_time == screenshot_time:
                    return True

                self.ctx.auto_battle_context.dodge_context.check_dodge_flash(screen, screenshot_time)
                state = state_record_service.get_state_recorder(YoloStateEventEnum.DODGE_RED.value)
                if state is not None and state.last_record_time == screenshot_time:
                    return True
                state = state_record_service.get_state_recorder(YoloStateEventEnum.DODGE_YELLOW.value)
                if state is not None and state.last_record_time == screenshot_time:
                    return True

        area = self.ctx.screen_loader.get_area('迷失之地-大世界', '区域-文本提示')
        if screen_utils.find_by_ocr(self.ctx, screen, target_cn='战斗开始', area=area):
            return True
        return screen_utils.find_by_ocr(self.ctx, screen, target_cn='侦测到最后的敌人', area=area)

    def check_battle_encounter_in_period(self, total_check_seconds: float) -> bool:
        """
        持续一段时间检测是否进入战斗
        @param total_check_seconds: 总共检测的秒数
        @return:
        """
        start = time.time()

        while True:
            screenshot_time = time.time()

            if screenshot_time - start >= total_check_seconds:
                return False

            screenshot_time, screen = self.ctx.controller.screenshot()
            if self.check_battle_encounter(screen, screenshot_time):
                return True

            time.sleep(self.ctx.battle_assistant_config.screenshot_interval)

    def get_artifact_by_full_name(self, name_full_str: str) -> LostVoidArtifact | None:
        """
        根据完整名称 获取对应的藏品 名称需要完全一致
        :param name_full_str: 识别的文本 [类型]名称
        :return:
        """
        for artifact in self.all_artifact_list:
            artifact_full_name = artifact.display_name
            if artifact_full_name == name_full_str:
                return artifact

        return None

    def find_artifact_data(self, category: str, name: str) -> LostVoidArtifact | None:
        """
        按 OCR 出的分类和名称 在藏品数据里找对应的藏品 得到是否武备、等级
        名称允许个别错字(如 万能催化剂 识别成 万能催化物)
        :param category: 分类 卡牌和无详情的文字在这两类里一起找
        :param name: 名称
        :return: 找不到时为空 说明候选名没识别出来(比如 OCR 读到的是效果描述)
        """
        if category in ['卡牌', '无详情']:
            cate_list = ['卡牌', '无详情']
        else:
            normalized = self._normalize_category_text(category)
            cate_list = [i for i in self.cate_2_artifact if self._normalize_category_text(i) == normalized]
        art_list = [art for cate in cate_list for art in self.cate_2_artifact.get(cate, [])]
        idx = str_utils.find_in_list_with_fuzzy(name, [i.name for i in art_list], cutoff=0.7)
        return art_list[idx] if idx is not None else None

    def is_artifact_known(self, artifact: LostVoidArtifact) -> bool:
        """
        候选是否对上了藏品数据 对不上说明候选名没识别出来
        """
        return any(i is artifact for i in self.all_artifact_list)

    def match_artifact_by_ocr_full(self, name_full_str: str) -> LostVoidArtifact | None:
        """
        使用 [类型]名称 的文本匹配 藏品
        :param name_full_str: 识别的文本 [类型]名称
        :return 藏品
        """
        name_full_str = name_full_str.strip()
        name_full_str = name_full_str.replace('[', '')
        name_full_str = name_full_str.replace(']', '')
        name_full_str = name_full_str.replace('【', '')
        name_full_str = name_full_str.replace('】', '')

        to_sort_list = []

        # 取出与分类名称长度一致的前缀 用LCS来判断对应的cate分类
        for cate in self.cate_2_artifact:
            cate_name = gt(cate, 'game')

            if cate not in ['卡牌', '无详情']:
                if len(name_full_str) < len(cate_name):
                    continue

                prefix = name_full_str[:len(cate_name)]
                to_sort_list.append((cate, str_utils.longest_common_subsequence_length(prefix, cate_name)))

        # cate分类使用LCS排序
        to_sort_list.sort(key=lambda x: x[1], reverse=True)
        sorted_cate_list = [x[0] for x in to_sort_list] + ['卡牌', '无详情']

        # 按排序后的cate去匹配对应的藏品
        for cate in sorted_cate_list:
            art_list = self.cate_2_artifact[cate]
            # 符合分类的情况下 判断后缀和藏品名字是否一致
            for art in art_list:
                art_name = gt(art.name, 'game')
                suffix = name_full_str[-len(art_name):]
                if str_utils.find_by_lcs(art_name, suffix, percent=0.5):
                    return art

    def check_artifact_priority_input(self, input_str: str) -> tuple[list[str], str]:
        """
        校验优先级的文本输入
        当前采用“文本驱动”策略：
        - 只做去空行清洗
        - 不再强依赖本地藏品清单进行合法性过滤
        :param input_str:
        :return: 匹配的藏品和错误信息
        """
        if input_str is None or len(input_str) == 0:
            return [], ''

        input_arr = [i.strip() for i in input_str.split('\n')]
        filter_result_list: list[str] = []
        for i in input_arr:
            if len(i) == 0:
                continue
            filter_result_list.append(i)

        return filter_result_list, ''

    def check_region_type_priority_input(self, input_str: str) -> tuple[list[str], str]:
        """
        校验优先级的文本输入
        错误的输入会被过滤掉
        :param input_str:
        :return: 匹配的区域类型和错误信息
        """
        if input_str is None or len(input_str) == 0:
            return [], ''

        all_valid_region_type = [i.value.value for i in LostVoidRegionType]

        input_arr = [i.strip() for i in input_str.split('\n')]
        filter_result_list = []
        error_msg = ''
        for i in input_arr:
            if i in all_valid_region_type:
                filter_result_list.append(i)
            else:
                error_msg += f'输入非法 {i}'

        return filter_result_list, error_msg

    def get_artifact_pos(
        self,
        screen: MatLike,
        to_choose_gear_branch: bool = False,
        screen_name: str = '迷失之地-通用选择',
    ) -> list[LostVoidArtifactPos]:
        """
        识别画面中出现的藏品
        - 通用选择
        - 邦布商店
        :param screen: 游戏画面
        :param to_choose_gear_branch: 是否识别战术棱镜
        :param screen_name: 当前界面名称，用于读取“区域-藏品名称”
        :return:
        """
        # 识别其它标识
        title_word_list = [
            gt('有同流派武备', 'game'),
            gt('已选择', 'game'),
            gt('齿轮硬币不足', 'game'),
            gt('NEW!', 'game')
        ]

        artifact_pos_list = self._build_artifact_candidates_from_name_ocr(screen, screen_name)

        # 识别武备分支
        if to_choose_gear_branch:
            for branch in ['a', 'b']:
                template_id = f'gear_branch_{branch}'
                template = self.ctx.template_loader.get_template('lost_void', template_id)
                if template is None:
                    continue
                mrl = cv2_utils.match_template(screen, template.raw, mask=template.mask, threshold=0.9)
                if mrl is None or mrl.max is None:
                    continue

                # 找横坐标最接近的藏品
                closest_artifact_pos: LostVoidArtifactPos | None = None
                for artifact_pos in artifact_pos_list:
                    # 标识需要在藏品的右方
                    if not mrl.max.rect.x1 > artifact_pos.rect.center.x:
                        continue

                    if closest_artifact_pos is None:
                        closest_artifact_pos = artifact_pos
                        continue
                    old_dis = abs(mrl.max.center.x - closest_artifact_pos.rect.center.x)
                    new_dis = abs(mrl.max.center.x - artifact_pos.rect.center.x)
                    if new_dis < old_dis:
                        closest_artifact_pos = artifact_pos

                if closest_artifact_pos is not None:
                    original_artifact = closest_artifact_pos.artifact
                    branch_name = f'{original_artifact.name}-{branch}'
                    # 分支优先用藏品数据里的 对不上时按OCR候选直接派生
                    branch_artifact = self.find_artifact_data(original_artifact.category, branch_name)
                    if branch_artifact is None:
                        branch_artifact = LostVoidArtifact(
                            category=original_artifact.category,
                            name=branch_name,
                            level=original_artifact.level,
                            is_gear=original_artifact.is_gear,
                            template_id=original_artifact.template_id,
                        )
                    closest_artifact_pos.artifact = branch_artifact

        # 标题标识（已选择/NEW/齿轮硬币不足）仍按全图OCR做空间关联
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        for ocr_result, mrl in ocr_result_map.items():
            title_idx: int = str_utils.find_best_match_by_difflib(ocr_result, title_word_list)
            if title_idx is None or title_idx < 0:
                continue
            # 找横坐标最接近的藏品
            closest_artifact_pos: LostVoidArtifactPos | None = None
            for artifact_pos in artifact_pos_list:
                # 标题需要在藏品的上方
                if not mrl.max.rect.y2 < artifact_pos.rect.y1:
                    continue

                if closest_artifact_pos is None:
                    closest_artifact_pos = artifact_pos
                    continue
                old_dis = abs(mrl.max.center.x - closest_artifact_pos.rect.center.x)
                new_dis = abs(mrl.max.center.x - artifact_pos.rect.center.x)
                if new_dis < old_dis:
                    closest_artifact_pos = artifact_pos

            if closest_artifact_pos is not None:
                if title_idx == 0:  # 有同流派武备
                    closest_artifact_pos.has_same_style = True
                    # “有同流派武备”在该场景可视作已选状态，避免重复点击同一项。
                    closest_artifact_pos.chosen = True
                    closest_artifact_pos.can_choose = False
                elif title_idx == 1:  # 已选择
                    closest_artifact_pos.chosen = True
                    closest_artifact_pos.can_choose = False
                elif title_idx == 2:  # 齿轮硬币不足
                    closest_artifact_pos.can_choose = False
                elif title_idx == 3:  # NEW!
                    closest_artifact_pos.is_new = True

        # artifact_pos_list = [i for i in artifact_pos_list if i.can_choose]  # 这行导致了chosen_list只会是空的

        display_text = ', '.join([i.artifact.display_name for i in artifact_pos_list]) if len(artifact_pos_list) > 0 else '无'
        primary_cnt = len([i for i in artifact_pos_list if i.is_primary_name])
        secondary_cnt = len(artifact_pos_list) - primary_cnt
        log.info(f'当前识别藏品 主选={primary_cnt} 次选={secondary_cnt} {display_text}')

        return artifact_pos_list

    def _build_artifact_candidates_from_name_ocr(
        self,
        screen: MatLike,
        screen_name: str,
    ) -> list[LostVoidArtifactPos]:
        """
        从“区域-藏品名称”OCR结果构建候选：
        1. []/【】结构 => 主选
        2. 其他文本 => 次选
        并按X坐标聚合为每卡一个候选，保留坐标用于点击。
        """
        try:
            area = self.ctx.screen_loader.get_area(screen_name, '区域-藏品名称')
        except Exception as e:
            log.warning(f'获取区域失败 screen={screen_name} area=区域-藏品名称 err={e}')
            return []

        ocr_result_map = self.ctx.ocr_service.get_ocr_result_map(
            image=screen,
            rect=area.rect,
            crop_first=True,
        )

        raw_candidates: list[LostVoidArtifactPos] = []
        for ocr_text, mrl in ocr_result_map.items():
            text = ocr_text.strip()
            if len(text) == 0:
                continue

            artifact, is_primary_name = self._create_artifact_from_ocr_text(text)
            if artifact is None:
                continue

            for mr in mrl:
                raw_candidates.append(
                    LostVoidArtifactPos(
                        art=artifact,
                        rect=mr.rect,
                        ocr_text=text,
                        is_primary_name=is_primary_name,
                    )
                )

        if len(raw_candidates) == 0:
            return []

        raw_candidates.sort(key=lambda i: (i.rect.center.x, i.rect.center.y))

        # 按x坐标聚合同一卡片，优先保留主选文本
        merged_candidates: list[LostVoidArtifactPos] = []
        for candidate in raw_candidates:
            merged = False
            for idx, existed in enumerate(merged_candidates):
                if abs(existed.rect.center.x - candidate.rect.center.x) < 90:
                    merged_candidates[idx] = self._pick_better_candidate(existed, candidate)
                    merged = True
                    break
            if not merged:
                merged_candidates.append(candidate)

        merged_candidates.sort(key=lambda i: (i.rect.center.x, i.rect.center.y))
        return merged_candidates

    def _create_artifact_from_ocr_text(self, ocr_text: str) -> tuple[LostVoidArtifact | None, bool]:
        """
        从OCR文本提取候选藏品信息
        :return: (artifact, is_primary_name)
        """
        if ocr_text is None:
            return None, False

        text = ocr_text.strip()
        if len(text) < 2:
            return None, False

        normalized = text.replace('【', '[').replace('】', ']')
        match = re.match(r'^\[(.+?)\](.+)$', normalized)
        if match is not None:
            raw_category = match.group(1).strip()
            raw_name = match.group(2).strip()
            if len(raw_name) == 0:
                return None, False

            # 例如：
            # 1. “击破: 叩击” -> “击破”
            # 2. “强袭” -> “强袭”
            # 便于和配置里的分类文本做匹配
            if '：' in raw_category:
                category = raw_category.split('：', 1)[0].strip()
            elif ':' in raw_category:
                category = raw_category.split(':', 1)[0].strip()
            else:
                # 保留完整分类文本（如“异常·击破”“射吸式焊炬”），
                # 由匹配侧 _is_category_match 归一化处理，避免截断丢信息
                category = raw_category.strip()
            if len(category) == 0:
                category = raw_category

            # 对上藏品数据时用数据里的 才知道是不是武备、等级
            artifact = self.find_artifact_data(category, raw_name)
            if artifact is None:
                artifact = LostVoidArtifact(category=category, name=raw_name, level='?')
            return artifact, True

        # 卡牌界面常见主标题样式：`「xxx」yyy`
        # 该结构应视为主选名称，而不是无详情说明文本。
        quote_match = re.match(r'^「(.+?)」\s*(.+)$', text)
        if quote_match is not None:
            title = quote_match.group(1).strip()
            suffix = quote_match.group(2).strip()
            if len(title) > 0:
                artifact = self.find_artifact_data('卡牌', text)
                if artifact is None:
                    name = f'{title} {suffix}'.strip() if len(suffix) > 0 else title
                    artifact = LostVoidArtifact(category='卡牌', name=name, level='?')
                return artifact, True

        # 没有[]结构，归为次选，对不上藏品数据时直接保留原文。
        artifact = self.find_artifact_data('无详情', text)
        if artifact is None:
            artifact = LostVoidArtifact(category='无详情', name=text, level='?')
        return artifact, False

    @staticmethod
    def _pick_better_candidate(left: LostVoidArtifactPos, right: LostVoidArtifactPos) -> LostVoidArtifactPos:
        """
        同x聚合时的候选优先级：
        1. 主选（[]）优先
        2. 已知等级（S/A/B）优先
        3. OCR文本更长优先
        4. y更小（更靠上）优先
        """
        left_known = left.artifact.level in ['S', 'A', 'B']
        right_known = right.artifact.level in ['S', 'A', 'B']

        left_score = (
            1 if left.is_primary_name else 0,
            1 if left_known else 0,
            len(left.ocr_text),
            -left.rect.center.y,
        )
        right_score = (
            1 if right.is_primary_name else 0,
            1 if right_known else 0,
            len(right.ocr_text),
            -right.rect.center.y,
        )
        return right if right_score > left_score else left

    @staticmethod
    def _normalize_category_text(category: str) -> str:
        if category is None:
            return ''
        text = category.strip()
        for ch in [' ', '　', '·', ':', '：', '[', ']', '【', '】']:
            text = text.replace(ch, '')

        # 常见别名归一
        if text == '击破':
            return '异常击破'
        return text

    @classmethod
    def _is_category_match(cls, artifact_category: str, priority_category: str) -> bool:
        if artifact_category == priority_category:
            return True

        normalized_artifact = cls._normalize_category_text(artifact_category)
        normalized_priority = cls._normalize_category_text(priority_category)
        if len(normalized_artifact) == 0 or len(normalized_priority) == 0:
            return False

        if normalized_artifact == normalized_priority:
            return True

        # 允许“异常·击破”与“击破”这类前后缀兼容
        return normalized_artifact in normalized_priority or normalized_priority in normalized_artifact

    def _is_priority_rule_match(self, artifact_pos: LostVoidArtifactPos, priority_rule: str) -> bool:
        """
        判断某个候选是否命中优先级规则
        支持：
        1. 分类：`通用`
        2. 分类 + 名称：`通用 喷水枪`
        3. 分类 + 等级：`通用 A`
        4. 纯文本（用于次选）：`啦啦啦`
        """
        if priority_rule is None:
            return False

        rule = priority_rule.strip()
        if len(rule) == 0:
            return False

        artifact = artifact_pos.artifact
        split_idx = rule.find(' ')
        if split_idx == -1:
            # 单词条：优先按分类匹配，次选文本可按名称/原文匹配
            if self._is_category_match(artifact.category, rule):
                return True
            if artifact.name == rule:
                return True
            return artifact_pos.ocr_text == rule

        cate_name = rule[:split_idx].strip()
        item_name = rule[split_idx + 1:].strip()

        if not self._is_category_match(artifact.category, cate_name):
            return False

        if len(item_name) == 0:
            return True

        if item_name in ['S', 'A', 'B']:
            return artifact.level == item_name

        if artifact.name == item_name or artifact_pos.ocr_text.endswith(item_name):
            return True
        return str_utils.find_by_lcs(item_name, artifact.name, percent=0.6) or str_utils.find_by_lcs(item_name, artifact_pos.ocr_text, percent=0.6)

    def _extract_priority_rule_category(self, priority_rule: str) -> str | None:
        """
        提取优先级规则中的分类部分。
        - `强攻` -> `强攻`
        - `强攻 割草除根` -> `强攻`
        """
        if priority_rule is None:
            return None

        rule = priority_rule.strip()
        if len(rule) == 0:
            return None

        split_idx = rule.find(' ')
        if split_idx == -1:
            return rule

        return rule[:split_idx].strip()

    def _is_specific_priority_rule(self, priority_rule: str) -> bool:
        """
        判断是否为“具体武备/角色”规则。
        只有纯分类规则（如 `强攻`）会被动态放弃组覆盖；
        带具体名称/等级的规则（如 `强攻 割草除根`）仍保留优先级。
        """
        if priority_rule is None:
            return False

        return ' ' in priority_rule.strip()

    def get_artifact_by_priority(
            self, artifact_list: list[LostVoidArtifactPos], choose_num: int,
            consider_priority_1: bool = True, consider_priority_2: bool = True,
            consider_not_in_priority: bool = True,
            ignore_idx_list: list[int] | None = None,
            consider_priority_new: bool = False,
    ) -> list[LostVoidArtifactPos]:
        """
        根据优先级 返回需要选择的藏品
        :param artifact_list: 识别到的藏品结果
        :param choose_num: 需要选择的数量
        :param consider_priority_1: 是否考虑优先级1的内容
        :param consider_priority_2: 是否考虑优先级2的内容
        :param consider_not_in_priority: 是否考虑优先级以外的选项
        :param ignore_idx_list: 需要忽略的下标
        :param consider_priority_new: 是否优先选择NEW类型 最高优先级
        :return: 按优先级选择的结果
        """
        def fmt_artifact(pos: LostVoidArtifactPos, idx: int | None = None) -> str:
            prefix = f'#{idx} ' if idx is not None else ''
            return (
                f'{prefix}{pos.artifact.display_name}'
                f' [分类={pos.artifact.category} 等级={pos.artifact.level} 主选={pos.is_primary_name} NEW={pos.is_new}]'
                f' [坐标=({pos.rect.center.x},{pos.rect.center.y})]'
            )

        raw_artifact_list = list(artifact_list)
        raw_text = '; '.join([fmt_artifact(pos, idx) for idx, pos in enumerate(raw_artifact_list)]) if len(raw_artifact_list) > 0 else '无'
        log.debug(f'优先级输入候选(去重前) 共{len(raw_artifact_list)}个: {raw_text}')

        artifact_list = self.remove_overlapping_artifacts(artifact_list)
        artifact_list = sorted(artifact_list, key=lambda i: (i.rect.center.x, i.rect.center.y))

        log.debug(f'当前考虑优先级 数量={choose_num} NEW!={consider_priority_new} 第一优先级={consider_priority_1} 第二优先级={consider_priority_2} 其他={consider_not_in_priority}')
        dedup_text = '; '.join([fmt_artifact(pos, idx) for idx, pos in enumerate(artifact_list)]) if len(artifact_list) > 0 else '无'
        log.debug(f'优先级输入候选(去重后) 共{len(artifact_list)}个: {dedup_text}')

        # 六级优先级模型，按顺序匹配：
        # 第1级 动态优先级 / 第2级 配置第一 / 第3级 配置第二 / 第4级 战斗组
        # 第5级 其他（非优先级）补位 / 第6级 放弃组 最后补位
        # 参数只控制放行到第几级：
        # consider_priority_1 -> 放行第0、1、2级（第0级=已有通用武备派系 仅同派系抱团时启用）
        # consider_priority_2 -> 放行第3、4级
        # consider_not_in_priority -> 放行第5、6级
        # 注意：主选组整体优先于次选组（任务目标优先），级别序只在组内生效。
        priority_levels: list[tuple[str, list[str]]] = []

        # 第0级 已有通用武备派系 同派系抱团时排在NEW和其他优先级之前
        faction_list: list[str] = []
        if consider_priority_1 and self.challenge_config.same_faction_first:
            faction_list = self.get_owned_gear_faction_list()

        if consider_priority_1:
            if len(self.dynamic_priority_list) > 0:
                priority_levels.append(('第1级(动态)', self.dynamic_priority_list))
            if len(self.challenge_config.artifact_priority) > 0:
                priority_levels.append(('第2级(配置一)', self.challenge_config.artifact_priority))

        if consider_priority_2:
            if len(self.challenge_config.artifact_priority_2) > 0:
                priority_levels.append(('第3级(配置二)', self.challenge_config.artifact_priority_2))
            if len(self.challenge_config.artifact_priority_in_battle) > 0:
                priority_levels.append(('第4级(战斗组)', self.challenge_config.artifact_priority_in_battle))

        # 四个优先级配置列表全部为空时 才强制考虑非优先级的
        # 不能依据门控后的 priority_levels 判断（门控可能因轮次放行限制挡住有内容的配置）
        if (len(faction_list) == 0
                and len(self.dynamic_priority_list) == 0
                and len(self.challenge_config.artifact_priority) == 0
                and len(self.challenge_config.artifact_priority_2) == 0
                and len(self.challenge_config.artifact_priority_in_battle) == 0):
            consider_not_in_priority = True

        level_text_list = [f'{name}={",".join(rule_list) if len(rule_list) > 0 else "空"}' for name, rule_list in priority_levels]
        if len(faction_list) > 0:
            level_text_list.insert(0, f'第0级(已有武备派系)={",".join(faction_list)}')
        level_text = ' '.join(level_text_list) if len(level_text_list) > 0 else '无'
        abandon_text = ', '.join(self.dynamic_abandon_list) if len(self.dynamic_abandon_list) > 0 else '空'
        primary_cnt = len([i for i in artifact_list if i.is_primary_name])
        secondary_cnt = len(artifact_list) - primary_cnt
        log.info(f'优先级决策 | 候选={len(artifact_list)}(主选={primary_cnt} 次选={secondary_cnt}) 需选={choose_num} | 放行=第1,2级:{consider_priority_1} 第3,4级:{consider_priority_2} 补位:{consider_not_in_priority} NEW:{consider_priority_new}')
        log.debug(f'优先级规则 | {level_text} 放弃组={abandon_text}')

        priority_idx_list: list[int] = []  # 优先级排序的下标
        choose_reason_map: dict[int, str] = {}
        ignored_idx_set = set(ignore_idx_list) if ignore_idx_list is not None else set()
        all_idx_list = [i for i in range(len(artifact_list)) if i not in ignored_idx_set]
        primary_idx_list = [i for i in all_idx_list if artifact_list[i].is_primary_name]
        secondary_idx_list = [i for i in all_idx_list if not artifact_list[i].is_primary_name]
        ignored_text = ', '.join([str(i) for i in sorted(ignored_idx_set)]) if len(ignored_idx_set) > 0 else '无'
        log.debug(f'优先级分组 忽略下标={ignored_text} 主选下标={primary_idx_list} 次选下标={secondary_idx_list}')

        def add_idx_if_absent(target_idx: int, reason: str) -> None:
            if target_idx in priority_idx_list:
                return
            priority_idx_list.append(target_idx)
            choose_reason_map[target_idx] = reason
            log.debug(f'候选入队 {fmt_artifact(artifact_list[target_idx], target_idx)} 原因={reason}')

        # 规则：先主选，再次选
        for group_name, group_idx_list in [('主选', primary_idx_list), ('次选', secondary_idx_list)]:
            # 0) 同派系抱团 已有通用武备派系最先考虑
            for faction in faction_list:
                for idx in group_idx_list:
                    if idx in priority_idx_list:
                        continue
                    if self._is_priority_rule_match(artifact_list[idx], faction):
                        add_idx_if_absent(idx, f'{group_name}-第0级(已有武备派系) 命中规则="{faction}"')

            # 1) 主次组内先考虑NEW
            if consider_priority_new:
                for level in ['S', 'A', 'B', '?']:
                    for idx in group_idx_list:
                        if idx in priority_idx_list:
                            continue
                        pos = artifact_list[idx]
                        if not pos.is_new:
                            continue
                        if level != '?' and pos.artifact.level != level:
                            continue
                        if level == '?' and pos.artifact.level in ['S', 'A', 'B']:
                            continue
                        add_idx_if_absent(idx, f'{group_name}-NEW优先 命中等级={level}')

            # 2) 按优先级级别匹配（坐标顺序作为同优先级稳定序）
            level_hit_parts: list[str] = []
            for level_name, priority_list in priority_levels:
                rule_parts: list[str] = []
                for priority_rule in priority_list:
                    matched_idx_list: list[int] = []
                    for idx in group_idx_list:
                        if idx in priority_idx_list:
                            continue
                        if self._is_priority_rule_match(artifact_list[idx], priority_rule):
                            matched_idx_list.append(idx)
                            add_idx_if_absent(idx, f'{group_name}-{level_name} 命中规则="{priority_rule}"')
                    if len(matched_idx_list) > 0:
                        hit_text = ', '.join([fmt_artifact(artifact_list[idx], idx) for idx in matched_idx_list])
                        rule_parts.append(f'规则"{priority_rule}"命中[{hit_text}]')
                    else:
                        rule_parts.append(f'规则"{priority_rule}"未命中')
                if len(rule_parts) > 0:
                    level_hit_parts.append(f'{level_name}: ' + '; '.join(rule_parts))
            if len(level_hit_parts) > 0:
                log.debug(f'优先级匹配 | {group_name}组 | ' + ' || '.join(level_hit_parts))

            # 3) 其余候选按坐标顺序补齐：先普通（第5级），再放弃组（第6级）
            if consider_not_in_priority:
                normal_idx_list: list[int] = []
                abandon_idx_list: list[int] = []
                for idx in group_idx_list:
                    if idx in priority_idx_list:
                        continue
                    artifact_category = artifact_list[idx].artifact.category
                    # 放弃组里存的是代理人类型值（如「击破」），藏品分类可能是「异常·击破」，
                    # 需要走归一化匹配才能命中，不能用精确 in
                    is_abandoned = any(
                        self._is_category_match(artifact_category, abandon_category)
                        for abandon_category in self.dynamic_abandon_list
                    )
                    if is_abandoned:
                        abandon_idx_list.append(idx)
                    else:
                        normal_idx_list.append(idx)

                for idx in normal_idx_list:
                    add_idx_if_absent(idx, f'{group_name}-非优先级补位')
                for idx in abandon_idx_list:
                    add_idx_if_absent(idx, f'{group_name}-动态放弃组补位')

        result_list: list[LostVoidArtifactPos] = []
        for i in range(choose_num):
            if i >= len(priority_idx_list):
                continue
            result_list.append(artifact_list[priority_idx_list[i]])

        display_text = ','.join([i.artifact.display_name for i in result_list]) if len(result_list) > 0 else '无'
        selected_detail = []
        for i, pos in enumerate(result_list):
            idx = priority_idx_list[i]
            reason = choose_reason_map.get(idx, '未知原因')
            selected_detail.append(f'{fmt_artifact(pos, idx)} 原因={reason}')
        selected_text = '; '.join(selected_detail) if len(selected_detail) > 0 else '无'
        queue_text = ', '.join([str(i) for i in priority_idx_list]) if len(priority_idx_list) > 0 else '空'
        log.debug(f'优先级入队顺序 下标={queue_text}')
        log.debug(f'当前符合优先级列表 {display_text}')
        log.debug(f'最终选择明细 {selected_text}')

        if len(result_list) > 0:
            log.info(f'优先级决策 | 结果 | 选中={len(result_list)} | {selected_text}')
        elif consider_not_in_priority:
            log.info('优先级决策 | 结果 | 未选中 | 原因=候选为空或全部被忽略')
        else:
            log.info('优先级决策 | 结果 | 未选中 | 原因=优先级规则未命中任何候选 且 非优先级未开启')

        return result_list

    def remove_overlapping_artifacts(self, artifact_list: list[LostVoidArtifactPos]) -> list[LostVoidArtifactPos]:
        """
        去掉横坐标太近的藏品，保留y坐标较小的（位置较高的）

        :param artifact_list: 待处理的藏品列表
        :return: 去重后的藏品列表
        """
        if len(artifact_list) <= 1:
            return artifact_list

        # 按x坐标排序，便于后续处理
        sorted_artifacts = sorted(artifact_list, key=lambda art: art.rect.center.x)
        result = []

        i = 0
        while i < len(sorted_artifacts):
            current_art = sorted_artifacts[i]
            overlapping_arts = [current_art]

            # 找出所有与当前藏品横坐标接近的藏品
            j = i + 1
            while j < len(sorted_artifacts):
                next_art = sorted_artifacts[j]
                x_distance = abs(current_art.rect.center.x - next_art.rect.center.x)

                if x_distance < 100:  # 横坐标太近
                    overlapping_arts.append(next_art)
                    log.debug(f'发现重叠藏品: {current_art.artifact.display_name} 和 {next_art.artifact.display_name}, 距离: {x_distance}')
                    j += 1
                else:
                    break  # 由于已排序，后面的距离只会更大

            # 在重叠的藏品中选择y坐标最小的（位置最高的）
            best_art = min(overlapping_arts, key=lambda art: art.rect.center.y)
            result.append(best_art)

            if len(overlapping_arts) > 1:
                removed_arts = [art.artifact.display_name for art in overlapping_arts if art != best_art]
                log.debug(f'保留 {best_art.artifact.display_name}，移除 {", ".join(removed_arts)}')

            # 跳过所有重叠的藏品
            i = j

        return result

    def get_entry_by_priority(
        self,
        entry_list: list[MoveTargetWrapper],
        ignore_entry_list: list[str] | None = None,
    ) -> MoveTargetWrapper | None:
        """
        根据优先级 返回一个前往的入口
        多个相同入口时选择最右 (因为丢失寻找目标的时候是往左转找)
        :param entry_list:
        :param ignore_entry_list:
        :return:
        """
        if entry_list is None or len(entry_list) == 0:
            return None

        ignore_entry_set: set[str] = set(ignore_entry_list) if ignore_entry_list is not None else set()
        if self.had_interacted_ophelia_on_current_level:
            ignore_entry_set.add(LostVoidRegionType.ELITE.value.value)

        # 先找规划的下一个区域 规划里更后面的区域不是当前房间要进的门
        # 没有规划或画面里没有规划的门时 按配置的区域优先级
        priority_list = self.planned_route[:1] + self.challenge_config.region_type_priority
        for priority in priority_list:
            if priority in ignore_entry_set:
                continue

            target: MoveTargetWrapper | None = None

            for entry in entry_list:
                for target_name in entry.target_name_list:
                    if target_name in ignore_entry_set:
                        continue
                    if target_name != priority:
                        continue

                    if target is None or entry.entire_rect.x1 > target.entire_rect.x1:
                        target = entry

            if target is not None:
                return target

        target: MoveTargetWrapper | None = None
        for entry in entry_list:
            if any(target_name in ignore_entry_set for target_name in entry.target_name_list):
                continue
            if target is None or entry.entire_rect.x1 > target.entire_rect.x1:
                target = entry

        return target
