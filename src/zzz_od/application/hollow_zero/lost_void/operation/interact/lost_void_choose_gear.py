import time

import cv2
from cv2.typing import MatLike
from typing import List

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

        gear_list = self.get_gear_pos(screen_list)
        if len(gear_list) == 0:
            # 识别耗时比较长 这里返回就不等待了
            return self.round_retry(status='无法识别武备')

        priority_list: List[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_by_priority(gear_list, 1)
        for art in priority_list:
            self.ctx.controller.click(art.rect.center)
            time.sleep(0.5)

        return self.round_success(wait=0.5)

    def get_gear_pos(self, screen_list: List[MatLike], only_no_level: bool = False) -> List[LostVoidArtifactPos]:
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

            if only_no_level:
                level_pos_list = self.get_level_pos(screen)
            else:
                level_pos_list = []

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

                if only_no_level:
                    with_level: bool = False
                    gear_width = mr.w
                    gear_center = mr.center
                    for level in level_pos_list:
                        level_center = level.center
                        if level_center.x < gear_center.x and abs(level_center.x - gear_center.x) < gear_width * 1.5:
                            with_level = True
                            break

                    if with_level:
                        continue

                if not existed:
                    result_list.append(LostVoidArtifactPos(gear, mr.rect))

        display_text = ','.join([i.artifact.display_name for i in result_list]) if len(result_list) > 0 else '无'
        log.info(f'当前识别藏品 {display_text}')

        return result_list

    def get_level_pos(self, screen: MatLike) -> List[MatchResult]:
        """
        获取等级的位置
        :param screen: 游戏画面
        :return:
        """
        area = self.ctx.screen_loader.get_area('迷失之地-武备选择', '等级列表')
        part = cv2_utils.crop_image_only(screen, area.rect)
        mask = cv2.inRange(part, (150, 150, 150), (255, 255, 255))
        mask = cv2_utils.dilate(mask, 2)
        to_ocr = cv2.bitwise_and(part, part, mask=mask)
        # cv2_utils.show_image(to_ocr, wait=0)

        level_result_list: List[MatchResult] = []

        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)
        for ocr_result, mrl in ocr_result_map.items():
            digit = str_utils.get_positive_digits(ocr_result)
            if digit is None:
                continue
            for mr in mrl:
                mr.add_offset(area.left_top)
                level_result_list.append(mr)

        return level_result_list

    @node_from(from_name='选择武备')
    @operation_node(name='点击携带')
    def click_equip(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='迷失之地-武备选择', area_name='按钮-携带',
                                                 success_wait=1, retry_wait=1)

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