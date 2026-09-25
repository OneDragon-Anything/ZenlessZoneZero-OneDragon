import difflib

from cv2.typing import MatLike

from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.utils.i18_utils import gt
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent, AgentEnum, AgentTypeEnum, DmgTypeEnum


class DefensePhaseTeamInfo:

    def __init__(
        self,
        phase_weakness: list[DmgTypeEnum],
        phase_resistance: list[DmgTypeEnum],
    ):
        self.phase_weakness: list[DmgTypeEnum] = phase_weakness
        self.phase_resistance: list[DmgTypeEnum] = phase_resistance
        self.team_idx: int = -1
        self.score: float = 0
        self.is_completed: bool = False


class DefenseTeamSearcher:

    # 虚狩代理人,配队评分给 1.2 倍加权。
    # 列表硬编码,游戏新增虚狩角色需手动补。概念见 docs/game/gameplay/combat.md「虚狩」。
    VOID_HUNTER_AGENT_ID_LIST: list[str] = [
        'yixuan',
        'hoshimi_miyabi',
        'yeshunguang',
        'remielle',
    ]
    VOID_HUNTER_SCORE_MULTIPLIER: float = 1.2

    def __init__(
        self,
        ctx: ZContext,
        target_list: list[DefensePhaseTeamInfo],
        candidate_team_idx_list: list[int],
    ):
        self.ctx: ZContext = ctx
        self.target_list: list[DefensePhaseTeamInfo] = target_list
        self.candidate_team_list: list[PredefinedTeamInfo] = [
            team
            for team_idx in candidate_team_idx_list
            if (team := self.ctx.team_config.get_team_by_idx(team_idx)) is not None
        ]
        self.best_team_list: list[DefensePhaseTeamInfo] = []
        self.best_score: float = -1
        self.chosen_team_idx_set: set[int] = set()
        self.chosen_agent_id_set: set[str] = set()

    def search(self) -> list[DefensePhaseTeamInfo]:
        self._search_target(0)
        return self.best_team_list

    def _search_target(self, target_idx: int) -> None:
        if target_idx >= len(self.target_list):
            self._save_best()
            return

        target = self.target_list[target_idx]
        for team in self.candidate_team_list:
            if team.idx in self.chosen_team_idx_set:
                continue

            agent_id_set = self._get_agent_id_set(team)
            if len(agent_id_set & self.chosen_agent_id_set) > 0:
                continue

            self.chosen_team_idx_set.add(team.idx)
            self.chosen_agent_id_set.update(agent_id_set)
            target.team_idx = team.idx
            target.score = self._calc_team_score(team, target)

            self._search_target(target_idx + 1)

            target.team_idx = -1
            target.score = 0
            self.chosen_team_idx_set.remove(team.idx)
            self.chosen_agent_id_set.difference_update(agent_id_set)

    def _save_best(self) -> None:
        total_score = sum(target.score for target in self.target_list)
        if len(self.best_team_list) > 0 and total_score <= self.best_score:
            return

        self.best_score = total_score
        self.best_team_list = []
        for target in self.target_list:
            result = DefensePhaseTeamInfo(target.phase_weakness, target.phase_resistance)
            result.team_idx = target.team_idx
            result.score = target.score
            self.best_team_list.append(result)

    def _calc_team_score(
        self,
        team: PredefinedTeamInfo,
        target: DefensePhaseTeamInfo,
    ) -> float:
        agent_list = self._get_agents(team)
        output_score_list: list[float] = []
        aligned_agent_count = 0

        for agent in agent_list:
            if agent.agent_type in [AgentTypeEnum.ATTACK, AgentTypeEnum.RUPTURE]:
                output_score_list.append(
                    self._get_agent_score(agent, target, is_anomaly=False)
                )
            elif agent.agent_type == AgentTypeEnum.ANOMALY:
                if agent.dmg_type in [DmgTypeEnum.WIND, DmgTypeEnum.LUMIFLUX]:
                    continue
                output_score_list.append(
                    self._get_agent_score(agent, target, is_anomaly=True)
                )
            elif agent.agent_type in [
                AgentTypeEnum.STUN,
                AgentTypeEnum.SUPPORT,
                AgentTypeEnum.DEFENSE,
            ]:
                aligned_agent_count += 1

        # 染色分支:风 / 流明异常角色不按自身属性评分,而是取队内其他异常角色的属性契合度
        # (靠队友其他异常「染色」触发紊流)。详见 docs/game/gameplay/combat.md「染色」。
        for agent in agent_list:
            if agent.agent_type != AgentTypeEnum.ANOMALY:
                continue
            if agent.dmg_type not in [DmgTypeEnum.WIND, DmgTypeEnum.LUMIFLUX]:
                continue

            dye_score_list = []
            for other_agent in agent_list:
                if other_agent.agent_id == agent.agent_id:
                    continue
                if other_agent.agent_type != AgentTypeEnum.ANOMALY:
                    continue
                if (
                    agent.dmg_type == DmgTypeEnum.WIND
                    and other_agent.dmg_type == DmgTypeEnum.LUMIFLUX
                ):
                    # 流明可变属性:与风队友组队时流明算风伤(非异色),无法触发风乱流,故风异常排除流明队友
                    continue
                dye_score_list.append(
                    self._get_dmg_type_score(
                        other_agent.dmg_type,
                        target,
                        is_anomaly=True,
                    )
                )

            output_score_list.append(
                self._apply_void_hunter_multiplier(
                    agent,
                    max(dye_score_list, default=1),
                )
            )

        if len(output_score_list) == 0:
            return 0

        return sum(output_score_list) + max(output_score_list) * aligned_agent_count

    def _get_agents(self, team: PredefinedTeamInfo) -> list[Agent]:
        agent_map = {agent.value.agent_id: agent.value for agent in AgentEnum}
        return [
            agent_map[agent_id]
            for agent_id in team.agent_id_list
            if agent_id in agent_map
        ]

    def _get_agent_id_set(self, team: PredefinedTeamInfo) -> set[str]:
        return {agent_id for agent_id in team.agent_id_list if agent_id != 'unknown'}

    def _get_agent_score(
        self,
        agent: Agent,
        target: DefensePhaseTeamInfo,
        is_anomaly: bool,
    ) -> float:
        score = self._get_dmg_type_score(agent.dmg_type, target, is_anomaly)
        return self._apply_void_hunter_multiplier(agent, score)

    def _apply_void_hunter_multiplier(
        self,
        agent: Agent,
        score: float,
    ) -> float:
        if agent.agent_id in self.VOID_HUNTER_AGENT_ID_LIST:
            return score * self.VOID_HUNTER_SCORE_MULTIPLIER
        return score

    def _get_dmg_type_score(
        self,
        dmg_type: DmgTypeEnum,
        target: DefensePhaseTeamInfo,
        is_anomaly: bool,
    ) -> float:
        """按属性对弱点 / 抗性的契合度给分(评分权重,非伤害倍率,仅用于排序选队)。"""
        if dmg_type in target.phase_weakness:
            return 1.69 if is_anomaly else 1.3
        if dmg_type in target.phase_resistance:
            return 0.49 if is_anomaly else 0.7
        return 1


def select_teams(
    ctx: ZContext,
    target_list: list[DefensePhaseTeamInfo],
    candidate_team_idx_list: list[int],
) -> list[DefensePhaseTeamInfo]:
    """
    为一至三个目标选择总分最高且互不冲突的预备编队
    """
    searcher = DefenseTeamSearcher(ctx, target_list, candidate_team_idx_list)
    return searcher.search()


def get_team_targets(
    ctx: ZContext,
    screen: MatLike,
    phase_cnt: int = 2,
    type_cnt: int = 2,
    screen_name: str = '式舆防卫战',
) -> list[DefensePhaseTeamInfo]:
    """
    识别普通节点的弱点和抗性
    """
    target_list: list[DefensePhaseTeamInfo] = []

    for phase_idx in range(phase_cnt):
        weakness_list: list[DmgTypeEnum] = []
        resistance_list: list[DmgTypeEnum] = []
        for type_idx in range(type_cnt):
            weakness_area = ctx.screen_loader.get_area(
                screen_name,
                f'弱点-{phase_idx + 1}-{type_idx + 1}',
            )
            weakness_list.append(check_type_by_area(ctx, screen, weakness_area))

            resistance_area = ctx.screen_loader.get_area(
                screen_name,
                f'抗性-{phase_idx + 1}-{type_idx + 1}',
            )
            resistance_list.append(check_type_by_area(ctx, screen, resistance_area))

        target_list.append(DefensePhaseTeamInfo(weakness_list, resistance_list))

    return target_list


def get_team_targets_for_multi_room(
    ctx: ZContext,
    screen: MatLike,
    screen_template: str,
    room_count: int,
) -> list[DefensePhaseTeamInfo]:
    """
    识别多间模式每间房的弱点和抗性
    """
    target_list: list[DefensePhaseTeamInfo] = []
    room_names = ['第一间', '第二间', '第三间']

    for room_idx in range(room_count):
        room_name = room_names[room_idx]
        room_area = ctx.screen_loader.get_area(screen_template, room_name)
        room_ocr_result = ctx.ocr.crop_and_run_ocr(screen, room_area.rect)
        all_text = ' '.join(room_ocr_result.keys()).strip()
        if all_text != '0' and all_text != '':
            completed_target = DefensePhaseTeamInfo(
                [DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN],
                [DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN],
            )
            completed_target.is_completed = True
            target_list.append(completed_target)
            continue

        attribute_area = ctx.screen_loader.get_area(screen_template, f'{room_name}属性')
        if attribute_area is None:
            target_list.append(
                DefensePhaseTeamInfo(
                    [DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN],
                    [DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN],
                )
            )
            continue

        attribute_ocr_result = ctx.ocr.crop_and_run_ocr(screen, attribute_area.rect)
        item_list: list[tuple[int, str]] = []
        resistance_boundary_y: int | None = None
        for text, match_list in attribute_ocr_result.items():
            if '强敌抗性' in text:
                for match in match_list:
                    resistance_boundary_y = match.y
            elif '属性' in text:
                for match in match_list:
                    item_list.append((match.y, text))

        if len(item_list) == 0 or resistance_boundary_y is None:
            target_list.append(
                DefensePhaseTeamInfo(
                    [DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN],
                    [DmgTypeEnum.UNKNOWN, DmgTypeEnum.UNKNOWN],
                )
            )
            continue

        weakness_text_list = [text for y, text in item_list if y < resistance_boundary_y]
        resistance_text_list = [text for y, text in item_list if y >= resistance_boundary_y]
        weakness_list = _extract_dmg_types(weakness_text_list)
        resistance_list = _extract_dmg_types(resistance_text_list)

        while len(weakness_list) < 2:
            weakness_list.append(DmgTypeEnum.UNKNOWN)
        while len(resistance_list) < 2:
            resistance_list.append(DmgTypeEnum.UNKNOWN)

        target_list.append(DefensePhaseTeamInfo(weakness_list[:2], resistance_list[:2]))

    return target_list


def _extract_dmg_types(text_list: list[str]) -> list[DmgTypeEnum]:
    """
    从 OCR 文本列表中提取伤害类型
    """
    result: list[DmgTypeEnum] = []
    full_text = ' '.join(text_list)

    dmg_type_list = [dmg_type for dmg_type in DmgTypeEnum if dmg_type != DmgTypeEnum.UNKNOWN]
    target_text_list = [gt(dmg_type.value, 'game') for dmg_type in dmg_type_list]

    for target_text in target_text_list:
        if target_text in full_text:
            result.append(dmg_type_list[target_text_list.index(target_text)])

    return result


def check_type_by_area(
    ctx: ZContext,
    screen: MatLike,
    area: ScreenArea,
) -> DmgTypeEnum:
    """
    识别一个属性
    """
    ocr_map = ctx.ocr.crop_and_run_ocr(screen, area.rect)

    dmg_type_list = [dmg_type for dmg_type in DmgTypeEnum if dmg_type != DmgTypeEnum.UNKNOWN]
    target_text_list = [gt(dmg_type.value, 'game') for dmg_type in dmg_type_list]

    for ocr_result in ocr_map:
        match_result_list = difflib.get_close_matches(ocr_result, target_text_list, n=1)
        if len(match_result_list) > 0:
            return dmg_type_list[target_text_list.index(match_result_list[0])]

    return DmgTypeEnum.UNKNOWN
