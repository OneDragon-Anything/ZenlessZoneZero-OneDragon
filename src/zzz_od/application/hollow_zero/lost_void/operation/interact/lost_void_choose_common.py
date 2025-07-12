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
        self.to_choose_num: int = 1  # 需要选择的数量
        self.chosen_idx_list: list[int] = []  # 已经选择过的下标

    @operation_node(name='选择', is_start_node=True)
    def choose_artifact(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '文本-详情')
        self.ctx.controller.mouse_move(area.center + Point(0, 100))
        time.sleep(0.1)
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '迷失之地-通用选择', '按钮-刷新')
        can_refresh = result.is_success

        art_list, chosen_list = self.get_artifact_pos(screen)
        art: Optional[LostVoidArtifactPos] = None
        if self.to_choose_num > 0:
            if len(art_list) == 0:
                return self.round_retry(status='无法识别藏品', wait=1)

            priority_list: list[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_by_priority(
                art_list, self.to_choose_num,
                consider_priority_1=True, consider_priority_2=not can_refresh,
                consider_not_in_priority=not can_refresh,
                consider_priority_new=self.ctx.lost_void.challenge_config.artifact_priority_new
            )

            # 如果需要选择多个 则有任意一个符合优先级即可 剩下的用优先级以外的补上
            if 0 < len(priority_list) < self.to_choose_num:
                priority_list = self.ctx.lost_void.get_artifact_by_priority(
                    art_list, self.to_choose_num,
                    consider_priority_1=True, consider_priority_2=True,
                    consider_not_in_priority=True,
                    consider_priority_new=self.ctx.lost_void.challenge_config.artifact_priority_new
                )

            # 注意最后筛选优先级的长度一定要符合需求的选择数量
            # 不然在选择2个情况下会一直选择1个 导致无法继续
            if len(priority_list) == self.to_choose_num:
                for chosen in chosen_list:
                    self.ctx.controller.click(chosen.rect.center + Point(0, 100))
                    time.sleep(0.5)

                for art in priority_list:
                    self.ctx.controller.click(art.rect.center)
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
            status = result.status if art is None else f'选择 {art.artifact.name}'
            return self.round_success(status)
        else:
            return self.round_retry(result.status, wait=1)

    def get_artifact_pos(self, screen: MatLike) -> Tuple[List[LostVoidArtifactPos], List[LostVoidArtifactPos]]:
        """
        获取藏品的位置
        @param screen: 游戏画面
        @return: Tuple[识别到的武备的位置, 已经选择的位置]
        """
        self.check_choose_title(screen)
        if self.to_choose_num == 0:  # 不需要选择的
            return [], []

        artifact_name_list: list[str] = []
        for art in self.ctx.lost_void.all_artifact_list:
            artifact_name_list.append(gt(art.display_name, 'game'))

        artifact_pos_list: list[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_pos(
            screen,
            to_choose_gear_branch=self.to_choose_gear_branch
        )

        can_choose_list = [i for i in artifact_pos_list if i.can_choose]
        display_text = ', '.join([i.artifact.display_name for i in can_choose_list]) if len(can_choose_list) > 0 else '无'
        log.info(f'当前可选择藏品 {display_text}')

        chosen_list = [i for i in artifact_pos_list if i.chosen]
        display_text = ', '.join([i.artifact.display_name for i in chosen_list]) if len(chosen_list) > 0 else '无'
        log.info(f'当前已选择藏品 {display_text}')

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

        target_result_list = [
            gt('请选择1项', 'game'),
            gt('请选择2项', 'game'),
            gt('请选择1个武备', 'game'),
            gt('获得武备', 'game'),
            gt('武备已升级', 'game'),
            gt('获得战利品', 'game'),
            gt('请选择1张卡牌', 'game'),
            gt('请选择战术棱镜方案强化的方向', 'game'),
        ]

        result = self.round_by_find_area(screen, '迷失之地-通用选择', '区域-武备标识')  # 下方的GEAR
        if result.is_success:
            self.to_choose_gear = True
            self.to_choose_num = 1

        for ocr_word in ocr_result.keys():
            idx = str_utils.find_best_match_by_difflib(ocr_word, target_result_list)
            if idx is None:
                self.to_choose_num = 0
            elif idx == 0:  # 请选择1项
                # 1.5 更新后 武备和普通鸣徽都是这个标题
                self.to_choose_num = 1
            elif idx == 1:  # 请选择2项
                self.to_choose_artifact = True
                self.to_choose_num = 2
            elif idx == 2:  # 请选择1个武备
                self.to_choose_gear = True
                self.to_choose_num = 1
            elif idx == 3:  # 获得武备
                self.to_choose_gear = True
                self.to_choose_num = 0
            elif idx == 4:  # 武备已升级
                self.to_choose_gear = True
                self.to_choose_num = 0
            elif idx == 5:  # 获得战利品
                self.to_choose_artifact = True
                self.to_choose_num = 0
            elif idx == 6:  # 请选择1张卡牌
                self.to_choose_artifact = True
                self.to_choose_num = 1
            elif idx == 7:  # 请选择战术棱镜方案强化的方向
                self.to_choose_gear = True
                self.to_choose_gear_branch = True
                self.to_choose_num = 1

def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.lost_void.init_before_run()
    ctx.start_running()

    op = LostVoidChooseCommon(ctx)
    op.execute()


def __get_get_artifact_pos():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.lost_void.init_before_run()

    op = LostVoidChooseCommon(ctx)
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('_1749883678280')
    art_list, chosen_list = op.get_artifact_pos(screen)
    print(len(art_list), len(chosen_list))
    cv2_utils.show_image(screen, chosen_list[0] if len(chosen_list) > 0 else None, wait=0)
    import cv2
    cv2.destroyAllWindows()


if __name__ == '__main__':
    __debug()