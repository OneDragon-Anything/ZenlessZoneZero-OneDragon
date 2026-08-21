import time
from collections import Counter
from typing import TYPE_CHECKING, ClassVar

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.game_data.agent import Agent, AgentEnum
from zzz_od.operation.agent_template_matcher import match_team_agent_template
from zzz_od.operation.zzz_operation import ZOperation

if TYPE_CHECKING:
    from one_dragon.base.matcher.match_result import MatchResult
    from zzz_od.config.team_config import PredefinedTeamInfo
    from zzz_od.context.zzz_context import ZContext

# 矩阵行动入口面板右下「UP代理人」头像行 (1080p)
MATRIX_ENTRY_UP_RECT: Rect = Rect(1480, 680, 1850, 810)

# UP徽章在代理人卡片左上角 与卡片中心的最大偏移 (矩阵编队选择网格卡片约155x200)
BADGE_MAX_DX: int = 95
BADGE_MAX_DY: int = 110


def compute_up_lineup(up_agents: list[Agent],
                      team_list: 'list[PredefinedTeamInfo]',
                      slot_cnt: int = 3) -> list[Agent]:
    """
    按「UP优先 + 同队搭档」规则算出目标配队

    1. 已拥有的UP全部进队 (拥有判定 = 出现在任意预备编队里)
    2. 一个UP都没拥有时 用第一个UP保底 (特遣调查可用试用UP 任意一位UP通关即有特遣补给)
    3. 剩余空位按「与已选UP同队次数 → 总出场次数」从高到低补搭档 (排除未拥有的UP)

    :param up_agents: 当期UP代理人列表
    :param team_list: 预备编队配置 (拥有判定与搭档统计的数据源)
    :param slot_cnt: 编队人数
    :return: 目标配队 (长度<=slot_cnt)
    """
    owned_ids: set[str] = {
        agent_id
        for team in team_list
        for agent_id in team.agent_id_list
        if agent_id != 'unknown'
    }
    owned_up = [a for a in up_agents if a.agent_id in owned_ids]
    lineup: list[Agent] = owned_up[:slot_cnt]
    if len(lineup) == 0 and len(up_agents) > 0:
        lineup = [up_agents[0]]

    up_ids_all = {a.agent_id for a in up_agents}
    co_cnt: Counter = Counter()
    freq_cnt: Counter = Counter()
    for team in team_list:
        ids = [i for i in team.agent_id_list if i != 'unknown']
        for i in ids:
            freq_cnt[i] += 1
        if any(a.agent_id in ids for a in lineup):
            for i in ids:
                co_cnt[i] += 1

    agent_by_id: dict[str, Agent] = {e.value.agent_id: e.value for e in AgentEnum}
    lineup_ids = {a.agent_id for a in lineup}
    partner_ids = sorted(
        [i for i in owned_ids
         if i not in up_ids_all and i not in lineup_ids and i in agent_by_id],
        key=lambda i: (-co_cnt[i], -freq_cnt[i], i),
    )
    for pid in partner_ids:
        if len(lineup) >= slot_cnt:
            break
        lineup.append(agent_by_id[pid])
    return lineup


def recognize_matrix_up(ctx: 'ZContext', screen) -> tuple[list[Agent], list[Agent]]:
    """
    在矩阵行动入口面板识别「UP代理人」头像行

    头像行含主战UP与协战UP 协战头像带「协战」标签且固定在最右

    :param ctx: 上下文
    :param screen: 游戏画面
    :return: (主战UP列表, 协战UP列表) 识别失败返回 ([], [])
    """
    mr_list: list[MatchResult] = match_team_agent_template(ctx, screen, MATRIX_ENTRY_UP_RECT, None)
    mr_list.sort(key=lambda m: m.left_top.x)
    if len(mr_list) == 0:
        return [], []

    support_idx: int | None = None
    ocr_result_list = ctx.ocr_service.get_ocr_result_list(image=screen, rect=MATRIX_ENTRY_UP_RECT)
    for ocr_text in ocr_result_list:
        if '协战' in ocr_text.data:
            support_idx = min(
                range(len(mr_list)),
                key=lambda i: abs(mr_list[i].center.x - ocr_text.center.x),
            )
            break
    if support_idx is None:
        # 协战标签识别不到时 按最右侧兜底
        support_idx = len(mr_list) - 1

    mains = [m.data for i, m in enumerate(mr_list) if i != support_idx]
    support = [mr_list[support_idx].data]
    return mains, support


def find_up_in_agent_grid(ctx: 'ZContext', screen, rect: Rect) -> list[Agent]:
    """
    在代理人网格里按UP徽章找UP代理人

    UP徽章的OCR召回率不高(约一半) 只作为入口识别的补充来源

    :param ctx: 上下文
    :param screen: 游戏画面
    :param rect: 代理人网格区域
    :return: 带UP徽章的代理人列表
    """
    mr_list: list[MatchResult] = match_team_agent_template(ctx, screen, rect, None)
    if len(mr_list) == 0:
        return []
    ocr_result_list = ctx.ocr_service.get_ocr_result_list(image=screen, rect=rect)
    found: dict[str, Agent] = {}
    for ocr_text in ocr_result_list:
        if ocr_text.data.strip().upper() != 'UP':
            continue
        best = None
        best_dist = None
        for mr in mr_list:
            dx = abs(mr.center.x - ocr_text.center.x)
            dy = abs(mr.center.y - ocr_text.center.y)
            if dx > BADGE_MAX_DX or dy > BADGE_MAX_DY:
                continue
            dist = dx + dy
            if best_dist is None or dist < best_dist:
                best = mr
                best_dist = dist
        if best is not None:
            found[best.data.agent_id] = best.data
    return list(found.values())


class LostVoidComposeUpTeam(ZOperation):
    """
    特遣调查出战画面: 逐槽位从选人面板换入目标配队

    画面机制 (2026-08-21 实拍 归档见测试仓 screens/通用-出战/):
    出战画面三个编队槽 + 邦布槽; 点击槽位打开选人面板(斜排卡片, 含试用代理人),
    点卡片高亮后点右侧丝带确认换入。
    注意: 空槽模式丝带是 SELECT(确认默认高亮卡) 占用槽替换模式才是 CANCEL,
    放弃选择必须点左上返回箭头, 点丝带会把默认高亮的卡确认进队。
    选人面板排序随槽位/模式变化 目标可能在任意页 需翻页查找。
    """

    SLOT_X: ClassVar[list[int]] = [475, 950, 1430]
    SLOT_Y: ClassVar[int] = 540
    NAME_RECTS: ClassVar[list[Rect]] = [
        Rect(170, 890, 560, 965),
        Rect(640, 890, 1030, 965),
        Rect(1110, 890, 1500, 975),
    ]
    DEPLOY_BTN_RECT: ClassVar[Rect] = Rect(1600, 980, 1900, 1075)  # 出战按钮
    PICKER_RECT: ClassVar[Rect] = Rect(1000, 0, 1920, 1080)
    PICKER_MARK_RECT: ClassVar[Rect] = Rect(440, 20, 740, 90)  # 潜能歧分/快捷编队 文本
    RIBBON_POS: ClassVar[Point] = Point(1870, 540)  # SELECT / CANCEL 丝带
    BACK_POS: ClassVar[Point] = Point(110, 52)  # 返回箭头
    MAX_SCROLL_PAGES: ClassVar[int] = 6

    def __init__(self, ctx: 'ZContext', lineup: list[Agent], up_ids: set[str]):
        """
        :param ctx: 上下文
        :param lineup: 目标配队
        :param up_ids: 当期UP的代理人ID集合 (校验用)
        """
        ZOperation.__init__(self, ctx, op_name=f"{gt('UP自动配队')} {[a.agent_name for a in lineup]}")
        self.lineup: list[Agent] = lineup
        self.up_ids: set[str] = up_ids
        self.plan: list[tuple[int, Agent]] = []  # (槽位下标, 目标代理人)
        self.plan_idx: int = 0
        self.placed: list[Agent] = []
        self.missed: list[Agent] = []

    def _read_current_member_ids(self) -> list[str | None]:
        """
        OCR三个槽位的代理人名字 转成 agent_id
        :return: 各槽位代理人ID 识别不出为 None
        """
        name_list = [e.value.agent_name for e in AgentEnum]
        agent_list = [e.value for e in AgentEnum]
        current: list[str | None] = []
        for rect in LostVoidComposeUpTeam.NAME_RECTS:
            ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
                image=self.last_screenshot, rect=rect)
            member_id: str | None = None
            for ocr_text in ocr_result_list:
                idx = str_utils.find_best_match_by_difflib(ocr_text.data, name_list, cutoff=0.6)
                if idx is not None and idx >= 0:
                    member_id = agent_list[idx].agent_id
                    break
            current.append(member_id)
        return current

    @operation_node(name='识别当前编队', is_start_node=True)
    def check_current_team(self) -> OperationRoundResult:
        current = self._read_current_member_ids()
        current_names = [i if i is not None else '(空)' for i in current]
        log.info(f'UP自动配队 当前编队: {current_names} 目标: {[a.agent_name for a in self.lineup]}')

        lineup_ids = [a.agent_id for a in self.lineup]
        keep = {i for i in current if i is not None and i in lineup_ids}
        to_place = [a for a in self.lineup if a.agent_id not in keep]
        slots_to_fill = [i for i, c in enumerate(current) if c is None or c not in lineup_ids]

        self.plan = list(zip(slots_to_fill, to_place, strict=False))
        self.plan_idx = 0
        if len(self.plan) == 0:
            return self.round_success(status='无需调整')
        return self.round_success(status='需调整')

    @node_from(from_name='识别当前编队', status='需调整')
    @operation_node(name='调整槽位', node_max_retry_times=3)
    def adjust_slot(self) -> OperationRoundResult:
        if self.plan_idx >= len(self.plan):
            return self.round_success(status='调整完成')

        slot_idx, agent = self.plan[self.plan_idx]

        # 0. 确认在出战画面 (上一步退出面板可能未完成)
        deploy_btn_ocr = self.ctx.ocr_service.get_ocr_result_list(
            image=self.last_screenshot, rect=LostVoidComposeUpTeam.DEPLOY_BTN_RECT)
        if not any('出战' in i.data for i in deploy_btn_ocr):
            self.ctx.controller.click(LostVoidComposeUpTeam.BACK_POS)
            return self.round_retry(status='未在出战画面', wait=1.5)

        # 1. 点击槽位 打开选人面板
        self.ctx.controller.click(Point(LostVoidComposeUpTeam.SLOT_X[slot_idx], LostVoidComposeUpTeam.SLOT_Y))
        time.sleep(1.5)
        self.screenshot()
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            image=self.last_screenshot, rect=LostVoidComposeUpTeam.PICKER_MARK_RECT)
        if not any('潜能' in i.data or '快捷' in i.data for i in ocr_result_list):
            return self.round_retry(status='选人面板未打开', wait=1)

        # 2. 翻页查找目标代理人
        target_mr = None
        prev_page_ids: set[str] | None = None
        for _ in range(LostVoidComposeUpTeam.MAX_SCROLL_PAGES):
            mr_list = match_team_agent_template(
                self.ctx, self.last_screenshot, LostVoidComposeUpTeam.PICKER_RECT, None)
            for mr in mr_list:
                if mr.data.agent_id == agent.agent_id:
                    target_mr = mr
                    break
            if target_mr is not None:
                break
            page_ids = {mr.data.agent_id for mr in mr_list}
            if prev_page_ids is not None and page_ids == prev_page_ids:
                # 翻页没生效 换个拖拽起点再试
                self.ctx.controller.drag_to(start=Point(1150, 800), end=Point(1150, 300))
            else:
                self.ctx.controller.drag_to(start=Point(1450, 750), end=Point(1450, 350))
            prev_page_ids = page_ids
            time.sleep(1)
            self.screenshot()

        if target_mr is None:
            log.warning(f'UP自动配队 选人面板未找到 [{agent.agent_name}] 跳过该位置')
            self.missed.append(agent)
            self.plan_idx += 1
            # 返回箭头退出面板 不确认任何选择
            self.ctx.controller.click(LostVoidComposeUpTeam.BACK_POS)
            time.sleep(1.5)
            return self.round_wait(status='继续调整')

        # 3. 点卡片 → 点丝带确认换入
        self.ctx.controller.click(target_mr.center)
        time.sleep(0.8)
        self.ctx.controller.click(LostVoidComposeUpTeam.RIBBON_POS)
        time.sleep(1.5)
        log.info(f'UP自动配队 槽位{slot_idx + 1} 已换入 [{agent.agent_name}]')
        self.placed.append(agent)
        self.plan_idx += 1
        return self.round_wait(status='继续调整')

    @node_from(from_name='识别当前编队', status='无需调整')
    @node_from(from_name='调整槽位', status='调整完成')
    @operation_node(name='校验编队')
    def verify_team(self) -> OperationRoundResult:
        current = self._read_current_member_ids()
        up_in_team = [i for i in current if i is not None and i in self.up_ids]
        member_names = [i if i is not None else '(空)' for i in current]
        if len(up_in_team) > 0:
            log.info(f'UP自动配队 完成: {member_names} (含{len(up_in_team)}个UP)')
            return self.round_success(status='配队完成')
        log.warning(f'UP自动配队 校验失败: 编队 {member_names} 不含UP')
        return self.round_fail(status='配队校验失败')
