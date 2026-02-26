import time
import re

import cv2
from cv2.typing import MatLike
from typing import Any

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, cal_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.lost_void.context.lost_void_artifact import LostVoidArtifact
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_artifact_pos import LostVoidArtifactPos
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidChooseGear(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        入口处 人物武备和通用武备的选择
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name='迷失之地-武备选择')

    @operation_node(name='选择武备', is_start_node=True)
    def choose_gear(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '文本-详情')
        self.ctx.controller.mouse_move(area.center + Point(0, 100))
        time.sleep(0.1)

        screen_list = []
        for i in range(10):
            screen_list.append(self.screenshot())
            time.sleep(0.2)

        screen_name = self.check_and_update_current_screen(screen_list[0])
        if screen_name != '迷失之地-武备选择':
            # 进入本指令之前 有可能识别错画面
            return self.round_retry(status=f'当前画面 {screen_name}', wait=1)

        choose_new: bool = False
        gear_contours, gear_context = self._find_gears_with_status()
        if not gear_contours:
            return self.round_retry(status='无法识别武备槽位')

        gear_list, has_level_list = self.get_gear_pos_by_click_ocr(gear_contours, gear_context)
        if len(gear_list) == 0:
            return self.round_retry(status='无法识别武备名称')

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

            for j, (level_contour, (level_x1, level_y1, level_x2, level_y2)) in enumerate(remaining_levels):
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
        return result

    @node_from(from_name='选择武备', success=False)
    @node_from(from_name='点击携带')
    @operation_node(name='点击返回')
    def click_back(self) -> OperationRoundResult:
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
