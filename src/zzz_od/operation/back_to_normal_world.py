from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.hollow_exit_by_menu import HollowExitByMenu
from zzz_od.operation.zzz_operation import ZOperation


class BackToNormalWorld(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        需要保证在任何情况下调用，都能返回大世界，让后续的应用可执行
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name=gt('返回大世界'))

        self.last_dialog_idx: int = -1  # 上次选择的对话选项下标
        self.click_exit_battle: bool = False

    @operation_node(name='画面识别', is_start_node=True, node_max_retry_times=60)
    def check_screen_and_run(self) -> OperationRoundResult:
        """
        识别游戏画面
        :return:
        """
        current_screen = self.check_and_update_current_screen()
        if current_screen in ['大世界-普通', '大世界-勘域']:
            return self.round_success(status=current_screen)

        result = self.round_by_goto_screen(screen=self.last_screenshot, screen_name='大世界-普通', retry_wait=None)
        if result.is_success:
            return self.round_success(result.status)

        if (not result.is_fail  # fail是没有路径可以到达
                and self.ctx.screen_loader.current_screen_name is not None):
            return self.round_wait(result.status, wait=1)

        result = self.round_by_find_area(self.last_screenshot, '大世界', '信息')
        if result.is_success:
            return self.round_success(result.status)

        mini_map = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)
        if mini_map.play_mask_found:
            return self.round_success(status='发现地图')

        # 大部分画面都有街区可以直接返回
        result = self.round_by_find_and_click_area(self.last_screenshot, '画面-通用', '左上角-街区')
        if result.is_success:
            return self.round_retry(result.status, wait=1)

        # 这可以是通用的退出战斗 退出战斗的画面也有返回按钮 需要在返回前面
        result = self.round_by_find_and_click_area(self.last_screenshot, '零号空洞-战斗', '退出战斗')
        if result.is_success:
            self.click_exit_battle = True
            return self.round_retry(result.status, wait=1)

        if self.click_exit_battle:
            result = self.round_by_find_and_click_area(self.last_screenshot, '零号空洞-战斗', '退出战斗-确认')
            if result.is_success:
                return self.round_retry(result.status, wait=1)
        self.click_exit_battle = False

        # 大部分画面左上角都有返回按钮
        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_retry(result.status, wait=1)

        # 进入游戏时 弹出来的继续对话框
        # 例如 空洞继续
        result = self.round_by_find_and_click_area(self.last_screenshot, '大世界', '对话框取消')
        if result.is_success:
            return self.round_retry(result.status, wait=1)

        # 这是领取完活跃度奖励的情况
        result = self.check_compendium(self.last_screenshot)
        if result is not None:
            return self.round_retry(result.status, wait=1)

        # 判断是否有好感度事件
        if self._check_agent_dialog(self.last_screenshot):
            return self._handle_agent_dialog(self.last_screenshot)

        # 判断在战斗画面
        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击')
        if result.is_success:
            self.round_by_click_area('战斗画面', '菜单')
            return self.round_retry(result.status, wait=1)
        # 空洞内撤退后的完成
        result = self.round_by_find_and_click_area(self.last_screenshot, '零号空洞-事件', '通关-完成')
        if result.is_success:
            return self.round_retry(result.status, wait=1)
        # 在空洞内
        result = hollow_event_utils.check_in_hollow(self.ctx, self.last_screenshot)
        if result is not None:
            op = HollowExitByMenu(self.ctx)
            op.execute()
            return self.round_retry(result, wait=1)

        click_back = self.round_by_click_area('菜单', '返回')
        if click_back.is_success:
            # 由于上方识别可能耗时较长
            # 这样就可能 当前截图是没加载的 耗时识别后加载好 但点击了返回
            # 那如果使用wait_round_time=1的话 可能导致点击后基本不等待
            # 进入下一轮截图就会识别到在大世界 但因为点击了返回又到了菜单
            # 相关 issue #1357
            return self.round_retry(click_back.status, wait=1)
        else:
            return self.round_fail()

    def _check_agent_dialog(self, screen: MatLike) -> bool:
        """
        识别是否有代理人好感度对话
        """
        area = self.ctx.screen_loader.get_area('大世界', '好感度标题')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        ocr_result_list = [i for i in ocr_result_map.keys()]
        agent_name_list = [gt(i.value.agent_name, 'game') for i in AgentEnum]
        idx1, idx2 = str_utils.find_most_similar(ocr_result_list, agent_name_list)
        return idx1 is not None and idx2 is not None

    def _handle_agent_dialog(self, screen: MatLike) -> OperationRoundResult:
        """
        处理代理人好感度对话
        """
        area = self.ctx.screen_loader.get_area('大世界', '好感度选项')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        if len(ocr_result_map) > 0:
            self.last_dialog_idx = 1  # 每次都换一个选项 防止错误识别点击了不是选项的地方
            if self.last_dialog_idx >= len(ocr_result_map):  # 下标过大 从0开始
                self.last_dialog_idx = 0

            current_idx = -1
            for ocr_result, mrl in ocr_result_map.items():
                current_idx += 1
                if current_idx == self.last_dialog_idx:
                    self.ctx.controller.click(mrl.max.center + area.left_top)
                    return self.round_wait(ocr_result, wait=1)
        else:
            self.round_by_click_area('菜单', '返回')
            return self.round_wait('对话无选项', wait=1)

    def check_compendium(self, screen: MatLike) -> OperationRoundResult:
        """
        判断是否在快捷手册
        """
        area = self.ctx.screen_loader.get_area('快捷手册', 'TAB列表')
        part = cv2_utils.crop_image_only(screen, area.rect)

        tab_list = self.ctx.compendium_service.data.tab_list
        target_word_list = [gt(i.tab_name, 'game') for i in tab_list]
        tab_num: int = 0
        ocr_results = self.ctx.ocr.run_ocr(part)
        for ocr_result, mrl in ocr_results.items():
            if mrl.max is None:
                continue

            idx = str_utils.find_best_match_by_difflib(ocr_result, target_word_list)
            if idx is not None and idx >= 0:
                tab_num += 1

        if tab_num >= 2:  # 找到了多个tab
            return self.round_by_click_area('快捷手册', '按钮-退出')

def __debug_op():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    op = BackToNormalWorld(ctx)
    ctx.run_context.start_running()
    op.execute()


def _debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    op = BackToNormalWorld(ctx)
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('111')
    import cv2
    op.last_screenshot = cv2.resize(screen, (1920, 1080))
    print(op.check_screen_and_run(screen).status)


if __name__ == '__main__':
    __debug_op()