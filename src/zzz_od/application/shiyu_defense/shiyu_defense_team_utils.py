import difflib

from cv2.typing import MatLike

from one_dragon.base.operation.application import application_const
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.utils.i18_utils import gt
from zzz_od.application.shiyu_defense import shiyu_defense_const
from zzz_od.application.shiyu_defense.shiyu_defense_config import (
    ShiyuDefenseConfig,
    ShiyuDefenseTeamConfig,
)
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import DmgTypeEnum


class DefensePhaseTeamInfo:

    def __init__(self,
                 phase_weakness: list[DmgTypeEnum], phase_resistance: list[DmgTypeEnum]):
        """
        每阶段的队伍信息
        @param phase_weakness: 弱点
        @param phase_resistance: 抗性
        """
        self.phase_weakness: list[DmgTypeEnum] = phase_weakness
        self.phase_resistance: list[DmgTypeEnum] = phase_resistance
        self.team_idx: int = -1  # 最终使用的队伍下标

        self.same_as_weakness: int = 0  # 是否与弱点一致
        self.same_as_resistance: int = 0  # 是否与抗性一致

    def cal_score(self, defense_team_config: ShiyuDefenseTeamConfig | None) -> None:
        """
        计算得分
        @param defense_team_config: 预备编队 设置的对应弱点
        @return:
        """
        if defense_team_config is None:
            # 非法的下标 用最差的评分
            self.same_as_weakness = 0
            self.same_as_resistance = 1
            return

        target_weakness_list = defense_team_config.weakness_list
        for target_weakness in target_weakness_list:
            if target_weakness in self.phase_weakness:
                self.same_as_weakness = 1
            if target_weakness in self.phase_resistance:
                self.same_as_resistance = 1

    @property
    def score(self) -> int:
        return self.same_as_weakness - self.same_as_resistance


class DefenseTeamSearcher:

    def __init__(self, ctx: ZContext, team_list: list[DefensePhaseTeamInfo]):
        """
        队伍搜索器
        @param ctx: 上下文
        @param team_list: 初始化的队伍 用于提供属性
        """
        self.ctx: ZContext = ctx

        self.config: ShiyuDefenseConfig = self.ctx.run_context.get_config(
            app_id=shiyu_defense_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.team_list: list[DefensePhaseTeamInfo] = team_list
        self.best_team_list: list[DefensePhaseTeamInfo] = []

        self.phase_cnt: int = len(team_list)  # 阶段数量
        self.predefined_team_list: list[PredefinedTeamInfo] = self.ctx.team_config.team_list  # 预备编队
        self.defense_team_config: dict[int, ShiyuDefenseTeamConfig] = {}

        for team in self.predefined_team_list:
            self.defense_team_config[team.idx] = self.config.get_config_by_team_idx(team.idx)

        self.chosen_idx: set = set()

    def search(self) -> list[DefensePhaseTeamInfo]:
        """
        搜索 返回最佳配队
        @return:
        """
        self.chosen_idx = set()
        self.dfs(0)
        return self.best_team_list

    def dfs(self, phase_idx: int):
        """
        递归搜索
        @param phase_idx: 阶段下标
        @return:
        """
        if phase_idx >= self.phase_cnt:
            self.compare_and_save_best()
            return

        if self.no_way_better(phase_idx):
            # 剪枝
            return

        current_phase_team = self.team_list[phase_idx]

        weakness_idx_list: list[int] = []
        resistance_idx_list: list[int] = []
        normal_idx_list: list[int] = []

        for predefined_team in self.predefined_team_list:
            # 之前已经选过了
            if predefined_team.idx in self.chosen_idx:
                continue

            defense_team_config = self.defense_team_config.get(predefined_team.idx, None)
            if defense_team_config is None or not defense_team_config.for_critical:
                continue

            sames_weakness: bool = False
            sames_resistance: bool = False
            for dmg_type in defense_team_config.weakness_list:
                if dmg_type in current_phase_team.phase_weakness:
                    sames_weakness = True
                elif dmg_type in current_phase_team.phase_resistance:
                    sames_resistance = True

            if sames_weakness:
                weakness_idx_list.append(predefined_team.idx)
            elif sames_resistance:
                resistance_idx_list.append(predefined_team.idx)
            else:
                normal_idx_list.append(predefined_team.idx)

        # 优先考虑弱点 迫不得已再选逆抗性
        candidate_idx_list = weakness_idx_list + normal_idx_list + resistance_idx_list
        for idx in candidate_idx_list:
            new_team = self.predefined_team_list[idx]
            conflict: bool = False  # 是否与现有配队有代理人冲突
            for old_idx in self.chosen_idx:
                if self.is_team_conflict(new_team, self.predefined_team_list[old_idx]):
                    conflict = True
                    break

            if conflict:
                continue

            self.chosen_idx.add(idx)
            current_phase_team.team_idx = idx

            defense_team_config = self.defense_team_config.get(idx, None)
            current_phase_team.cal_score(defense_team_config)

            self.dfs(phase_idx + 1)

            self.chosen_idx.remove(idx)
            current_phase_team.team_idx = -1

    def compare_and_save_best(self) -> bool:
        """
        对比当前结果和最佳结果 并保存
        @return: 是否保存到最佳结果
        """
        new_score: int = 0
        for team in self.team_list:
            new_score += team.score

        old_score: int = 0
        for team in self.best_team_list:
            old_score += team.score

        if len(self.best_team_list) == 0 or new_score > old_score:
            self.best_team_list = []
            for team in self.team_list:
                new_team = DefensePhaseTeamInfo(team.phase_weakness, team.phase_resistance)
                new_team.team_idx = team.team_idx
                new_team.same_as_weakness = team.same_as_weakness
                new_team.same_as_resistance = team.same_as_resistance
                self.best_team_list.append(new_team)
            return True
        else:
            return False

    def no_way_better(self, next_phase_idx: int) -> bool:
        """
        当前搜索是否无可能更优
        @param next_phase_idx: 下一个搜索的阶段下标
        @return:
        """
        # 剩余还有多少个阶段没选
        phase_left = self.phase_cnt - next_phase_idx

        new_score: int = 0
        for team in self.team_list:
            new_score += team.score

        old_score: int = 0
        for team in self.best_team_list:
            old_score += team.score

        # 剩余阶段都符合弱点拿1分 依然不能比现在更高分
        return new_score + phase_left <= old_score

    def is_team_conflict(self, team_1: PredefinedTeamInfo, team_2: PredefinedTeamInfo) -> bool:
        """
        两队的代理人是否冲突
        @param team_1:
        @param team_2:
        @return:
        """
        team_1_id_set = {i for i in team_1.agent_id_list if i != 'unknown'}
        team_2_id_set = {i for i in team_2.agent_id_list if i != 'unknown'}
        return len(team_1_id_set & team_2_id_set) > 0


def calc_teams(
    ctx: ZContext,
    screen: MatLike,
    phase_cnt: int = 2,
    type_cnt: int = 2,
    screen_name: str = '式舆防卫战'
) -> list[DefensePhaseTeamInfo]:
    """
    计算配队
    @param ctx: 上下文
    @param screen: 游戏画面
    @param phase_cnt: 阶段数量
    @param type_cnt: 属性数量
    @param screen_name: 屏幕模板名称
    @return:
    """
    # 先识别弱点和数量
    team_list = []

    for phase_idx in range(phase_cnt):
        weakness_list = []
        resistance_list = []
        for type_idx in range(type_cnt):
            area = ctx.screen_loader.get_area(screen_name, f'弱点-{phase_idx + 1}-{type_idx + 1}')
            weakness_list.append(check_type_by_area(ctx, screen, area))

            area = ctx.screen_loader.get_area(screen_name, f'抗性-{phase_idx + 1}-{type_idx + 1}')
            resistance_list.append(check_type_by_area(ctx, screen, area))

        team = DefensePhaseTeamInfo(weakness_list, resistance_list)
        team_list.append(team)

    searcher = DefenseTeamSearcher(ctx, team_list)
    return searcher.search()


def calc_teams_for_multi_room(
    ctx: ZContext,
    screen: MatLike,
    screen_template: str,
    room_count: int,
) -> list[DefensePhaseTeamInfo]:
    """
    计算多间模式节点的最佳编队
    对每间房间右半区域 OCR，按 y 坐标分组弱点(上)和抗性(下)
    """
    team_list = []
    room_names = ['第一间', '第二间', '第三间']

    for room_idx in range(room_count):
        room_name = room_names[room_idx]
        area = ctx.screen_loader.get_area(screen_template, room_name)
        ocr_result = ctx.ocr.crop_and_run_ocr(screen, area.rect)

        # 检查得分：OCR 结果为 "0" 或空（识别不到也算0分）才打
        all_text = ' '.join(ocr_result.keys()).strip()
        has_unfinished = all_text == '0' or all_text == ''
        if not has_unfinished:
            team_info = DefensePhaseTeamInfo([DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN],
                                              [DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN])
            team_info.team_idx = -1  # 标记跳过
            team_list.append(team_info)
            continue

        # 属性识别：用"第一间属性"等区域
        attr_name = f'{room_name}属性'
        area = ctx.screen_loader.get_area(screen_template, attr_name)
        if area is None:
            # 没有属性区域，保留未知属性，不标记已完成跳过
            team_info = DefensePhaseTeamInfo([DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN],
                                              [DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN])
            team_info.team_idx = 0  # 保持待配队占位，不标记跳过
            team_list.append(team_info)
            continue
        ocr_result = ctx.ocr.crop_and_run_ocr(screen, area.rect)

        # 收集所有包含"属性"的文本及 y 坐标
        items: list[tuple[int, str]] = []
        boundary_y: int | None = None
        for text, match_list in ocr_result.items():
            if '强敌抗性' in text:
                for match in match_list:
                    boundary_y = match.y
            elif '属性' in text:
                for match in match_list:
                    items.append((match.y, text))

        if len(items) == 0 or boundary_y is None:
            # 属性识别失败，保留未知属性，不标记已完成跳过
            team_list.append(DefensePhaseTeamInfo([DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN],
                                                  [DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN]))
            continue

        weakness_texts = [t for y, t in items if y < boundary_y]
        resistance_texts = [t for y, t in items if y >= boundary_y]

        weakness_list = _extract_dmg_types(weakness_texts)
        resistance_list = _extract_dmg_types(resistance_texts)

        # 补齐到2个
        while len(weakness_list) < 2:
            weakness_list.append(DmgTypeEnum.UNKNOWN)
        while len(resistance_list) < 2:
            resistance_list.append(DmgTypeEnum.UNKNOWN)

        team_list.append(DefensePhaseTeamInfo(weakness_list[:2], resistance_list[:2]))
        team_list[-1].team_idx = 0  # 标记待配队，searcher 会覆盖

    # 只传需要配队的房间给搜索器，跳过已通关（team_idx == -1）的房间
    scored_indices = [i for i, t in enumerate(team_list) if t.team_idx != -1]
    scored_teams = [team_list[i] for i in scored_indices]
    if len(scored_teams) > 0:
        searcher = DefenseTeamSearcher(ctx, scored_teams)
        search_result = searcher.search()
        for orig_idx, result_team in zip(scored_indices, search_result):
            team_list[orig_idx] = result_team
    return team_list


def _extract_dmg_types(texts: list[str]) -> list[DmgTypeEnum]:
    """
    从 OCR 文本列表中提取伤害类型
    """
    result: list[DmgTypeEnum] = []
    full_text = ' '.join(texts)

    type_list = [i for i in DmgTypeEnum if i != DmgTypeEnum.UNKNOWN]
    target_list = [gt(i.value, 'game') for i in DmgTypeEnum if i != DmgTypeEnum.UNKNOWN]

    for target in target_list:
        if target in full_text:
            idx = target_list.index(target)
            result.append(type_list[idx])

    return result


def check_type_by_area(ctx: ZContext, screen: MatLike, area: ScreenArea) -> DmgTypeEnum:
    """
    识别一个属性
    @param ctx: 上下文
    @param screen: 游戏画面
    @param area: 识别区域
    @return:
    """
    ocr_map = ctx.ocr.crop_and_run_ocr(screen, area.rect)

    type_list = [i for i in DmgTypeEnum if i != DmgTypeEnum.UNKNOWN]
    target_list = [gt(i.value, 'game') for i in DmgTypeEnum if i != DmgTypeEnum.UNKNOWN]

    for ocr_result in ocr_map:
        match_results = difflib.get_close_matches(ocr_result, target_list, n=1)
        if match_results is not None and len(match_results) > 0:
            idx = target_list.index(match_results[0])
            return type_list[idx]

    return DmgTypeEnum.UNKNOWN
