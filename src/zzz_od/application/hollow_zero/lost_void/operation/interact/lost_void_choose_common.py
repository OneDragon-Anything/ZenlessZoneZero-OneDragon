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
        """
        通用事件选择，内置优先级选择、无效重试、放弃、刷新等逻辑
        """
        # =======================================
        # 第一阶段：初始化与识别
        # =======================================
        log.debug("进入通用选择流程...")
        # 移动鼠标避免悬浮在选项上触发tips
        area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '文本-详情')
        self.ctx.controller.mouse_move(area.center + Point(0, 100))
        time.sleep(0.2)
        screen = self.screenshot()

        # 获取所有可选和已选项目, 此方法会调用 check_choose_title 更新 to_choose_num
        art_list, chosen_list = self.get_artifact_pos(screen)
        log.debug(f"识别到 {len(art_list)} 个可选项, {len(chosen_list)} 个已选项, 需要选择 {self.to_choose_num} 个")
        
        # 预先检查刷新按钮，用于后续的优先级判断和放弃流程
        result = self.round_by_find_area(screen, '迷失之地-通用选择', '按钮-刷新')
        can_refresh = result.is_success
        log.debug(f"是否可刷新: {can_refresh}")

        # =======================================
        # 第二阶段：分支处理
        # =======================================
        # 分支A: 无需选择
        if self.to_choose_num == 0:
            log.info("检测到无需选择，尝试点击确定")
            result = self.round_by_find_and_click_area(screen, '迷失之地-通用选择', '按钮-确定',
                                                       success_wait=1, retry_wait=1)
            if result.is_success:
                return self.round_success("已确定")
            else:
                log.warning("找不到确定按钮，可能已在非选择界面，直接返回成功")
                return self.round_success("无需操作")

        # 分支B: 需要选择
        if len(art_list) == 0:
            log.warning("需要选择但未识别到任何可选项")
            return self.round_retry(status='无法识别藏品', wait=1)
        
        # 先取消所有已选择的项目，确保一个干净的初始状态
        if len(chosen_list) > 0:
            log.info(f"检测到已选项目 {[c.artifact.name for c in chosen_list]}，执行取消操作")
            for chosen in chosen_list:
                self.ctx.controller.click(chosen.rect.center)
                time.sleep(0.3)
            # 取消后刷新截图，重新识别选项
            screen = self.screenshot()
            art_list, _ = self.get_artifact_pos(screen)
            log.debug(f"取消选择后，重新识别到 {len(art_list)} 个可选项")

        # 2.1 计算优先级 (沿用现有逻辑)
        log.debug("开始计算优先级...")
        priority_list: list[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_by_priority(
            art_list, self.to_choose_num,
            consider_priority_1=True, consider_priority_2=not can_refresh,
            consider_not_in_priority=not can_refresh,
            consider_priority_new=self.ctx.lost_void.challenge_config.artifact_priority_new
        )
        if 0 < len(priority_list) < self.to_choose_num:  # 优先级不足时放宽标准补齐
            log.debug("高优先级选项不足，放宽标准重新计算")
            priority_list = self.ctx.lost_void.get_artifact_by_priority(
                art_list, self.to_choose_num, consider_priority_1=True, consider_priority_2=True,
                consider_not_in_priority=True,
                consider_priority_new=self.ctx.lost_void.challenge_config.artifact_priority_new
            )
        log.debug(f"最终优先级列表: {[item.artifact.name for item in priority_list] if priority_list else '空'}")

        # 2.2 执行选择或放弃
        if len(priority_list) == self.to_choose_num:
            log.info(f"按优先级选择: {[item.artifact.name for item in priority_list]}")
            # =======================================
            # 核心选择验证模块
            # =======================================
            if self.to_choose_num == 1:  # 单选，逐个验证
                log.debug("进入单选验证流程")
                for choice in priority_list:
                    log.debug(f"尝试选择: {choice.artifact.name}")
                    self.ctx.controller.click(choice.rect.center)
                    time.sleep(0.5)
                    
                    screen_after_click = self.screenshot()
                    confirm_check_result = self.round_by_find_area(screen_after_click, '迷失之地-通用选择', '按钮-确定')

                    if confirm_check_result.is_success:
                        log.info(f'选择 [{choice.artifact.name}] 有效, 点击确定')
                        click_result = self.round_by_find_and_click_area(
                            screen=screen_after_click,
                            screen_name='迷失之地-通用选择', area_name='按钮-确定',
                            success_wait=1, retry_wait=1
                        )
                        if click_result.is_success:
                            return self.round_success(f'选择 {choice.artifact.name}')
                        else:
                            return self.round_retry(click_result.status, wait=1)
                    else:
                        log.warning(f'选择 [{choice.artifact.name}] 无效, 取消并尝试下一个')
                        self.ctx.controller.click(choice.rect.center)  # 取消选择
                        time.sleep(0.2)
                        continue # 尝试下一个优先项
            
            else:  # 多选，一次性验证
                log.debug("进入多选流程，一次性全部选择后确认")
                for art in priority_list:
                    self.ctx.controller.click(art.rect.center)
                    time.sleep(0.3)
                
                screen_after_click = self.screenshot()
                log.info('多选完成, 点击确定')
                click_result = self.round_by_find_and_click_area(
                    screen=screen_after_click,
                    screen_name='迷失之地-通用选择', area_name='按钮-确定',
                    success_wait=1, retry_wait=1
                )
                if click_result.is_success:
                    return self.round_success(f'选择 {[item.artifact.name for item in priority_list]}')
                else:
                    return self.round_retry(click_result.status, wait=1)

        # =======================================
        # 第三阶段：放弃/收尾流程
        # =======================================
        log.warning('最优选项不满足要求或均无效, 进入放弃/刷新流程')

        # 1. 尝试刷新
        if can_refresh:
            log.info("尝试刷新")
            result = self.round_by_find_and_click_area(screen, '迷失之地-通用选择', '按钮-刷新')
            if result.is_success:
                return self.round_wait('已刷新', wait=1)

        # 2. 尝试放弃
        log.info("尝试放弃")
        abandon_button_location = ('迷失之地-通用选择', '按钮-放弃')
        result = self.round_by_find_and_click_area(
            screen,
            screen_name=abandon_button_location[0], area_name=abandon_button_location[1],
            success_wait=1, retry_wait=1
        )
        if result.is_success:
            return self.round_success('已放弃')

        # 3. 如果以上都失败
        return self.round_fail('所有选项均无效且无法放弃或刷新')

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