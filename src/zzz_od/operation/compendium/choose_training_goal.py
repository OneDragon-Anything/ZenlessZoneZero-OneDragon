import re
from dataclasses import dataclass
from typing import ClassVar

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.charge_plan.charge_plan_config import (
    CardNumEnum,
    ChargePlanItem,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.compendium.compendium_choose_category import (
    CompendiumChooseCategory,
)
from zzz_od.operation.zzz_operation import ZOperation


@dataclass
class TrainingGoalSelection:
    """特训目标统一页选出的一次实际副本。"""

    category_name: str
    required_charge: int
    card_num: str = CardNumEnum.DEFAULT.value.value
    use_burnout_mode: bool = False
    go_point: Point | None = None

    def to_plan(self, source: ChargePlanItem) -> ChargePlanItem:
        """继承用户配置，生成只运行一次的实际副本计划。"""
        return ChargePlanItem(
            tab_name='训练',
            category_name=self.category_name,
            mission_type_name='代理人方案培养',
            mission_name=None,
            level=source.level,
            auto_battle_config=source.auto_battle_config,
            run_times=0,
            plan_times=1,
            card_num=self.card_num,
            predefined_team_idx=source.predefined_team_idx,
            notorious_hunt_buff_num=source.notorious_hunt_buff_num,
            plan_id=source.plan_id,
            use_burnout_mode=self.use_burnout_mode,
        )


def build_training_goal_selection(
    section_name: str,
    charge_text: str,
    available_charge: int,
    go_point: Point | None = None,
) -> TrainingGoalSelection | None:
    """按分区和游戏给出的电量范围确定本次副本与实际消耗。"""
    normalized_charge = charge_text.strip()
    for separator in ('—', '–', '～', '~'):
        normalized_charge = normalized_charge.replace(separator, '-')
    match = re.fullmatch(r'(\d+)(?:-(\d+))?', normalized_charge)
    if match is None:
        return None

    minimum_charge = int(match.group(1))
    maximum_charge = int(match.group(2) or match.group(1))
    is_drive_disc = str_utils.find_by_lcs(
        gt('驱动盘', 'game'), section_name, percent=0.5
    )

    if is_drive_disc:
        return TrainingGoalSelection('区域巡防', 60, go_point=go_point)

    if minimum_charge == 20:
        required_cards = max(1, min(5, maximum_charge // 20))
        affordable_cards = max(1, min(required_cards, available_charge // 20))
        return TrainingGoalSelection(
            '实战模拟室',
            affordable_cards * 20,
            card_num=str(affordable_cards),
            go_point=go_point,
        )

    if minimum_charge == 40:
        use_burnout_mode = maximum_charge >= 80 and available_charge >= 80
        return TrainingGoalSelection(
            '专业挑战室',
            80 if use_burnout_mode else 40,
            use_burnout_mode=use_burnout_mode,
            go_point=go_point,
        )

    if minimum_charge == 60:
        return TrainingGoalSelection('恶名狩猎', 60, go_point=go_point)

    return None


class ChooseTrainingGoal(ZOperation):
    """从快捷手册“特训目标”统一页选择优先级最高的一项并传送。"""

    STATUS_NO_TARGET: ClassVar[str] = '未设置特训目标或没有可刷取目标'

    def __init__(self, ctx: ZContext, available_charge: int) -> None:
        """初始化统一页选择操作和本次可用电量。"""
        ZOperation.__init__(self, ctx, op_name='快捷手册 选择特训目标')
        self.available_charge: int = available_charge
        self.selection: TrainingGoalSelection | None = None
        self.missing_times: int = 0
        self.scroll_times: int = 0

    @operation_node(name='重置列表位置', is_start_node=True)
    def reset_list_position(self) -> OperationRoundResult:
        """切走再切回，使游戏把动态列表稳定重置到第一项。"""
        self.missing_times = 0
        self.scroll_times = 0
        normal_result = CompendiumChooseCategory(self.ctx, '实战模拟室').execute()
        if not normal_result.success:
            return self.round_by_op_result(normal_result)
        target_result = CompendiumChooseCategory(self.ctx, '特训目标').execute()
        # 分类文字先出现，右侧动态材料列表随后才完成刷新。实机最慢约 4 秒，
        # 子操作已等待 1 秒，这里再留 3 秒，避免对过渡帧连续 OCR。
        return self.round_by_op_result(target_result, wait=3)

    @node_from(from_name='重置列表位置')
    @operation_node(name='识别并选择目标', node_max_retry_times=3)
    def choose_goal(self) -> OperationRoundResult:
        """选择当前最高优先级目标，必要时下滚查找推荐驱动盘。"""
        selection = self.analyze_goal(self.last_screenshot)
        if selection is None or selection.go_point is None:
            self.missing_times += 1
            if self.missing_times == 1:
                return self.round_retry(self.STATUS_NO_TARGET, wait=1)
            if self.scroll_times < 2:
                self.ctx.controller.drag_to(
                    start=Point(1050, 850),
                    end=Point(1050, 550),
                )
                self.scroll_times += 1
                return self.round_retry('向下查找推荐驱动盘', wait=1)
            return self.round_retry(self.STATUS_NO_TARGET, wait=1)

        self.selection = selection
        if not self.ctx.controller.click(selection.go_point):
            return self.round_retry('点击特训目标失败', wait=1)
        return self.round_success(wait=1)

    @node_from(from_name='识别并选择目标')
    @operation_node(name='确认传送')
    def confirm(self) -> OperationRoundResult:
        """确认从统一页传送到本次实际副本。"""
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '快捷手册',
            '传送确认',
            success_wait=5,
            retry_wait=1,
        )

    def analyze_goal(self, screen: MatLike) -> TrainingGoalSelection | None:
        """识别当前视口第一项；首屏无目标时由节点向下查找驱动盘。"""
        content_area = self.ctx.screen_loader.get_area('快捷手册', '特训目标-内容列表')
        go_area = self.ctx.screen_loader.get_area('快捷手册', '前往列表')
        ocr_map: dict[str, MatchResultList] = self.ctx.ocr.run_ocr(screen)

        go_points: list[Point] = []
        for text, match_list in ocr_map.items():
            if not str_utils.find_by_lcs(gt('前往', 'game'), text, percent=0.5):
                continue
            for result in match_list:
                center = result.center
                if (
                    go_area.rect.x1 <= center.x <= go_area.rect.x2
                    and go_area.rect.y1 <= center.y <= go_area.rect.y2
                ):
                    go_points.append(center)
        if not go_points:
            return None
        go_point = min(go_points, key=lambda point: point.y)

        section_names = ['代理人', '音擎', '技能', '核心技', '驱动盘']
        section_candidates: list[tuple[int, str]] = []
        charge_candidates: list[tuple[int, str]] = []
        for text, match_list in ocr_map.items():
            for result in match_list:
                center = result.center
                if not (
                    content_area.rect.x1 <= center.x <= content_area.rect.x2
                    and content_area.rect.y1 <= center.y <= content_area.rect.y2
                ):
                    continue

                if center.y < go_point.y:
                    for section_name in section_names:
                        if str_utils.find_by_lcs(
                            gt(section_name, 'game'), text, percent=0.6
                        ):
                            section_candidates.append((center.y, text))
                            break

                normalized_text = text.strip()
                for separator in ('—', '–', '～', '~'):
                    normalized_text = normalized_text.replace(separator, '-')
                if (
                    center.x >= 1350
                    and abs(center.y - go_point.y) <= 130
                    and re.fullmatch(r'\d+(?:-\d+)?', normalized_text)
                ):
                    charge_candidates.append((abs(center.y - go_point.y), normalized_text))

        if not charge_candidates:
            return None
        section_name = max(section_candidates, default=(0, ''), key=lambda item: item[0])[1]
        charge_text = min(charge_candidates, key=lambda item: item[0])[1]
        return build_training_goal_selection(
            section_name=section_name,
            charge_text=charge_text,
            available_charge=self.available_charge,
            go_point=go_point,
        )
