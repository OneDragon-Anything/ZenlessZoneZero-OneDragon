import time

from cv2.typing import MatLike
from typing import List, Optional, Tuple

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidChooseCommon(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        有详情 有显示选择数量的选择
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name='迷失之地-通用选择')

        self.to_choose_num: int = 1  # 需要选择的数量

    @operation_node(name='选择', is_start_node=True)
    def choose_artifact(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '文本-详情')
        self.ctx.controller.mouse_move(area.center + Point(0, 100))
        time.sleep(0.1)
        screen = self.screenshot()

        screen_name = self.check_and_update_current_screen()
        if screen_name != '迷失之地-通用选择':
            # 进入本指令之前 有可能识别错画面
            return self.round_retry(status=f'当前画面 {screen_name}', wait=1)

        result = self.round_by_find_area(screen, '迷失之地-通用选择', '按钮-刷新')
        can_refresh = result.is_success

        art_list, chosen_list = self.get_artifact_pos(screen)
        art: Optional[MatchResult] = None
        if self.to_choose_num > 0:
            if len(art_list) == 0:
                return self.round_retry(status='无法识别藏品', wait=1)

            priority_list = self.ctx.lost_void.get_artifact_by_priority(
                art_list, self.to_choose_num,
                consider_priority_1=True, consider_priority_2=not can_refresh,
                consider_not_in_priority=not can_refresh
            )

            # 如果需要选择多个 则有任意一个符合优先级即可 剩下的用优先级以外的补上
            if len(priority_list) > 0 and len(priority_list) < self.to_choose_num:
                priority_list = self.ctx.lost_void.get_artifact_by_priority(
                    art_list, self.to_choose_num,
                    consider_priority_1=True, consider_priority_2=True,
                    consider_not_in_priority=True
                )

            # 注意最后筛选优先级的长度一定要符合需求的选择数量
            # 不然在选择2个情况下会一直选择1个 导致无法继续
            if len(priority_list) == self.to_choose_num:
                for chosen in chosen_list:
                    self.ctx.controller.click(chosen.center + Point(0, 100))
                    time.sleep(0.5)

                for art in priority_list:
                    self.ctx.controller.click(art.center)
                    time.sleep(0.5)
            elif can_refresh:
                result = self.round_by_find_and_click_area(screen, '迷失之地-通用选择', '按钮-刷新')
                if result.is_success:
                    return self.round_wait(result.status, wait=1)
                else:
                    return self.round_retry(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen=screen, screen_name='迷失之地-通用选择', area_name='按钮-确定',
                                                   success_wait=1, retry_wait=1)
        if result.is_success:
            status = result.status if art is None else f'选择 {art.data.name}'
            return self.round_success(status)
        else:
            return self.round_retry(result.status, wait=1)

    def get_artifact_pos(self, screen: MatLike) -> Tuple[List[MatchResult], List[MatchResult]]:
        """
        获取藏品的位置
        @param screen: 游戏画面
        @return: Tuple[识别到的武备的位置, 已经选择的位置]
        """
        is_gear: bool = False  # 区域-武备名称
        is_artifact: bool = False # 区域-藏品名称
        self.to_choose_num = 0

        area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '区域-标题')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result = self.ctx.ocr.run_ocr(part)

        target_result_list = [
            gt('请选择1项'),
            gt('请选择2项'),
            gt('请选择1个武备'),
            gt('获得武备'),
            gt('武备已升级'),
            gt('获得战利品'),
            gt('请选择1张卡牌'),
        ]

        for ocr_word in ocr_result.keys():
            idx = str_utils.find_best_match_by_difflib(ocr_word, target_result_list)
            if idx is None:
                self.to_choose_num = 0
            elif idx == 0:  # 请选择1项
                # 1.5 更新后 武备和普通鸣徽都是这个标题
                self.to_choose_num = 1
            elif idx == 1:  # 请选择2项
                is_artifact = True
                self.to_choose_num = 2
            elif idx == 2:  # 请选择1个武备
                is_gear = True
                self.to_choose_num = 1
            elif idx == 3:  # 获得武备
                is_gear = True
                self.to_choose_num = 0
            elif idx == 4:  # 武备已升级
                is_gear = True
                self.to_choose_num = 0
            elif idx == 5:  # 获得战利品
                is_artifact = True
                self.to_choose_num = 0
            elif idx == 6:  # 请选择1张卡牌
                is_artifact = True
                self.to_choose_num = 1

        if self.to_choose_num == 0:  # 不需要选择的
            return [], []

        if is_artifact:
            area_name = '区域-藏品名称'
            chosen_area_name = '区域-藏品已选择'
        elif is_gear:
            area_name = '区域-武备名称'
            chosen_area_name = None
        else:
            result = self.round_by_find_area(screen, '迷失之地-通用选择', '区域-武备标识')  # 下方的GEAR
            if result.is_success:
                area_name = '区域-武备名称'
                self.to_choose_num = 1
            else:
                area_name = '区域-藏品名称'
                self.to_choose_num = 1
            chosen_area_name = None

        area = self.ctx.screen_loader.get_area('迷失之地-通用选择', area_name)
        part = cv2_utils.crop_image_only(screen, area.rect)

        result_list: List[MatchResult] = []

        ocr_result_map = self.ctx.ocr.run_ocr(part)
        for ocr_result, mrl in ocr_result_map.items():
            art = self.ctx.lost_void.match_artifact_by_ocr_full(ocr_result)
            if art is None:
                continue

            result = mrl.max
            result.add_offset(area.left_top)
            result.data = art
            result_list.append(result)

        display_text = ','.join([i.data.display_name for i in result_list]) if len(result_list) > 0 else '无'
        log.info(f'当前识别藏品 {display_text}')

        to_cancel_list: List[MatchResult] = []
        target_chosen_words = ['有同流派武备', '已选择']
        if chosen_area_name is not None:
            area = self.ctx.screen_loader.get_area('迷失之地-通用选择', chosen_area_name)
            part = cv2_utils.crop_image_only(screen, area.rect)
            ocr_result_map = self.ctx.ocr.run_ocr(part)
            for ocr_word, mrl in ocr_result_map.items():
                idx = str_utils.find_best_match_by_difflib(ocr_word, target_chosen_words)
                if idx is None:
                    continue

                for mr in mrl:
                    mr.add_offset(area.left_top)
                    to_cancel_list.append(mr)

        return result_list, to_cancel_list


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.ocr.init_model()
    ctx.lost_void.init_before_run()
    ctx.start_running()

    op = LostVoidChooseCommon(ctx)
    op.execute()


def __get_get_artifact_pos():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.ocr.init_model()
    ctx.lost_void.init_before_run()

    op = LostVoidChooseCommon(ctx)
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('lost_void_choose_common')
    art_list, chosen_list = op.get_artifact_pos(screen)
    print(len(art_list), len(chosen_list))
    cv2_utils.show_image(screen, chosen_list[0] if len(chosen_list) > 0 else None, wait=0)
    import cv2
    cv2.destroyAllWindows()


if __name__ == '__main__':
    __debug()