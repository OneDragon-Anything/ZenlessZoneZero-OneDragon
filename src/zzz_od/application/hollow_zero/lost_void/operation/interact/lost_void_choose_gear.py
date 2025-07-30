import time

import cv2
from cv2.typing import MatLike
from typing import List, Tuple

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, cal_utils, str_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.lost_void.context.lost_void_artifact import LostVoidArtifact
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_artifact_pos import LostVoidArtifactPos
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidChooseGear(ZOperation):

    def __init__(self, ctx: ZContext, chase_new_mode: bool = False):
        """
        入口处 人物武备和通用武备的选择
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name='迷失之地-武备选择')
        self.chase_new_mode = chase_new_mode

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

        if self.chase_new_mode:
            gear_contours, gear_context = self._find_gears_with_status()

            if not gear_contours:
                return self.round_retry(status='【武备追新】无法识别任何武备')
            
            unlocked_gears = [g for g, has_level in gear_contours if not has_level]

            if unlocked_gears:
                target_contour = unlocked_gears[0]
                log.debug("【武备追新】找到一个未获取的武备，准备点击")
            else:
                target_contour = gear_contours[0][0]
                log.debug("【武备追新】所有武备都已获取，选择第一个作为保底")

            M = cv2.moments(target_contour)
            center_x = int(M["m10"] / M["m00"])
            center_y = int(M["m01"] / M["m00"])
            offset_x, offset_y = gear_context.crop_offset
            click_pos = Point(center_x + offset_x, center_y + offset_y)
            log.debug(f"【武备追新】 点击目标坐标: {click_pos} (相对: ({center_x}, {center_y}), 偏移: {gear_context.crop_offset})")
            self.ctx.controller.click(click_pos)
            time.sleep(0.5)

        else:
            gear_list = self.get_gear_pos_by_feature(screen_list)
            if len(gear_list) == 0:
                return self.round_retry(status='无法识别武备')

            priority_list: List[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_by_priority(gear_list, 1)
            if priority_list:
                self.ctx.controller.click(priority_list[0].rect.center)
                time.sleep(0.5)

        return self.round_success(wait=0.5)

    def _find_gears_with_status(self) -> Tuple[List[tuple[any, bool]], any]:
        """
        使用CV流水线查找武备及其状态
        :return: (武备轮廓, 是否有等级)
        """
        gear_context = self.ctx.cv_service.run_pipeline('迷失之地-武备列表检测', self.last_screenshot)
        level_context = self.ctx.cv_service.run_pipeline('迷失之地-武备等级检测', self.last_screenshot)

        if not gear_context.is_success or not gear_context.contours:
            return [], gear_context

        gear_with_status = []
        for gear_contour in gear_context.contours:
            gear_rect = cv2.boundingRect(gear_contour)
            has_level = False
            if level_context.is_success and level_context.contours:
                for level_contour in level_context.contours:
                    level_M = cv2.moments(level_contour)
                    if level_M["m00"] == 0: continue
                    level_center_x = int(level_M["m10"] / level_M["m00"])
                    level_center_y = int(level_M["m01"] / level_M["m00"])

                    # 简单的空间关系判断：等级中心点在武备矩形的右侧附近
                    if (gear_rect[0] < level_center_x < gear_rect[0] + gear_rect[2] * 1.5 and
                            gear_rect[1] < level_center_y < gear_rect[1] + gear_rect[3]):
                        has_level = True
                        break
            gear_with_status.append((gear_contour, has_level))

        return gear_with_status, gear_context

    def get_gear_pos_by_feature(self, screen_list: List[MatLike]) -> List[LostVoidArtifactPos]:
        """
        获取武备的位置
        @param screen_list: 游戏截图列表 由于武备的图像是动态的 需要多张识别后合并结果
        @param only_no_level: 只获取无等级的
        @return: 识别到的武备的位置
        """
        area = self.ctx.screen_loader.get_area('迷失之地-武备选择', '武备列表')
        to_check_list: List[LostVoidArtifact] = [
            i
            for i in self.ctx.lost_void.all_artifact_list
            if i.template_id is not None
        ]

        result_list: List[LostVoidArtifactPos] = []

        for screen in screen_list:
            part = cv2_utils.crop_image_only(screen, area.rect)

            source_kps, source_desc = cv2_utils.feature_detect_and_compute(part)
            for gear in to_check_list:
                template = self.ctx.template_loader.get_template('lost_void', gear.template_id)
                if template is None:
                    continue

                template_kps, template_desc = template.features
                mr = cv2_utils.feature_match_for_one(
                    source_kps, source_desc,
                    template_kps, template_desc,
                    template_width=template.raw.shape[1], template_height=template.raw.shape[0],
                    knn_distance_percent=0.5
                )

                if mr is None:
                    continue

                mr.add_offset(area.left_top)
                mr.data = gear

                existed = False
                for existed_result in result_list:
                    if cal_utils.distance_between(existed_result.rect.center, mr.center) < existed_result.rect.width // 2:
                        existed = True
                        break

                if not existed:
                    result_list.append(LostVoidArtifactPos(gear, mr.rect))

        display_text = ','.join([i.artifact.display_name for i in result_list]) if len(result_list) > 0 else '无'
        log.info(f'当前识别藏品 {display_text}')

        return result_list

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
    ctx.start_running()

    op = LostVoidChooseGear(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()