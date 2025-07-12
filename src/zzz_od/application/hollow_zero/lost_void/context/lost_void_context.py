import time

import os
from cv2.typing import MatLike
from typing import Optional, List, Tuple

from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.screen_utils import FindAreaResultEnum
from one_dragon.utils import os_utils, str_utils, cv2_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon.yolo.detect_utils import DetectFrameResult
from zzz_od.application.hollow_zero.lost_void.context.lost_void_artifact import LostVoidArtifact
from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import LostVoidDetector
from zzz_od.application.hollow_zero.lost_void.context.lost_void_investigation_strategy import \
    LostVoidInvestigationStrategy
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import LostVoidRegionType, \
    LostVoidChallengeConfig
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_artifact_pos import LostVoidArtifactPos
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import MoveTargetWrapper
from zzz_od.auto_battle.auto_battle_dodge_context import YoloStateEventEnum
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import CommonAgentStateEnum


class LostVoidContext:

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx

        self.detector: Optional[LostVoidDetector] = None
        self.auto_op: Optional[AutoBattleOperator] = None  # 自动战斗指令
        self.challenge_config: Optional[LostVoidChallengeConfig] = None

        self.all_artifact_list: List[LostVoidArtifact] = []  # 武备 + 鸣徽
        self.gear_by_name: dict[str, LostVoidArtifact] = {}  # key=名称 value=武备
        self.cate_2_artifact: dict[str, List[LostVoidArtifact]] = {}  # key=分类 value=藏品

        self.investigation_strategy_list: list[LostVoidInvestigationStrategy] = []  # 调查战略

        self.predefined_team_idx: int = -1  # 本次挑战所使用的预备编队

    def init_before_run(self) -> None:
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

    def init_auto_op(self) -> None:
        """
        初始化自动战斗指令
        @return:
        """
        if self.auto_op is not None:  # 如果有上一个 先销毁
            self.auto_op.dispose()
        self.auto_op = AutoBattleOperator(self.ctx, 'auto_battle', self.get_auto_op_name())
        success, msg = self.auto_op.init_before_running()
        if not success:
            raise Exception(msg)

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
        self.challenge_config = LostVoidChallengeConfig(self.ctx.lost_void_config.challenge_config)

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
        if self.auto_op is not None:
            in_battle = self.auto_op.auto_battle_context.is_normal_attack_btn_available(screen)
            if in_battle:
                self.auto_op.auto_battle_context.agent_context.check_agent_related(screen, screenshot_time)
                state = self.auto_op.get_state_recorder(CommonAgentStateEnum.LIFE_DEDUCTION_31.value.state_name)
                if state is not None and state.last_record_time == screenshot_time:
                    return True

                self.auto_op.auto_battle_context.dodge_context.check_dodge_flash(screen, screenshot_time)
                state = self.auto_op.get_state_recorder(YoloStateEventEnum.DODGE_RED.value)
                if state is not None and state.last_record_time == screenshot_time:
                    return True
                state = self.auto_op.get_state_recorder(YoloStateEventEnum.DODGE_YELLOW.value)
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

            screen = self.ctx.controller.screenshot()
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
        错误的输入会被过滤掉
        :param input_str:
        :return: 匹配的藏品和错误信息
        """
        if input_str is None or len(input_str) == 0:
            return [], ''

        input_arr = [i.strip() for i in input_str.split('\n')]
        filter_result_list = []
        error_msg = ''
        for i in input_arr:
            if len(i) == 0:
                continue
            split_idx = i.find(' ')
            if split_idx != -1:
                cate_name = i[:split_idx]
                item_name = i[split_idx+1:]
            else:
                cate_name = i
                item_name = ''

            is_valid: bool = False

            if cate_name in self.cate_2_artifact:

                if item_name == '':  # 整个分类
                    is_valid = True
                elif item_name in ['S', 'A', 'B']:  # 按等级
                    is_valid = True
                else:
                    for art in self.cate_2_artifact[cate_name]:
                        if item_name == art.name:
                            is_valid = True
                            break

            if not is_valid:
                error_msg += f'输入非法 {i}'
            else:
                filter_result_list.append(i)

        return filter_result_list, error_msg

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
            self, screen: MatLike,
            to_choose_gear_branch: bool = False
    ) -> list[LostVoidArtifactPos]:
        """
        识别画面中出现的藏品
        - 通用选择
        - 邦布商店
        :param screen: 游戏画面
        :param to_choose_gear_branch: 是否识别战术棱镜
        :return:
        """
        artifact_name_list: list[str] = []
        for art in self.ctx.lost_void.all_artifact_list:
            artifact_name_list.append(gt(art.display_name, 'game'))

        artifact_pos_list: list[LostVoidArtifactPos] = []
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        for ocr_result, mrl in ocr_result_map.items():
            title_idx: int = str_utils.find_best_match_by_difflib(ocr_result, artifact_name_list)
            if title_idx is None or title_idx < 0:
                continue

            artifact = self.ctx.lost_void.all_artifact_list[title_idx]
            artifact_pos = LostVoidArtifactPos(artifact, mrl.max.rect)
            artifact_pos_list.append(artifact_pos)

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
                    branch_artifact_name: str = f'{original_artifact.display_name}-{branch}'
                    branch_artifact = self.ctx.lost_void.get_artifact_by_full_name(branch_artifact_name)
                    if branch_artifact is not None:
                        closest_artifact_pos.artifact = branch_artifact

        # 识别其它标识
        title_word_list = [
            gt('有同流派武备', 'game'),
            gt('已选择', 'game'),
            gt('齿轮硬币不足', 'game'),
            gt('NEW!', 'game')
        ]
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
                if title_idx == 1:  # 已选择
                    closest_artifact_pos.chosen = True
                    closest_artifact_pos.can_choose = False
                elif title_idx == 2:  # 齿轮硬币不足
                    closest_artifact_pos.can_choose = False
                elif title_idx == 3:  # NEW!
                    closest_artifact_pos.is_new = True

        artifact_pos_list = [i for i in artifact_pos_list if i.can_choose]

        display_text = ', '.join([i.artifact.display_name for i in artifact_pos_list]) if len(artifact_pos_list) > 0 else '无'
        log.info(f'当前识别藏品 {display_text}')

        return artifact_pos_list

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

        log.info(f'当前考虑优先级 数量={choose_num} NEW!={consider_priority_new} 第一优先级={consider_priority_1} 第二优先级={consider_priority_2} 其他={consider_not_in_priority}')
        priority_list_to_consider = []
        if consider_priority_1:
            priority_list_to_consider.append(self.challenge_config.artifact_priority)
        if consider_priority_2:
            priority_list_to_consider.append(self.challenge_config.artifact_priority_2)

        if len(priority_list_to_consider) == 0:  # 两个优先级都是空的时候 强制考虑非优先级的
            consider_not_in_priority = True

        priority_idx_list: List[int] = []  # 优先级排序的下标

        # 优先选择NEW类型 最高优先级
        if consider_priority_new:
            for level in ['S', 'A', 'B']:
                for idx in range(len(artifact_list)):
                    if ignore_idx_list is not None and idx in ignore_idx_list:  # 需要忽略的下标
                        continue

                    if idx in priority_idx_list:  # 已经加入过了
                        continue

                    pos = artifact_list[idx]
                    if pos.artifact.level != level:
                        continue

                    if not pos.is_new:
                        continue

                    priority_idx_list.append(idx)

        # 按优先级顺序 将匹配的藏品下标加入
        # 同时 优先考虑等级高的
        for target_level in ['S', 'A', 'B']:
            for priority_list in priority_list_to_consider:
                for priority in priority_list:
                    split_idx = priority.find(' ')
                    if split_idx != -1:
                        cate_name = priority[:split_idx]
                        item_name = priority[split_idx+1:]
                    else:
                        cate_name = priority
                        item_name = ''

                    for idx in range(len(artifact_list)):
                        if ignore_idx_list is not None and idx in ignore_idx_list:  # 需要忽略的下标
                            continue

                        artifact: LostVoidArtifact = artifact_list[idx].artifact

                        if artifact.level != target_level:
                            continue

                        if idx in priority_idx_list:  # 已经加入过了
                            continue

                        if artifact.category != cate_name:  # 不符合分类
                            continue

                        if item_name == '':
                            priority_idx_list.append(idx)
                            continue

                        if item_name in ['S', 'A', 'B']:
                            if artifact.level == item_name:
                                priority_idx_list.append(idx)
                            continue

                        if item_name == artifact.name:
                            priority_idx_list.append(idx)

        # 将剩余的 按等级加入
        if consider_not_in_priority:
            for level in ['S', 'A', 'B']:
                for idx in range(len(artifact_list)):
                    if ignore_idx_list is not None and idx in ignore_idx_list:  # 需要忽略的下标
                        continue

                    if idx in priority_idx_list:  # 已经加入过了
                        continue

                    artifact: LostVoidArtifact = artifact_list[idx].artifact

                    if artifact.level == level:
                        priority_idx_list.append(idx)

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

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        @return:
        """
        if self.auto_op is not None:
            self.auto_op.stop_running()
            self.auto_op.dispose()
