from cv2.typing import MatLike

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.hollow_exit_by_menu import HollowExitByMenu
from zzz_od.operation.map_transport import MapTransport
from zzz_od.operation.zzz_operation import ZOperation


class BackToNormalWorld(ZOperation):

    def __init__(self, ctx: ZContext, ensure_normal_world: bool = False):
        """
        需要保证在任何情况下调用，都能返回大世界，让后续的应用可执行

        Args:
            ctx (ZContext): 上下文
            ensure_normal_world (bool): 是否回到普通大世界
        """
        ZOperation.__init__(self, ctx, op_name=gt('返回大世界'))

        self.ensure_normal_world: bool = ensure_normal_world  # 是否回到普通大世界
        self.handle_init()

    def handle_init(self) -> None:
        self.last_dialog_idx: int = -1  # 上次选择的对话选项下标
        self.click_exit_battle: bool = False  # 是否点击了退出战斗
        self.prefer_dialog_confirm: bool = False  # 第一次优先取消，后续确认/取消轮流点击

    @node_from(from_name='打开地图', success=False)
    @node_from(from_name='执行传送')
    @node_from(from_name='执行传送', success=False)
    @node_from(from_name='确认脱离卡死', success=False)
    @operation_node(name='画面识别', is_start_node=True, node_max_retry_times=60)
    def check_screen_and_run(self) -> OperationRoundResult:
        """
        识别游戏画面
        :return:
        """
        screen_name_list = ['大世界-普通', '大世界-勘域']
        current_screen = self.check_and_update_current_screen()
        if current_screen in screen_name_list:
            if current_screen == '大世界-勘域':
                already_transport = self.previous_node.name == '执行传送' and self.previous_node.is_success
                if self.ensure_normal_world and not already_transport:
                    return self.round_success('传送到录像店')

            return self.round_success(status=current_screen)

        result = self.round_by_goto_screen(screen=self.last_screenshot, screen_name='大世界-普通', retry_wait=None)
        if result.is_success:
            return self.round_success(result.status)

        if (not result.is_fail  # fail是没有路径可以到达
                and self.ctx.screen_loader.current_screen_name is not None):
            return self.round_wait(result.status, wait=1)

        result = self.round_by_find_area_binary(self.last_screenshot, '大世界', '信息')
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_area(self.last_screenshot, '大世界', '星期')
        if result.is_success:
            return self.round_success(result.status)

        mini_map = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)
        if mini_map.play_mask_found:
            return self.round_success(status='发现地图')

        # 大部分画面都有街区可以直接返回
        result = self.round_by_find_and_click_area(self.last_screenshot, '画面-通用', '左上角-街区')
        if result.is_success:
            return self.round_retry(result.status, wait=1)


        # 战斗菜单-退出战斗（完全通用，包括但不限于危局强袭战！）
        result = self.round_by_find_and_click_area(self.last_screenshot, '战斗-菜单', '按钮-退出战斗')
        if result.is_success:
            self.click_exit_battle = True
            return self.round_retry(result.status, wait=1)
        if self.click_exit_battle:  # 必须置前，因为会被通用的"取消"误判
            result = self.round_by_find_and_click_area(self.last_screenshot, '战斗-菜单', '按钮-退出战斗-确认')
            if result.is_success:
                return self.round_retry(result.status, wait=1)
        self.click_exit_battle = False

        # 战斗菜单-脱离卡死（大世界-勘域不慎进入战斗状态时使用）
        result = self.round_by_find_and_click_area(self.last_screenshot, '战斗-菜单', '按钮-脱离卡死')
        if result.is_success:
            return self.round_success('脱离卡死', wait=1)

        # 通用返回按钮（识别点击型）
        # 需要在"完成"前面，某些插件场景可能会识别到'返回'和"完成"同时存在
        result = self.round_by_find_and_click_area(self.last_screenshot, '画面-通用', '返回')
        if result.is_success:
            return self.round_retry(result.status, wait=1)

        # 部分画面有关闭按钮
        result = self.round_by_find_and_click_area(self.last_screenshot, '画面-通用', '关闭')
        if result.is_success:
            return self.round_retry(result.status, wait=1)

        # 通用完成按钮
        # 某些插件场景"合成"可能会被误匹配为"完成"
        # 需要在'返回'后面，购买大月卡后返回大世界一直点击“已完成购买” issue #2005
        result = self.round_by_find_and_click_area(self.last_screenshot, '画面-通用', '完成')
        if result.is_success:
            return self.round_retry(result.status, wait=1)

        # 在空洞内
        result = hollow_event_utils.check_in_hollow(self.ctx, self.last_screenshot)
        if result is not None:
            op = HollowExitByMenu(self.ctx)
            op.execute()
            return self.round_retry(result, wait=1)

        # 通用对话框：确认/取消轮流优先点击，避免卡在只点一种按钮
        first_area = '对话框确认' if self.prefer_dialog_confirm else '对话框取消'
        second_area = '对话框取消' if self.prefer_dialog_confirm else '对话框确认'
        result = self.round_by_find_and_click_area(self.last_screenshot, '大世界', first_area)
        if result.is_success:
            self.prefer_dialog_confirm = not self.prefer_dialog_confirm
            return self.round_retry(result.status, wait=1)
        result = self.round_by_find_and_click_area(self.last_screenshot, '大世界', second_area)
        if result.is_success:
            self.prefer_dialog_confirm = not self.prefer_dialog_confirm
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
            return self.round_retry(result.status, wait=0.5)

        # 通用返回按钮（兜底点击型）
        # 区域位于左上角的红色返回按钮，不进行识别，相当于点击空白区域，故不能提前使用
        click_back = self.round_by_click_area('画面-通用', '返回')
        if click_back.is_success:
            # 由于上方识别可能耗时较长
            # 这样就可能 当前截图是没加载的 耗时识别后加载好 但点击了返回
            # 那如果使用wait_round_time=1的话 可能导致点击后基本不等待
            # 进入下一轮截图就会识别到在大世界 但因为点击了返回又到了菜单
            # 相关 issue #1357
            return self.round_retry(click_back.status, wait=0.5)
        else:
            return self.round_fail()

    @node_from(from_name='画面识别', status='脱离卡死')
    @operation_node(name='确认脱离卡死')
    def confirm_escape_stuck(self) -> OperationRoundResult:
        """确认脱离卡死"""
        return self.round_by_find_and_click_area(self.last_screenshot, '战斗-菜单', '按钮-脱离卡死-确认', retry_wait=0.5)

    @node_from(from_name='画面识别', status='传送到录像店')
    @node_from(from_name='确认脱离卡死')
    @operation_node(name='打开地图', node_max_retry_times=60)
    def open_map(self) -> OperationRoundResult:
        """脱离卡死后，识别到大世界立即点击地图按钮"""
        return self.round_by_find_and_click_area(self.last_screenshot, '大世界', '地图', retry_wait=0.5)

    @node_from(from_name='打开地图')
    @operation_node(name='执行传送')
    def do_transport(self) -> OperationRoundResult:
        """打开地图后，传送到录像店房间"""
        op = MapTransport(self.ctx, '录像店', '房间')
        return self.round_by_op_result(op.execute())

    def _check_agent_dialog(self, screen: MatLike) -> bool:
        """
        识别是否有代理人好感度对话
        """
        area = self.ctx.screen_loader.get_area('大世界', '好感度标题')
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            image=screen,
            rect=area.rect,
        )
        ocr_word_list: list[str] = [i.data for i in ocr_result_list]
        agent_name_list = [i.value.agent_name for i in AgentEnum] + ['小黑']
        agent_name_list = [gt(i, 'game') for i in agent_name_list]
        idx1, idx2 = str_utils.find_most_similar(ocr_word_list, agent_name_list)
        return idx1 is not None and idx2 is not None

    def _handle_agent_dialog(self, screen: MatLike) -> OperationRoundResult | None:
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

        return None

    def check_compendium(self, screen: MatLike) -> OperationRoundResult | None:
        """
        判断是否在快捷手册
        """
        area = self.ctx.screen_loader.get_area('快捷手册', 'TAB列表')

        tab_list = self.ctx.compendium_service.data.tab_list
        target_word_list = [gt(i.tab_name, 'game') for i in tab_list]
        tab_num: int = 0

        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            image=screen,
            rect=area.rect,
        )
        for mr in ocr_result_list:
            idx = str_utils.find_best_match_by_difflib(mr.data, target_word_list)
            if idx is not None and idx >= 0:
                tab_num += 1

        if tab_num >= 2:  # 找到了多个tab
            return self.round_by_click_area('快捷手册', '按钮-退出')

        return None


def _debug():
    ctx = ZContext()
    ctx.init()
    op = BackToNormalWorld(ctx)
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('508500962-c6b83e60-fc00-49ce-83d0-17e0e49a5aa1')
    import cv2
    op.last_screenshot = cv2.resize(screen, (1920, 1080))
    print(op.check_screen_and_run().status)


if __name__ == '__main__':
    _debug()
