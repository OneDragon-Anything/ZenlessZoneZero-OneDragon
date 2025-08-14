import random
import time

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolArea, WorldPatrolLargeMapIcon
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
        target_word_idx = str_utils.find_best_match_by_difflib(gt(target_area_name, 'game'), ocr_word_list)
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
    @operation_node(name='初始化传送点搜索')
    def init_tp_search(self) -> OperationRoundResult:
        """
        初始化传送点搜索：获取目标传送点信息和搜索参数
        """
        # 获取目标传送点信息
        large_map = self.ctx.world_patrol_service.get_large_map_by_area_full_id(self.target_area.full_id)
        icon_word_list = []
        target_icon: WorldPatrolLargeMapIcon = None
        for i in large_map.icon_list:
            icon_word_list.append(i.icon_name)
            if i.icon_name == self.target_tp_name:
                target_icon = i

        if target_icon is None:
            log.error(f'未找到目标传送点配置 {self.target_tp_name}')
            return self.round_fail(f'未找到目标传送点配置 {self.target_tp_name}')

        # 存储搜索所需的信息
        self.large_map = large_map
        self.icon_word_list = icon_word_list
        self.target_icon = target_icon
        self.map_area = self.ctx.screen_loader.get_area('3D地图', '区域-地图')

        log.info(f'初始化传送点搜索完成，目标：{self.target_tp_name}')
        return self.round_success()

    @node_from(from_name='初始化传送点搜索')
    @operation_node(name='搜索传送点循环', node_max_retry_times=20)
    def search_tp_icon_loop(self) -> OperationRoundResult:
        """
        传送点搜索主循环：
        原子化交互与导航策略：
        1. 侦察 - 寻找当前画面内所有可见的传送点图标
        2. 决策点 - 根据画面内是否有图标选择行动
        3. 交互与识别 - 点击一个图标并识别其名称
        4. 导航计算 - 匹配检查或计算精确拖动方向
        5. 执行与循环 - 执行精确拖动操作并重新开始流程
        """
        # 步骤1: 侦察 - 寻找所有可见的传送点图标
        part = cv2_utils.crop_image_only(self.last_screenshot, self.map_area.rect)

        template1 = self.ctx.template_loader.get_template('map', '3d_map_tp_icon_1')
        all_mrl = cv2_utils.match_template(
            source=part,
            template=template1.raw,
            mask=template1.mask,
            threshold=0.5,
            only_best=False,
            ignore_inf=True,
        )

        # 步骤2: 决策点 - 根据画面内是否有图标选择行动
        if len(all_mrl) == 0:
            # 情况A：画面内无任何图标 - 执行随机方向拖动
            log.debug('画面内无传送点图标，执行随机拖动')
            self._perform_random_drag(self.map_area)
            return self.round_retry(wait=0.5)  # 等待拖动完成后重试

        # 情况B：画面内有图标 - 依次尝试每个图标
        log.debug(f'画面内发现 {len(all_mrl)} 个传送点图标，开始逐个检查')

        # 首先检查所有图标，看是否有目标传送点
        navigation_reference = None  # 用于导航的参考点
        for idx, selected_icon in enumerate(all_mrl):
            log.debug(f'检查第 {idx + 1}/{len(all_mrl)} 个图标')

            # 步骤3: 交互与识别 - 点击图标并识别名称
            # 点击图标
            click_pos = selected_icon.center + self.map_area.left_top
            self.ctx.controller.click(click_pos)
            time.sleep(1)
            self.screenshot()

            # 检查是否出现前往按钮
            found_go = self.round_by_find_area(
                screen=self.last_screenshot,
                screen_name='3D地图',
                area_name='按钮-前往',
            )

            if found_go.is_fail:
                log.warning('点击图标后未找到前往按钮')
                continue  # 尝试下一个图标

            # OCR识别传送点名称
            ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
                self.last_screenshot,
                rect=self.ctx.screen_loader.get_area('3D地图', '标题-当前选择传送点').rect,
            )

            if len(ocr_result_list) == 0:
                log.warning('未能OCR识别到传送点名称')
                continue  # 尝试下一个图标

            recognized_name = ocr_result_list[0].data
            log.debug(f'OCR识别到传送点名称：{recognized_name}')

            # 匹配到具体的图标
            icon_idx = str_utils.find_best_match_by_difflib(gt(recognized_name, 'game'), self.icon_word_list)
            if icon_idx is None or icon_idx < 0:
                log.warning(f'无法匹配传送点名称：{recognized_name}')
                continue  # 尝试下一个图标

            matched_icon = self.large_map.icon_list[icon_idx]
            log.debug(f'成功匹配到传送点：{matched_icon.icon_name}')
            current_icon_name = matched_icon.icon_name

            # 步骤4: 导航计算
            if current_icon_name == self.target_tp_name:
                # 找到目标传送点！
                log.info(f'找到目标传送点：{self.target_tp_name}')
                return self.round_success()

            # 记录第一个图标作为导航参考点
            if navigation_reference is None:
                navigation_reference = matched_icon
                log.debug(f'记录导航参考点：{matched_icon.icon_name}({matched_icon.lm_pos.x}, {matched_icon.lm_pos.y})')

        # 所有图标都检查完毕，没有找到目标，执行导航
        if navigation_reference is not None:
            # 步骤5: 使用参考点执行精确导航
            log.debug(f'当前参考位置：{navigation_reference.icon_name}({navigation_reference.lm_pos.x}, {navigation_reference.lm_pos.y})')
            log.debug(f'目标位置：{self.target_tp_name}({self.target_icon.lm_pos.x}, {self.target_icon.lm_pos.y})')

            # 计算目标相对于当前位置的方向
            dx = self.target_icon.lm_pos.x - navigation_reference.lm_pos.x
            dy = self.target_icon.lm_pos.y - navigation_reference.lm_pos.y

            # 标准化拖动距离（避免过小的移动）
            drag_distance = 300
            if abs(dx) > abs(dy):
                # 主要沿X轴移动
                # 目标在右侧(dx>0)时，需要向左拖动地图(drag_x<0)
                drag_x = -drag_distance if dx > 0 else drag_distance
                drag_y = -int(drag_distance * (dy / abs(dx))) if dx != 0 else 0
            else:
                # 主要沿Y轴移动
                # 目标在下方(dy>0)时，需要向上拖动地图(drag_y<0)
                drag_y = -drag_distance if dy > 0 else drag_distance
                drag_x = -int(drag_distance * (dx / abs(dy))) if dy != 0 else 0

            start_point = self.map_area.center
            end_point = start_point + Point(drag_x, drag_y)

            log.debug(f'执行精确拖动：从 {navigation_reference.icon_name}({navigation_reference.lm_pos.x}, {navigation_reference.lm_pos.y}) '
                      f'向 {self.target_icon.icon_name}({self.target_icon.lm_pos.x}, {self.target_icon.lm_pos.y}) '
                      f'坐标差({dx}, {dy}) -> 拖动方向({drag_x}, {drag_y})')

            self.ctx.controller.drag_to(start=start_point, end=end_point)
        else:
            # 所有图标都识别失败，执行随机拖动
            log.debug('所有图标识别失败，执行随机拖动')
            self._perform_random_drag(self.map_area)

        # 等待拖动完成后重试
        return self.round_retry(wait=0.5)

    def _perform_random_drag(self, map_area: ScreenArea):
        """执行随机方向拖动"""
        # 随机选择拖动方向
        directions = [
            Point(300, 0),    # 右
            Point(-300, 0),   # 左
            Point(0, 300),    # 下
            Point(0, -300),   # 上
            Point(300, 300),  # 右下
            Point(-300, -300), # 左上
            Point(300, -300), # 右上
            Point(-300, 300), # 左下
        ]

        direction = random.choice(directions)
        start_point = map_area.center
        end_point = start_point + direction

        log.debug(f'执行随机拖动：{direction}')
        self.ctx.controller.drag_to(start=start_point, end=end_point)

    @node_from(from_name='搜索传送点循环')
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
        if i.full_id == 'former_employee_community':
            area = i
            break

    tp_name = '职工宿舍西区'

    op = TransportBy3dMap(ctx, area, tp_name)

    ctx.run_context.start_running()
    op.execute()
    ctx.run_context.stop_running()


if __name__ == '__main__':
    __debug()
