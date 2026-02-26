import os
import time
from typing import Optional, List, Tuple
import re

from cv2.typing import MatLike

from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.base.operation.application import application_const
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.screen_utils import FindAreaResultEnum
from one_dragon.utils import os_utils, str_utils, cv2_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon.yolo.detect_utils import DetectFrameResult
from zzz_od.application.hollow_zero.lost_void import lost_void_const
from zzz_od.application.hollow_zero.lost_void.context.lost_void_artifact import LostVoidArtifact
from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import LostVoidDetector
from zzz_od.application.hollow_zero.lost_void.context.lost_void_investigation_strategy import \
    LostVoidInvestigationStrategy
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import LostVoidRegionType, \
    LostVoidChallengeConfig
from zzz_od.application.hollow_zero.lost_void.lost_void_config import LostVoidConfig
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_artifact_pos import LostVoidArtifactPos
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import MoveTargetWrapper
from zzz_od.auto_battle.auto_battle_dodge_context import YoloStateEventEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import CommonAgentStateEnum


class LostVoidContext:

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx

        self.detector: Optional[LostVoidDetector] = None
        self.challenge_config: Optional[LostVoidChallengeConfig] = None

        self.all_artifact_list: List[LostVoidArtifact] = []  # 武备 + 鸣徽
        self.gear_by_name: dict[str, LostVoidArtifact] = {}  # key=名称 value=武备
        self.cate_2_artifact: dict[str, List[LostVoidArtifact]] = {}  # key=分类 value=藏品

        self.investigation_strategy_list: list[LostVoidInvestigationStrategy] = []  # 调查战略

        self.predefined_team_idx: int = -1  # 本次挑战所使用的预备编队
        self.priority_updated: bool = False  # 动态优先级是否已经更新
        self.dynamic_priority_list: list[str] = []  # 动态获取的优先级列表

    def init_before_run(self) -> None:
        self.priority_updated = False
        self.dynamic_priority_list = []
        self.init_lost_void_det_model()
        self.load_artifact_data()
        self.load_challenge_config()
        self.load_investigation_strategy()

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
                gh_proxy=self.ctx.env_config.is_gh_proxy,
                gh_proxy_url=self.ctx.env_config.gh_proxy_url if self.ctx.env_config.is_gh_proxy else None,
                personal_proxy=self.ctx.env_config.personal_proxy if self.ctx.env_config.is_personal_proxy else None,
                gpu=use_gpu
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
        if result == FindAreaResultEnum.TRUE:
            return True

        return False

    def detect_to_go(self, screen: MatLike, screenshot_time: float, ignore_list: Optional[List[str]] = None) -> DetectFrameResult:
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
        if screen_utils.find_by_ocr(self.ctx, screen, target_cn='侦测到最后的敌人', area=area):
            return True

        return False

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

    def get_artifact_by_full_name(self, name_full_str: str) -> Optional[LostVoidArtifact]:
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

    def match_artifact_by_ocr_full(self, name_full_str: str) -> Optional[LostVoidArtifact]:
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
        for cate in self.cate_2_artifact.keys():
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

    def check_artifact_priority_input(self, input_str: str) -> Tuple[List[str], str]:
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

    def check_region_type_priority_input(self, input_str: str) -> Tuple[List[str], str]:
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
                closest_artifact_pos: Optional[LostVoidArtifactPos] = None
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
                    # 分支标识按OCR候选直接派生，不依赖本地藏品库
                    closest_artifact_pos.artifact = LostVoidArtifact(
                        category=original_artifact.category,
                        name=f'{original_artifact.name}-{branch}',
                        level=original_artifact.level,
                        is_gear=original_artifact.is_gear,
                        template_id=original_artifact.template_id,
                    )

        # 标题标识（已选择/NEW/齿轮硬币不足）仍按全图OCR做空间关联
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        for ocr_result, mrl in ocr_result_map.items():
            title_idx: int = str_utils.find_best_match_by_difflib(ocr_result, title_word_list)
            if title_idx is None or title_idx < 0:
                continue
            # 找横坐标最接近的藏品
            closest_artifact_pos: Optional[LostVoidArtifactPos] = None
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

    def _create_artifact_from_ocr_text(self, ocr_text: str) -> Tuple[Optional[LostVoidArtifact], bool]:
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

            # 例如 “击破: 叩击” -> “击破”，便于和配置里的分类文本做匹配
            category = raw_category.split('：', 1)[0].split(':', 1)[0].strip()
            if len(category) == 0:
                category = raw_category

            return LostVoidArtifact(category=category, name=raw_name, level='?'), True

        # 没有[]结构，归为次选，直接保留原文。
        return LostVoidArtifact(category='无详情', name=text, level='?'), False

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

    def get_artifact_by_priority(
            self, artifact_list: List[LostVoidArtifactPos], choose_num: int,
            consider_priority_1: bool = True, consider_priority_2: bool = True,
            consider_not_in_priority: bool = True,
            ignore_idx_list: Optional[list[int]] = None,
            consider_priority_new: bool = False,
    ) -> List[LostVoidArtifactPos]:
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
        artifact_list = self.remove_overlapping_artifacts(artifact_list)
        artifact_list = sorted(artifact_list, key=lambda i: (i.rect.center.x, i.rect.center.y))

        log.info(f'当前考虑优先级 数量={choose_num} NEW!={consider_priority_new} 第一优先级={consider_priority_1} 第二优先级={consider_priority_2} 其他={consider_not_in_priority}')
        
        # 合并动态优先级和静态优先级
        priority_list_to_consider = []
        
        final_priority_list_1 = self.dynamic_priority_list.copy()
        if consider_priority_1 and self.challenge_config.artifact_priority:
            final_priority_list_1.extend(self.challenge_config.artifact_priority)
        priority_list_to_consider.append(final_priority_list_1)
        
        if consider_priority_2 and self.challenge_config.artifact_priority_2:
            priority_list_to_consider.append(self.challenge_config.artifact_priority_2)

        if len(priority_list_to_consider) == 0:  # 两个优先级都是空的时候 强制考虑非优先级的
            consider_not_in_priority = True

        priority_idx_list: List[int] = []  # 优先级排序的下标
        ignored_idx_set = set(ignore_idx_list) if ignore_idx_list is not None else set()
        all_idx_list = [i for i in range(len(artifact_list)) if i not in ignored_idx_set]
        primary_idx_list = [i for i in all_idx_list if artifact_list[i].is_primary_name]
        secondary_idx_list = [i for i in all_idx_list if not artifact_list[i].is_primary_name]

        def add_idx_if_absent(target_idx: int) -> None:
            if target_idx in priority_idx_list:
                return
            priority_idx_list.append(target_idx)

        # 规则：先主选，再次选
        for group_idx_list in [primary_idx_list, secondary_idx_list]:
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
                        add_idx_if_absent(idx)

            # 2) 按优先级文本匹配（坐标顺序作为同优先级稳定序）
            for priority_list in priority_list_to_consider:
                for priority_rule in priority_list:
                    for idx in group_idx_list:
                        if idx in priority_idx_list:
                            continue
                        if self._is_priority_rule_match(artifact_list[idx], priority_rule):
                            add_idx_if_absent(idx)

            # 3) 其余候选按坐标顺序补齐
            if consider_not_in_priority:
                for idx in group_idx_list:
                    if idx in priority_idx_list:
                        continue
                    add_idx_if_absent(idx)

        result_list: List[LostVoidArtifactPos] = []
        for i in range(choose_num):
            if i >= len(priority_idx_list):
                continue
            result_list.append(artifact_list[priority_idx_list[i]])

        display_text = ','.join([i.artifact.display_name for i in result_list]) if len(result_list) > 0 else '无'
        log.info(f'当前符合优先级列表 {display_text}')

        return result_list

    def remove_overlapping_artifacts(self, artifact_list: List[LostVoidArtifactPos]) -> List[LostVoidArtifactPos]:
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

                if x_distance < 200:  # 横坐标太近
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

    def get_entry_by_priority(self, entry_list: List[MoveTargetWrapper]) -> Optional[MoveTargetWrapper]:
        """
        根据优先级 返回一个前往的入口
        多个相同入口时选择最右 (因为丢失寻找目标的时候是往左转找)
        :param entry_list:
        :return:
        """
        if entry_list is None or len(entry_list) == 0:
            return None

        for priority in self.challenge_config.region_type_priority:
            target: Optional[MoveTargetWrapper] = None

            for entry in entry_list:
                for target_name in entry.target_name_list:
                    if target_name != priority:
                        continue

                    if target is None or entry.entire_rect.x1 > target.entire_rect.x1:
                        target = entry

            if target is not None:
                return target

        target: Optional[MoveTargetWrapper] = None
        for entry in entry_list:
            if target is None or entry.entire_rect.x1 > target.entire_rect.x1:
                target = entry

        return target
