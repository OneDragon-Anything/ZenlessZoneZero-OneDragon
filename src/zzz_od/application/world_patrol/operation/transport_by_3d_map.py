import random
import time

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolArea
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.zzz_operation import ZOperation


class TransportBy3dMap(ZOperation):

    def __init__(
            self,
            ctx: ZContext,
            area: WorldPatrolArea,
            tp_name: str,
    ):
        """
        使用3D地图 传送指定的传送点
        """
        ZOperation.__init__(self, ctx, op_name=gt('传送'))

        self.target_area: WorldPatrolArea = area
        self.target_tp_name: str = tp_name

    @operation_node(name='初始回到大世界', is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        current_screen = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['3D地图'])
        if current_screen == '3D地图':
            return self.round_success(status=current_screen)
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='初始回到大世界')
    @operation_node(name='打开地图')
    def open_map(self) -> OperationRoundResult:
        current_screen = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['3D地图'])
        if current_screen == '3D地图':
            return self.round_success()

        mini_map = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)
        if mini_map.play_mask_found:
            self.round_by_click_area('大世界', '小地图')
            return self.round_wait(status='点击打开地图', wait=1)
        else:
            return self.round_retry(status='未发现地图', wait=1)

    @node_from(from_name='初始回到大世界', status='3D地图')
    @node_from(from_name='打开地图')
    @operation_node(name='选择区域')
    def choose_area(self) -> OperationRoundResult:
        if self.target_area.parent_area is None:
            target_area_name = self.target_area.area_name
        else:
            target_area_name = self.target_area.parent_area.area_name

        area = self.ctx.screen_loader.get_area('3D地图', '区域-区域列表')
        ocr_result_map = self.ctx.ocr_service.get_ocr_result_map(self.last_screenshot, rect=area.rect)

        ocr_word_list = list(ocr_result_map.keys())
        target_word_idx = str_utils.find_best_match_by_difflib(gt(target_area_name), ocr_word_list)
        if target_word_idx is not None and target_word_idx >= 0:
            mrl = ocr_result_map.get(ocr_word_list[target_word_idx])
            if mrl.max is not None:
                self.ctx.controller.click(mrl.max.center)
                return self.round_success(wait=1)

        order_cn_list = [i.area_name for i in self.ctx.world_patrol_service.area_list]
        is_target_after: bool = str_utils.is_target_after_ocr_list(
            target_cn=target_area_name,
            order_cn_list=order_cn_list,
            ocr_result_list=ocr_word_list,
        )

        start_point = area.center
        end_point = start_point + Point(0, 400 * (-1 if is_target_after else 1))
        self.ctx.controller.drag_to(start=start_point, end=end_point)
        return self.round_retry(wait=1)

    @node_from(from_name='选择区域')
    @operation_node(name='选择子区域', node_max_retry_times=6)
    def choose_sub_area(self) -> OperationRoundResult:
        if self.target_area.parent_area is None:
            return self.round_success(status='无需选择')

        self.round_by_click_area('3D地图', '按钮-当前子区域',
                                 success_wait=1)

        self.screenshot()
        return self.round_by_ocr_and_click(
            screen=self.last_screenshot,
            target_cn=self.target_area.area_name,
            area=self.ctx.screen_loader.get_area('3D地图', '区域-子区域列表'),
            success_wait=1,
            retry_wait=1,
        )

    @node_from(from_name='选择子区域')
    @operation_node(name='打开筛选')
    def open_filter(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '3D地图', '标题-标识点筛选')
        if result.is_success:
            return self.round_success(status=result.status)

        self.round_by_click_area('3D地图', '按钮-筛选')
        return self.round_retry(wait=1)

    @node_from(from_name='打开筛选')
    @operation_node(name='筛选传送点')
    def choose_filter(self) -> OperationRoundResult:
        if self.target_area.is_hollow:
            target_word = '裂隙信标'
        else:
            target_word = '传送'

        return self.round_by_ocr_and_click(
            screen=self.last_screenshot,
            target_cn=target_word,
            area=self.ctx.screen_loader.get_area('3D地图', '区域-筛选选项'),
            success_wait=1,
            retry_wait=1,
        )

    @node_from(from_name='筛选传送点')
    @operation_node(name='关闭筛选')
    def close_filter(self) -> OperationRoundResult:
        current_screen = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['3D地图'])
        if current_screen == '3D地图':
            return self.round_success(status=current_screen)

        self.round_by_click_area('3D地图', '按钮-关闭筛选')
        return self.round_wait(status='关闭筛选', wait=1)

    @node_from(from_name='关闭筛选')
    @operation_node(name='最小缩放', is_start_node=False)
    def click_mini_scale(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('3D地图', '按钮-最小缩放')
        start_point = area.center
        end_point = start_point + Point(-300, 0)
        self.ctx.controller.drag_to(start=start_point, end=end_point)
        return self.round_success()

    @node_from(from_name='最小缩放')
    @operation_node(name='选择传送点')
    def choose_tp_icon(self) -> OperationRoundResult:
        map_area = self.ctx.screen_loader.get_area('3D地图', '区域-地图')
        part = cv2_utils.crop_image_only(self.last_screenshot, map_area.rect)

        template1 = self.ctx.template_loader.get_template('map', '3d_map_tp_icon_1')
        all_mrl = cv2_utils.match_template(
            source=part,
            template=template1.raw,
            mask=template1.mask,
            threshold=0.5,
            only_best=False,
            ignore_inf=True,
        )
        # cv2_utils.show_image(part, rects=all_mrl, wait=0)

        large_map = self.ctx.world_patrol_service.get_large_map_by_area_full_id(self.target_area.full_id)
        icon_word_list = []
        target_icon = None
        for i in large_map.icon_list:
            icon_word_list.append(gt(i.icon_name))
            if i.icon_name == self.target_tp_name:
                target_icon = i

        top: bool | None = None
        left: bool | None  = None
        last_pos: Point | None = None
        least_confidence: float = 0  # 一些特殊情况 限制最低的置信度
        for mr in all_mrl:
            if not self.ctx.run_context.is_context_running:
                break

            if mr.confidence < least_confidence:
                continue

            # 判断方向是否满足
            if last_pos is not None:
                if top and mr.center.y > last_pos.y:
                    continue
                if not top and mr.center.y < last_pos.y:
                    continue
                if left and mr.center.x > last_pos.x:
                    continue
                if not left and mr.center.x < last_pos.x:
                    continue

            last_pos = mr.center
            self.ctx.controller.click(mr.center + map_area.left_top)
            time.sleep(1)
            self.screenshot()

            found_go = self.round_by_find_area(
                screen=self.last_screenshot,
                screen_name='3D地图',
                area_name='按钮-前往',
            )

            if not found_go:
                log.error('未找到前往按钮')
                least_confidence = mr.confidence
                continue

            # 当前显示的名字 理论上只有一个文本
            ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
                self.last_screenshot,
                rect=self.ctx.screen_loader.get_area('3D地图', '标题-当前选择传送点').rect,
            )
            if len(ocr_result_list) == 0:
                log.error('未识别到传送点名称')
                least_confidence = mr.confidence
                continue
            log.info(f'识别到传送点名称 {ocr_result_list[0].data}')

            icon_idx = str_utils.find_best_match_by_difflib(ocr_result_list[0].data, icon_word_list)
            if icon_idx is None or icon_idx < 0:
                log.error(f'未识别到传送点名称 {ocr_result_list[0].data}')
                least_confidence = mr.confidence
                continue

            current_icon = large_map.icon_list[icon_idx]
            log.info(f'匹配传送点 {current_icon.icon_name}')
            if current_icon.icon_name == self.target_tp_name:
                return self.round_success()

            # 判断下一个要选择的点在哪个方向
            left = target_icon.lm_pos.x < current_icon.lm_pos.x
            top = target_icon.lm_pos.y < current_icon.lm_pos.y

        # 本次截图全部的图标都不匹配
        if top is None:
            top = random.random() < 0.5
        if left is None:
            left = random.random() < 0.5
        start_point = map_area.center
        end_point = start_point + Point(300 * (1 if left else -1), 300 * (1 if top else -1))
        self.ctx.controller.drag_to(start=start_point, end=end_point)

        return self.round_retry()

    @node_from(from_name='选择传送点')
    @operation_node(name='点击前往')
    def click_go(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '3D地图', '按钮-前往',
            until_not_find_all=[('3D地图', '按钮-前往')],
            success_wait=1,
            retry_wait=1,
        )

    @node_from(from_name='点击前往')
    @operation_node(name='等待画面加载')
    def back_at_last(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

def __debug():
    ctx = ZContext()
    ctx.init_ocr()
    ctx.init_by_config()
    ctx.world_patrol_service.load_data()

    area = None
    for i in ctx.world_patrol_service.area_list:
        if i.full_id == 'production_area_building_east_side':
            area = i
            break

    tp_name = '中央制造区入口'

    op = TransportBy3dMap(ctx, area, tp_name)

    ctx.run_context.start_running()
    op.execute()
    ctx.run_context.stop_running()


if __name__ == '__main__':
    __debug()