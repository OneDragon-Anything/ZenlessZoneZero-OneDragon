import time

from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen import screen_utils
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_artifact_pos import LostVoidArtifactPos
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidChooseCommon(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        有详情 有显示选择数量的选择
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name='迷失之地-通用选择')

        self.to_choose_artifact: bool = False  # 需要选择普通藏品
        self.to_choose_gear: bool = False  # 需要选择武备
        self.to_choose_gear_branch: bool = False  # 需要选择武备分支
        self.to_choose_num: int = 1  # 需选数量（本轮总目标）
        self.chosen_idx_list: list[int] = []  # 已经选择过的下标

    @operation_node(name='选择', is_start_node=True)
    def choose_artifact(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '文本-详情')
        self.ctx.controller.mouse_move(area.center + Point(0, 100))
        time.sleep(0.1)

        art_list, chosen_list = self.get_artifact_pos(self.last_screenshot)
        if self.to_choose_num > 0:
            log.info(
                f'选择概览 需选数量={self.to_choose_num} 已选数量={len(chosen_list)} 可选数量={len(art_list)}'
            )
            if len(chosen_list) >= self.to_choose_num:
                return self.click_confirm()

            # 四层流程：NEW -> 同流派 -> 优先级 -> 兜底
            # 每层都按“还需选择数量”补齐，补满即确认。
            if len(art_list) > 0 and self.select_by_layers(self.to_choose_num):
                return self.click_confirm()

            # 兜底：无条件点击可见文本块后直接确认，避免卡死。
            self.try_choose_by_click_name_text(target_num=self.to_choose_num)

        return self.click_confirm()

    def select_by_layers(self, target_num: int) -> bool:
        layer_order = ['NEW', '同流派', '优先级']

        for layer in layer_order:
            _, current_screen = self.ctx.controller.screenshot()
            can_choose_list, chosen_list = self.get_artifact_pos(current_screen)
            chosen_cnt = len(chosen_list)
            if chosen_cnt >= target_num:
                return True

            need_cnt = target_num
            remain_cnt = target_num - chosen_cnt
            candidate_list: list[LostVoidArtifactPos] = []
            available_list = [i for i in can_choose_list if i.can_choose]

            if len(available_list) == 0:
                continue

            if layer == 'NEW':
                if self.ctx.lost_void.challenge_config.artifact_priority_new:
                    candidate_list = self.sort_candidates([
                        i for i in available_list if i.is_new
                    ])[:remain_cnt]
            elif layer == '同流派':
                candidate_list = self.sort_candidates([
                    i for i in available_list if i.has_same_style
                ])[:remain_cnt]
            elif layer == '优先级':
                if self.has_priority_rule():
                    candidate_list = self.ctx.lost_void.get_artifact_by_priority(
                        available_list, remain_cnt,
                        consider_priority_1=True,
                        consider_priority_2=True,
                        consider_not_in_priority=False,
                        consider_priority_new=False,
                    )

            if len(candidate_list) == 0:
                continue

            display_text = ', '.join([i.artifact.display_name for i in candidate_list])
            log.info(
                f'分层选择 [{layer}] 需选数量={need_cnt} 已选数量={chosen_cnt} 可选数量={len(available_list)} '
                f'还需选择={remain_cnt} 本层待点={len(candidate_list)} {display_text}'
            )
            for artifact_pos in candidate_list:
                self.ctx.controller.click(artifact_pos.rect.center)
                time.sleep(0.3)
                # 每次点击后立即复核，达标就立刻退出，避免“已满足仍继续点下一层”
                if self._reached_target_choose_num(target_num):
                    return True

        _, final_screen = self.ctx.controller.screenshot()
        _, final_chosen_list = self.get_artifact_pos(final_screen)
        return len(final_chosen_list) >= target_num

    def _reached_target_choose_num(self, target_num: int) -> bool:
        for _ in range(3):
            _, latest_screen = self.ctx.controller.screenshot()
            _, chosen_list = self.get_artifact_pos(latest_screen)
            if len(chosen_list) >= target_num:
                return True
            time.sleep(0.2)
        return False

    def has_priority_rule(self) -> bool:
        cfg = self.ctx.lost_void.challenge_config
        if cfg is None:
            return False
        if len(self.ctx.lost_void.dynamic_priority_list) > 0:
            return True
        if len(cfg.artifact_priority) > 0:
            return True
        if len(cfg.artifact_priority_2) > 0:
            return True
        return False

    def sort_candidates(self, candidate_list: list[LostVoidArtifactPos]) -> list[LostVoidArtifactPos]:
        if len(candidate_list) <= 1:
            return candidate_list

        level_rank = {'S': 0, 'A': 1, 'B': 2}
        return sorted(
            candidate_list,
            key=lambda i: (
                0 if i.is_primary_name else 1,
                level_rank.get(i.artifact.level, 9),
                i.rect.center.x,
                i.rect.center.y,
            )
        )

    def click_confirm(self) -> OperationRoundResult:
        _, latest_screen = self.ctx.controller.screenshot()
        result = self.round_by_find_and_click_area(
            screen=latest_screen,
            screen_name='迷失之地-通用选择',
            area_name='按钮-确定',
            success_wait=1,
            retry_wait=1
        )
        if result.is_success:
            self.ctx.lost_void.priority_updated = False
            log.info("藏品选择成功，已设置优先级更新标志")
            return self.round_success(result.status)
        else:
            return self.round_retry(result.status, wait=1)

    def try_choose_by_click_name_text(self, target_num: int | None = None) -> bool:
        """
        兜底选择：
        1. 获取“区域-藏品名称”的OCR文本块
        2. 第一轮逐个点击，每次点击后检查“有同流派武备”
        3. 若第一轮未命中，第二轮逐个点击，每次点击后检查“已选择”
        """
        if target_num is not None:
            return self.try_fill_by_can_choose(target_num)

        _, current_screen = self.ctx.controller.screenshot()
        click_target_list = self.get_name_text_click_target_list(current_screen)
        if len(click_target_list) == 0:
            log.info('无法识别藏品 兜底点击未识别到藏品名称文本块')
            return False

        clicked_any = False

        log.info(f'无法识别藏品 兜底第一轮 文本块数量={len(click_target_list)}')
        for target_idx, target in enumerate(click_target_list):
            self.ctx.controller.click(target.center)
            clicked_any = True
            time.sleep(0.3)

            _, clicked_screen = self.ctx.controller.screenshot()
            if self.has_same_style_selected(clicked_screen):
                log.info(f'兜底点击藏品成功 第一轮命中同流派武备 第{target_idx + 1}/{len(click_target_list)}个')
                return True

        log.info(f'无法识别藏品 兜底第二轮 文本块数量={len(click_target_list)}')
        for target_idx, target in enumerate(click_target_list):
            self.ctx.controller.click(target.center)
            clicked_any = True
            time.sleep(0.3)

            _, clicked_screen = self.ctx.controller.screenshot()
            if self.has_selected(clicked_screen):
                log.info(f'兜底点击藏品成功 第二轮命中已选择 第{target_idx + 1}/{len(click_target_list)}个')
                return True

        _, final_screen = self.ctx.controller.screenshot()
        if self.has_selected(final_screen):
            log.info('兜底点击藏品成功 第二轮结束后检测到已选择')
            return True

        log.info('无法识别藏品 兜底两轮结束仍未检测到目标标志')
        return False

    def try_fill_by_can_choose(self, target_num: int) -> bool:
        """
        选择数量场景下的兜底：
        仅点击当前可选(can_choose)候选，避免点到已选导致覆盖。
        每次点击后都重新截图和重算，直到达到需选数量或候选耗尽。
        """
        tried_center_list: list[Point] = []

        for _ in range(12):
            _, current_screen = self.ctx.controller.screenshot()
            can_choose_list, chosen_list = self.get_artifact_pos(current_screen)
            if len(chosen_list) >= target_num:
                log.info('兜底点击藏品成功 通过can_choose达到目标数量')
                return True

            candidate_list = self.sort_candidates([i for i in can_choose_list if i.can_choose])
            target = None
            for candidate in candidate_list:
                duplicated = False
                for tried_center in tried_center_list:
                    if abs(candidate.rect.center.x - tried_center.x) < 40 and abs(candidate.rect.center.y - tried_center.y) < 40:
                        duplicated = True
                        break
                if not duplicated:
                    target = candidate
                    break

            if target is None:
                break

            self.ctx.controller.click(target.rect.center)
            tried_center_list.append(target.rect.center)
            time.sleep(0.3)

        _, final_screen = self.ctx.controller.screenshot()
        _, chosen_after = self.get_artifact_pos(final_screen)
        if len(chosen_after) >= target_num:
            log.info('兜底点击藏品成功 can_choose结束后达到目标数量')
            return True

        log.info('兜底点击藏品结束 can_choose候选耗尽仍未达到目标数量')
        return len(tried_center_list) > 0

    def get_name_text_click_target_list(self, screen: MatLike) -> list[MatchResult]:
        area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '区域-藏品名称')
        ocr_result_map = self.ctx.ocr_service.get_ocr_result_map(
            image=screen,
            rect=area.rect,
            crop_first=True
        )

        all_result_list: list[MatchResult] = []
        for text, mrl in ocr_result_map.items():
            if len(text.strip()) == 0:
                continue
            for mr in mrl:
                all_result_list.append(mr)

        all_result_list.sort(key=lambda i: (i.center.x, i.center.y))

        # 同一卡片名称可能被OCR拆成多个文本块，按X坐标做一次聚合，避免重复点同一张
        result_list: list[MatchResult] = []
        for mr in all_result_list:
            duplicated = False
            for existed in result_list:
                if abs(existed.center.x - mr.center.x) < 90:
                    duplicated = True
                    break
            if not duplicated:
                result_list.append(mr)

        return result_list

    def has_same_style_selected(self, screen: MatLike) -> bool:
        selected_area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '区域-藏品已选择')
        return screen_utils.find_by_ocr(
            self.ctx,
            screen,
            target_cn='有同流派武备',
            area=selected_area
        )

    def has_selected(self, screen: MatLike) -> bool:
        selected_area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '区域-藏品已选择')
        return screen_utils.find_by_ocr(
            self.ctx,
            screen,
            target_cn='已选择',
            area=selected_area
        )

    def get_artifact_pos(self, screen: MatLike) -> tuple[list[LostVoidArtifactPos], list[LostVoidArtifactPos]]:
        """
        获取藏品的位置
        @param screen: 游戏画面
        @return: tuple[识别到的武备的位置, 已经选择的位置]
        """
        self.check_choose_title(screen)
        if self.to_choose_num == 0:  # 不需要选择的
            return [], []

        artifact_pos_list: list[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_pos(
            screen,
            to_choose_gear_branch=self.to_choose_gear_branch,
            screen_name='迷失之地-通用选择'
        )

        can_choose_list = [i for i in artifact_pos_list if i.can_choose]
        can_choose_text = ', '.join([i.artifact.display_name for i in can_choose_list]) if len(can_choose_list) > 0 else '无'
        log.info(f'当前可选藏品 数量={len(can_choose_list)} {can_choose_text}')

        chosen_list = [i for i in artifact_pos_list if i.chosen]
        chosen_text = ', '.join([i.artifact.display_name for i in chosen_list]) if len(chosen_list) > 0 else '无'
        log.info(f'当前已选藏品 数量={len(chosen_list)} {chosen_text}')

        return can_choose_list, chosen_list

    def check_choose_title(self, screen: MatLike) -> None:
        """
        识别标题 判断要选择的类型和数量
        :param screen: 游戏画面
        """
        self.to_choose_artifact = False
        self.to_choose_gear = False
        self.to_choose_gear_branch = False
        self.to_choose_num = 0
        area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '区域-标题')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result = self.ctx.ocr.run_ocr(part)

        title_words = [w.strip() for w in ocr_result.keys() if len(w.strip()) > 0]
        title_text = ''.join(title_words)
        normalized_text = (
            title_text.replace('（', '(').replace('）', ')')
            .replace(' ', '').replace('　', '')
        )

        def apply_rule(rule_id: str) -> None:
            if rule_id == 'GEAR_GAIN':
                self.to_choose_gear = True
                self.to_choose_num = 0
            elif rule_id == 'GEAR_UPGRADE':
                self.to_choose_gear = True
                self.to_choose_num = 0
            elif rule_id == 'ARTIFACT_GAIN':
                self.to_choose_artifact = True
                self.to_choose_num = 0
            elif rule_id == 'GEAR_BRANCH':
                self.to_choose_gear = True
                self.to_choose_gear_branch = True
                self.to_choose_num = 1
            elif rule_id == 'CHOOSE_2':
                self.to_choose_artifact = True
                self.to_choose_num = 2
            elif rule_id == 'CHOOSE_1_GEAR':
                self.to_choose_gear = True
                self.to_choose_num = 1
            elif rule_id == 'CHOOSE_1_CARD':
                self.to_choose_artifact = True
                self.to_choose_num = 1
            elif rule_id == 'CHOOSE_1':
                # 1.5 更新后 武备和普通鸣徽都可能是这个标题
                self.to_choose_num = 1

        # 第一轮：精准匹配（避免“1项”被模糊吸附到“2项”）
        exact_rule_list: list[tuple[str, list[str]]] = [
            ('GEAR_GAIN', ['获得武备']),
            ('GEAR_UPGRADE', ['武备已升级']),
            ('ARTIFACT_GAIN', ['获得战利品']),
            ('GEAR_BRANCH', ['请选择战术棱镜方案强化的方向']),
            # 兼容 2枚/两枚 变体
            ('CHOOSE_2', ['请选择2项', '请选择2枚鸣徽', '请选择两枚鸣徽']),
            ('CHOOSE_1_GEAR', ['请选择1个武备']),
            ('CHOOSE_1_CARD', ['请选择1张卡牌']),
            # 你指出的文案修正：1枚鸣徽
            ('CHOOSE_1', ['请选择1项', '请选择1枚鸣徽', '请选择一枚鸣徽']),
        ]

        matched_rule = None
        for rule_id, phrase_list in exact_rule_list:
            if any(phrase in normalized_text for phrase in phrase_list):
                apply_rule(rule_id)
                matched_rule = f'exact:{rule_id}'
                break

        # 第二轮：模糊匹配兜底（只有第一轮没命中才使用）
        if matched_rule is None and len(title_words) > 0:
            fuzzy_target_list = [
                '获得武备',
                '武备已升级',
                '获得战利品',
                '请选择战术棱镜方案强化的方向',
                '请选择2项',
                '请选择2枚鸣徽',
                '请选择两枚鸣徽',
                '请选择1个武备',
                '请选择1张卡牌',
                '请选择1项',
                '请选择1枚鸣徽',
                '请选择一枚鸣徽',
            ]
            target_2_rule = {
                '获得武备': 'GEAR_GAIN',
                '武备已升级': 'GEAR_UPGRADE',
                '获得战利品': 'ARTIFACT_GAIN',
                '请选择战术棱镜方案强化的方向': 'GEAR_BRANCH',
                '请选择2项': 'CHOOSE_2',
                '请选择2枚鸣徽': 'CHOOSE_2',
                '请选择两枚鸣徽': 'CHOOSE_2',
                '请选择1个武备': 'CHOOSE_1_GEAR',
                '请选择1张卡牌': 'CHOOSE_1_CARD',
                '请选择1项': 'CHOOSE_1',
                '请选择1枚鸣徽': 'CHOOSE_1',
                '请选择一枚鸣徽': 'CHOOSE_1',
            }
            for ocr_word in title_words:
                idx = str_utils.find_best_match_by_difflib(
                    ocr_word,
                    fuzzy_target_list,
                    cutoff=0.9,
                )
                if idx is None:
                    continue
                target_phrase = fuzzy_target_list[idx]
                apply_rule(target_2_rule[target_phrase])
                matched_rule = f'fuzzy:{target_2_rule[target_phrase]}:{ocr_word}->{target_phrase}'
                break

        # 兜底：标题仍未命中时，仍可用下方GEAR标识判断为武备单选
        if matched_rule is None:
            result = self.round_by_find_area(screen, '迷失之地-通用选择', '区域-武备标识')
            if result.is_success:
                self.to_choose_gear = True
                self.to_choose_num = 1
                matched_rule = 'fallback:gear_marker'
            else:
                matched_rule = 'fallback:none'

        log.info(
            f'标题判定 OCR={title_words if len(title_words) > 0 else ["无"]} '
            f'规则={matched_rule} '
            f'需选数量={self.to_choose_num} 选择藏品={self.to_choose_artifact} '
            f'选择武备={self.to_choose_gear} 武备分支={self.to_choose_gear_branch}'
        )

def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.init_ocr()
    ctx.lost_void.init_before_run()
    ctx.run_context.start_running()

    op = LostVoidChooseCommon(ctx)
    op.execute()


def __get_get_artifact_pos():
    ctx = ZContext()
    ctx.init()
    ctx.init_ocr()
    ctx.lost_void.init_before_run()

    op = LostVoidChooseCommon(ctx)
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('20251112133547')
    art_list, chosen_list = op.get_artifact_pos(screen)
    print(len(art_list), len(chosen_list))
    cv2_utils.show_image(screen, chosen_list[0] if len(chosen_list) > 0 else None, wait=0)
    import cv2
    cv2.destroyAllWindows()


if __name__ == '__main__':
    __debug()
