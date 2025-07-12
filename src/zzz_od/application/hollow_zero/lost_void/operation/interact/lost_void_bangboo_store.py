import time
from typing import List

import cv2
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.lost_void.context.lost_void_artifact import LostVoidArtifact
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_artifact_pos import LostVoidArtifactPos
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_common import LostVoidChooseCommon
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidBangbooStore(ZOperation):

    def __init__(self, ctx: ZContext):
        ZOperation.__init__(self, ctx, op_name='迷失之地-邦布商店')

        self.refresh_times: int = 0  # 刷新次数
        self.store_type: str = '标识-金币'  # 商店类型
        self.slide_to_right: bool = False  # 滑动到右侧看更多的商品

    @operation_node(name='识别商店类型', is_start_node=True)
    def check_store_type(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '迷失之地-邦布商店', '标识-金币')
        if result.is_success:
            self.store_type = result.status
            return self.round_success(result.status)

        result = self.round_by_find_area(screen, '迷失之地-邦布商店', '标识-血量')
        if result.is_success:
            self.store_type = result.status
            return self.round_success(result.status)

        return self.round_retry(status='未识别商店类型', wait=1)

    @node_from(from_name='识别商店类型')
    @node_from(from_name='识别商店类型', success=False)
    @node_from(from_name='确认后处理')
    @operation_node(name='购买藏品')
    def buy_artifact_gold(self) -> OperationRoundResult:
        # 移动鼠标到空的区域 防止阻碍识别
        area = self.ctx.screen_loader.get_area('迷失之地-邦布商店', '文本-详情')
        self.ctx.controller.mouse_move(area.center + Point(0, 100))
        time.sleep(0.1)

        screen = self.screenshot()

        if self.store_type == '标识-血量':
            if not self.ctx.lost_void.challenge_config.store_blood:
                return self.round_fail('不使用血量购买')

            if not self.check_min_blood_valid(screen):
                return self.round_fail('血量低于设定最小值')

        # 按刷新之后的确认
        result = self.round_by_find_and_click_area(screen, '迷失之地-邦布商店', '按钮-刷新-确认')
        if result.is_success:
            self.refresh_times += 1
            return self.round_wait(result.status, wait=1)

        screen_name = self.check_and_update_current_screen()
        if screen_name != '迷失之地-邦布商店':
            # 进入本指令之前 有可能识别错画面
            return self.round_retry(status=f'当前画面 {screen_name}', wait=1)

        art_list: List[LostVoidArtifactPos] = self.get_artifact_pos(screen)
        if len(art_list) == 0:
            if not self.slide_to_right:
                start = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
                end = start + Point(-400, 0)
                self.ctx.controller.drag_to(start=start, end=end)
                self.slide_to_right = True
                return self.round_wait(status='向右滑动')
            return self.round_retry(status='未识别可购买藏品', wait=1)

        priority_list: List[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_by_priority(
            art_list, 1,
            consider_priority_1=True, consider_priority_2=self.refresh_times > self.ctx.lost_void.challenge_config.buy_only_priority_1,
            consider_not_in_priority=self.refresh_times > self.ctx.lost_void.challenge_config.buy_only_priority_2,
            consider_priority_new=self.ctx.lost_void.challenge_config.artifact_priority_new
        )

        if len(priority_list) == 0:
            if not self.slide_to_right:
                start = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
                end = start + Point(-400, 0)
                self.ctx.controller.drag_to(start=start, end=end)
                self.slide_to_right = True
                return self.round_wait(status='向右滑动')

            result = self.round_by_find_and_click_area(screen, '迷失之地-邦布商店', '按钮-刷新-可用')
            if result.is_success:
                self.slide_to_right = False  # 刷新后 重置滑动
                return self.round_wait(result.status, wait=1)

            # 不可以刷新了 就不管优先级都买了
            priority_list = self.ctx.lost_void.get_artifact_by_priority(art_list, len(art_list))

        if len(priority_list) == 0:
            return self.round_retry(status='按优先级选择藏品失败', wait=1)

        target: LostVoidArtifactPos = priority_list[0]
        target_item: LostVoidArtifact = target.artifact

        self.ctx.controller.click(target.store_buy_rect.center)
        return self.round_success(target_item.name, wait=1)

    def get_artifact_pos(self, screen: MatLike) -> List[LostVoidArtifactPos]:
        """
        获取藏品的位置
        @param screen: 游戏画面
        @return: 识别到的藏品
        """
        artifact_pos_list: list[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_pos(screen)

        # 识别价格
        area = self.ctx.screen_loader.get_area('迷失之地-邦布商店', '区域-价格')
        part = cv2_utils.crop_image_only(screen, area.rect)
        mask = cv2.inRange(part, (200, 200, 200), (255, 255, 255))
        mask = cv2_utils.dilate(mask, 2)
        to_ocr = cv2.bitwise_and(part, part, mask=mask)
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)
        for ocr_result, mrl in ocr_result_map.items():
            price = str_utils.get_positive_digits(ocr_result)
            if price is None:
                continue

            for mr in mrl:
                mr.add_offset(area.left_top)
                for artifact_pos in artifact_pos_list:
                    artifact_pos.add_price(price, mr.rect)

        # 识别购买按钮
        area = self.ctx.screen_loader.get_area('迷失之地-邦布商店', '区域-购买按钮')
        part = cv2_utils.crop_image_only(screen, area.rect)
        mask = cv2.inRange(part, (200, 200, 200), (255, 255, 255))
        mask = cv2_utils.dilate(mask, 2)
        to_ocr = cv2.bitwise_and(part, part, mask=mask)
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)
        for ocr_result, mrl in ocr_result_map.items():
            if not str_utils.find_by_lcs(gt('购买', 'game'), ocr_result):
                continue

            for mr in mrl:
                mr.add_offset(area.left_top)
                for artifact_pos in artifact_pos_list:
                    artifact_pos.add_buy(mr.rect)

        can_buy_list = [i for i in artifact_pos_list if i.store_buy_rect is not None]
        display_text = ', '.join([i.artifact.display_name for i in can_buy_list]) if len(can_buy_list) > 0 else '无'
        log.info(f'当前可购买藏品 {display_text}')

        return can_buy_list

    def check_min_blood_valid(self, screen: MatLike) -> bool:
        """
        识别当前血量是否满足购买
        @param screen: 游戏画面
        @return:
        """
        min_blood = self.ctx.lost_void.challenge_config.store_blood_min

        area = self.ctx.screen_loader.get_area('迷失之地-邦布商店', '区域-角色头像')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        for ocr_result, mrl in ocr_result_map.items():
            blood = str_utils.get_positive_digits(ocr_result)
            if blood is None:
                continue
            if blood < min_blood:
                return False

        return True

    @node_from(from_name='购买藏品')
    @operation_node(name='点击确认')
    def click_confirm(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='迷失之地-邦布商店', area_name='按钮-购买-确认',
                                                 success_wait=1, retry_wait=1,
                                                 until_not_find_all=[('迷失之地-邦布商店', '按钮-购买-确认')])

    @node_from(from_name='点击确认')
    @operation_node(name='确认后处理')
    def after_confirm(self) -> OperationRoundResult:
        """
        处理可能出现的武备升级环节
        @return:
        """
        screen = self.screenshot()
        screen_name = self.check_and_update_current_screen(screen)

        if screen_name == '迷失之地-通用选择':
            op = LostVoidChooseCommon(self.ctx)
            op_result = op.execute()
            if op_result.success:
                return self.round_wait(status='武备升级', wait=1)
            else:
                return self.round_retry(status='武备升级失败', wait=1)
        elif screen_name == '迷失之地-邦布商店':
            return self.round_success(status=self.store_type, wait=1)
        else:
            return self.round_retry(status=f'未知画面 {screen_name}', wait=1)

    @node_from(from_name='购买藏品', success=False)
    @operation_node(name='购买结束')
    def finish(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='迷失之地-邦布商店', area_name='按钮-返回',
                                                 success_wait=1, retry_wait=1,
                                                 until_not_find_all=[('迷失之地-邦布商店', '按钮-返回')])


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.lost_void.init_before_run()
    ctx.start_running()

    op = LostVoidBangbooStore(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()