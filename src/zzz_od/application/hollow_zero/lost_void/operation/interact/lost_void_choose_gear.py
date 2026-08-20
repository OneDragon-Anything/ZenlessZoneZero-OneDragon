import re
import time
from typing import Any, ClassVar

import cv2
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.lost_void.context.lost_void_artifact import (
    LostVoidArtifact,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_artifact_pos import (
    LostVoidArtifactPos,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidChooseGear(ZOperation):

    STATUS_REPEATED: ClassVar[str] = '重复武备选择'

    def __init__(self, ctx: ZContext, completed_name_list: list[str] | None = None):
        """
        入口处 人物武备和通用武备的选择
        :param ctx:
        :param completed_name_list: 入口层已完成选择画面的首个武备名列表 跨交互共享
            传入时 若当前画面首个武备命中列表 说明重复交互了同一个NPC 直接返回退出 不再重复整套选择
            完成一次选择后 本画面的首个武备名会补充进列表
            判断信号与存储信号对称(都是画面首个武备名) 避免与其他画面的非首个武备误匹配
        """
        ZOperation.__init__(self, ctx, op_name='迷失之地-武备选择')
        self.completed_name_list: list[str] | None = completed_name_list
        self.recognized_name_list: list[str] = []  # 本次画面识别到的武备名称 首个在携带成功后写入 completed_name_list

    @operation_node(name='选择武备', is_start_node=True)
    def choose_gear(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '文本-详情')
        self.ctx.controller.mouse_move(area.center + Point(0, 100))
        time.sleep(0.1)

        screen_name = self.check_and_update_current_screen(self.last_screenshot)
        if screen_name != '迷失之地-武备选择':
            # 进入本指令之前 有可能识别错画面
            return self.round_retry(status=f'当前画面 {screen_name}', wait=1)

        choose_new: bool = False
        gear_contours, gear_context = self._find_gears_with_status()
        if not gear_contours:
            return self.round_retry(status='无法识别武备槽位')

        # 入口层可能因为交互判定(角度>距离)命中了刚选完武备的NPC 重复打开同一个画面
        # 此时只看首个武备名称 命中已完成列表(各画面首个武备名)则直接退出 避免重复整套点击识别
        # cutoff=0.8 只容忍同名的OCR错字 不同画面即使名称相近也不会误判为重复
        if self.completed_name_list is not None and len(self.completed_name_list) > 0:
            first_name = self._get_first_gear_name(gear_context)
            if (first_name is not None
                    and str_utils.find_best_match_by_difflib(first_name, self.completed_name_list, cutoff=0.8) is not None):
                log.info(f'重复进入已完成选择的武备画面 直接返回 首个武备={first_name}')
                return self.round_success(LostVoidChooseGear.STATUS_REPEATED)

        gear_list, has_level_list = self.get_gear_pos_by_click_ocr(gear_contours, gear_context)
        if len(gear_list) == 0:
            return self.round_retry(status='无法识别武备名称')

        self.recognized_name_list = [i.artifact.display_name for i in gear_list]

        if self.ctx.lost_void.challenge_config.chase_new_mode:
            unlocked_gears: list[LostVoidArtifactPos] = [
                gear_list[i]
                for i in range(min(len(gear_list), len(has_level_list)))
                if not has_level_list[i]
            ]
            if unlocked_gears:
                priority_new = self.ctx.lost_void.get_artifact_by_priority(unlocked_gears, 1)
                target = priority_new[0] if len(priority_new) > 0 else unlocked_gears[0]
                self.ctx.controller.click(target.rect.center)
                time.sleep(0.5)

                # 将选择的武备类型鸣徽添加至第一优先级
                text = target.artifact.category
                self.ctx.lost_void.challenge_config.artifact_priority_in_battle.append(text)
                log.info('【武备追新】添加开局选择的武备属性至第一优先级: [' + text + ']')

                choose_new = True
                log.info(f'【武备追新】当前可选未获取武备 {",".join([i.artifact.display_name for i in unlocked_gears])}')
            else:
                log.info('【武备追新】所有武备都已获取，回退至优先级')

        if not choose_new:
            priority_list: list[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_by_priority(gear_list, 1)
            target = priority_list[0] if len(priority_list) > 0 else gear_list[0]
            self.ctx.controller.click(target.rect.center)
            time.sleep(0.5)

        return self.round_success(wait=0.5)

    def _find_gears_with_status(self) -> tuple[list[tuple[Any, bool]], Any]:
        """
        使用CV流水线查找武备及其状态
        :return: (武备轮廓, 是否有等级)
        """

        # 经常截错图，等1秒
        time.sleep(1)
        gear_context = self.ctx.cv_service.run_pipeline('迷失之地-武备列表检测', self.last_screenshot)
        level_context = self.ctx.cv_service.run_pipeline('迷失之地-武备等级检测', self.last_screenshot)

        if not gear_context.is_success or not gear_context.contours:
            return [], gear_context

        # 1. 预处理：获取所有武备框和等级框的绝对坐标
        gear_rects = gear_context.get_absolute_rect_pairs()
        # 按x1坐标排序武备框
        gear_rects.sort(key=lambda item: item[1][0])  # item[1][0] 是 x1 坐标

        level_rects = []  # [(轮廓, 绝对矩形坐标)]
        if level_context.is_success and level_context.contours:
            level_rects = level_context.get_absolute_rect_pairs()
            # 按x1坐标排序等级框
            level_rects.sort(key=lambda item: item[1][0])  # item[1][0] 是 x1 坐标

        # 按x1坐标排序等级框
        if level_rects:
            level_rects.sort(key=lambda item: item[1][0])  # item[1][0] 是 x1 坐标

        # 2. 生成用于显示的框
        # debug_rects = []
        # 添加所有矩形框
        # for _, (x1, y1, x2, y2) in gear_rects:
        #     debug_rects.append(Rect(x1, y1, x2, y2))
        # for _, (x1, y1, x2, y2) in level_rects:
        #     debug_rects.append(Rect(x1, y1, x2, y2))

        # 3. 匹配武备和等级
        gear_with_status = []
        remaining_levels = list(level_rects)  # 创建一个副本用于迭代和删除

        for i, (gear_contour, (gear_x1, gear_y1, gear_x2, gear_y2)) in enumerate(gear_rects):
            has_level = False

            for j, (_level_contour, (level_x1, level_y1, level_x2, level_y2)) in enumerate(remaining_levels):
                is_overlapping = not (gear_x2 < level_x1 or level_x2 < gear_x1 or
                                      gear_y2 < level_y1 or level_y2 < gear_y1)

                if is_overlapping:
                    log.debug(f"  !!! 发现重叠: 武备[{i}] ({gear_x1},{gear_y1},{gear_x2},{gear_y2}) "
                              f"与 等级[{j}] ({level_x1},{level_y1},{level_x2},{level_y2}) 匹配成功 !!!")
                    has_level = True
                    remaining_levels.pop(j)  # 直接移除匹配的等级
                    break

            gear_with_status.append((gear_contour, has_level))

        # 4. 显示debug信息
        # cv2_utils.show_image(self.last_screenshot, debug_rects, wait=0)
        return gear_with_status, gear_context

    def _get_first_gear_name(self, gear_context: Any) -> str | None:
        """
        点击最左侧的武备 读取其名称 用于入口重复画面的快速判断
        :param gear_context: 武备列表检测的CV流水线结果
        :return: 武备展示名 无法识别时返回None
        """
        gear_abs_pairs = gear_context.get_absolute_rect_pairs()
        if len(gear_abs_pairs) == 0:
            return None
        gear_abs_pairs.sort(key=lambda item: item[1][0])
        x1, y1, x2, y2 = gear_abs_pairs[0][1]
        self.ctx.controller.click(Point((x1 + x2) // 2, (y1 + y2) // 2))
        time.sleep(1)
        _, current_screen = self.ctx.controller.screenshot()

        name_area = self.ctx.screen_loader.get_area('迷失之地-武备选择', '武备名称')
        name_part = cv2_utils.crop_image_only(current_screen, name_area.rect)
        ocr_map = self.ctx.ocr_service.get_ocr_result_map(
            image=name_part,
            crop_first=False,
        )

        token_list: list[tuple[int, str]] = []
        for text, mrl in ocr_map.items():
            token = text.strip()
            if len(token) == 0:
                continue
            for mr in mrl:
                token_list.append((mr.center.x, token))
        token_list.sort(key=lambda item: item[0])
        ocr_text = ''.join([i[1] for i in token_list]).strip()

        art, _ = self._build_artifact_from_ocr_name(ocr_text)
        if art is None:
            return None
        return art.display_name

    def get_gear_pos_by_click_ocr(
            self,
            gear_with_status: list[tuple[Any, bool]],
            gear_context: Any,
    ) -> tuple[list[LostVoidArtifactPos], list[bool]]:
        """
        逐个点击武备，等待1秒截图，裁剪“武备名称”区域，按实际数量纵向拼图后统一OCR。
        按从上到下的OCR结果回填到从左到右的武备槽位。
        """
        if len(gear_with_status) == 0:
            return [], []

        name_area = self.ctx.screen_loader.get_area('迷失之地-武备选择', '武备名称')
        gear_abs_pairs = gear_context.get_absolute_rect_pairs()
        gear_abs_pairs.sort(key=lambda item: item[1][0])
        sorted_status_list = sorted(gear_with_status, key=lambda item: cv2.boundingRect(item[0])[0])

        slice_list: list[MatLike] = []
        click_rect_list: list[Rect] = []
        has_level_list: list[bool] = []

        for i, (_, (x1, y1, x2, y2)) in enumerate(gear_abs_pairs):
            click_pos = Point((x1 + x2) // 2, (y1 + y2) // 2)
            self.ctx.controller.click(click_pos)
            time.sleep(1)
            _, current_screen = self.ctx.controller.screenshot()
            slice_list.append(cv2_utils.crop_image_only(current_screen, name_area.rect))
            click_rect_list.append(Rect(x1, y1, x2, y2))

            if i < len(sorted_status_list):
                has_level_list.append(sorted_status_list[i][1])
            else:
                has_level_list.append(True)

        if len(slice_list) == 0:
            return [], []

        stitched = cv2.vconcat(slice_list)
        ocr_map = self.ctx.ocr_service.get_ocr_result_map(
            image=stitched,
            crop_first=False,
        )
        name_list = self._extract_names_from_stitched_ocr(ocr_map, len(slice_list), slice_list[0].shape[0])

        result_list: list[LostVoidArtifactPos] = []
        total_cnt = min(len(click_rect_list), len(name_list))
        for i in range(total_cnt):
            ocr_text = name_list[i]
            if len(ocr_text) == 0:
                continue

            art, is_primary = self._build_artifact_from_ocr_name(ocr_text)
            if art is None:
                continue

            result_list.append(
                LostVoidArtifactPos(
                    art=art,
                    rect=click_rect_list[i],
                    ocr_text=ocr_text,
                    is_primary_name=is_primary,
                )
            )

        display_text = ','.join([i.artifact.display_name for i in result_list]) if len(result_list) > 0 else '无'
        log.info(f'当前识别武备 {display_text}')
        return result_list, has_level_list

    def _extract_names_from_stitched_ocr(
            self,
            ocr_map: dict[str, MatchResultList],
            slot_cnt: int,
            slot_height: int,
    ) -> list[str]:
        slot_tokens: list[list[tuple[int, str]]] = [[] for _ in range(slot_cnt)]
        for text, mrl in ocr_map.items():
            token = text.strip()
            if len(token) == 0:
                continue
            for mr in mrl:
                slot_idx = mr.center.y // slot_height
                if slot_idx < 0 or slot_idx >= slot_cnt:
                    continue
                slot_tokens[slot_idx].append((mr.center.x, token))

        name_list: list[str] = []
        for token_list in slot_tokens:
            token_list.sort(key=lambda item: item[0])
            text = ''.join([i[1] for i in token_list]).strip()
            name_list.append(text)
        return name_list

    def _build_artifact_from_ocr_name(self, ocr_text: str) -> tuple[LostVoidArtifact | None, bool]:
        normalized = ocr_text.strip().replace('【', '[').replace('】', ']')
        if len(normalized) == 0:
            return None, False

        match = re.search(r'\[(.+?)\](.+)$', normalized)
        if match is not None:
            raw_category = match.group(1).strip()
            raw_name = match.group(2).strip()
            if len(raw_name) == 0:
                return None, False
            # OCR 常见识别错误修复
            raw_category = raw_category.replace('昇常', '异常')
            category = raw_category.split('：', 1)[0].split(':', 1)[0].strip()
            if len(category) == 0:
                category = raw_category
            return LostVoidArtifact(category=category, name=raw_name, level='?', is_gear=True), True

        # 武备选择仅接受 [分类]名称 结构，其他OCR结果直接丢弃。
        return None, False

    @node_from(from_name='选择武备')
    @operation_node(name='点击携带')
    def click_equip(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(screen_name='迷失之地-武备选择', area_name='按钮-携带',
                                                   success_wait=1, retry_wait=1)
        if result.is_success:
            self.ctx.lost_void.priority_updated = False
            log.info("武备选择成功，已设置优先级更新标志")
            # 只记录本画面的首个武备名 与重复判断读取的信号一致
            # 记录全部名称会让其他画面的首个武备有机会与本画面的非首个武备误匹配
            if self.completed_name_list is not None and len(self.recognized_name_list) > 0:
                first_name = self.recognized_name_list[0]
                if first_name not in self.completed_name_list:
                    self.completed_name_list.append(first_name)
        return result

    @node_from(from_name='选择武备', status=STATUS_REPEATED)
    @operation_node(name='重复退出')
    def exit_repeated(self) -> OperationRoundResult:
        """
        重复进入已完成选择的画面时 点击返回退出 并透传重复状态给调用方
        """
        result = self.round_by_find_and_click_area(screen_name='迷失之地-武备选择', area_name='按钮-返回',
                                                   until_not_find_all=[('迷失之地-武备选择', '按钮-返回')],
                                                   success_wait=1, retry_wait=1)
        if result.is_success:
            return self.round_success(LostVoidChooseGear.STATUS_REPEATED)
        return result

    @node_from(from_name='选择武备', success=False)
    @node_from(from_name='点击携带')
    @operation_node(name='点击返回')
    def click_back(self) -> OperationRoundResult:
        # 先尝试点击返回
        result = self.round_by_find_and_click_area(screen_name='迷失之地-武备选择', area_name='按钮-返回',
                                                 success_wait=1, retry_wait=1)
        if result.is_success:
            return result

        # 如果找不到返回按钮，说明有弹窗，先点不再提示，再点确认
        result = self.round_by_find_and_click_area(screen_name='迷失之地-武备选择', area_name='不再提示',
                                                   success_wait=0.5, retry_wait=0.5)
        if not result.is_success:
            # 找不到不再提示，可能弹窗没有出现，直接重试返回
            return self.round_retry(wait=1)

        # 点确认
        self.round_by_find_and_click_area(screen_name='迷失之地-武备选择', area_name='确认',
                                         success_wait=0.5, retry_wait=0.5)

        # 最后再点返回
        return self.round_by_find_and_click_area(screen_name='迷失之地-武备选择', area_name='按钮-返回',
                                                 success_wait=1, retry_wait=1)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.lost_void.init_before_run()
    ctx.run_context.start_running()

    op = LostVoidChooseGear(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
