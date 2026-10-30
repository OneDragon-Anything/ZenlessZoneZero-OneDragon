import re

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, i18_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.hollow_exit_by_menu import HollowExitByMenu
from zzz_od.operation.map_transport import MapTransport
from zzz_od.operation.zzz_operation import ZOperation


class BackToNormalWorld(ZOperation):

    def __init__(self, ctx: ZContext, ensure_normal_world: bool = False, allow_battle: bool = False):
        """
        需要保证在任何情况下调用，都能返回大世界，让后续的应用可执行

        Args:
            ctx (ZContext): 上下文
            ensure_normal_world (bool): 是否回到普通大世界
            allow_battle (bool): 是否允许在战斗状态直接返回成功（锄大地传送后用，让调用方处理战斗）。
                启用时调用方必须处理返回的 status='大世界-战斗'，否则角色将卡在战斗画面。
        """
        ZOperation.__init__(self, ctx, op_name=gt('返回大世界'))

        self.ensure_normal_world: bool = ensure_normal_world  # 是否回到普通大世界
        self.allow_battle: bool = allow_battle  # 是否允许战斗状态直接返回
        self.handle_init()

    def handle_init(self) -> None:
        self.last_dialog_idx: int = -1  # 上次选择的对话选项下标
        self.click_exit_battle: bool = False  # 是否点击了退出战斗
        self.prefer_dialog_confirm: bool = True  # 默认为 True：优先确认/前往，确保导航和操作正常推进
        self._dialog_confirm_times: int = 0  # 弹窗确认点击尝试次数
        self._last_dialog_key: tuple[str, ...] | None = None  # 上次处理的双按钮弹窗标识 弹窗变化时重置确认次数

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
        # 1. 优先检查并处理阻断大世界交互的各类模态弹窗（提示/确认/错误）
        modal_res = self._handle_modal_dialog(self.last_screenshot)
        if modal_res is not None:
            return modal_res

        # 检查小地图：如果小地图已出现，说明已经处于正常大世界，直接返回成功，避免误触发场景对话
        # 勘域中同样有小地图 需要确保在普通大世界时交给下方画面识别处理传送
        if not self.ensure_normal_world:
            mini_map = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)
            if mini_map is not None and getattr(mini_map, 'play_mask_found', False):
                return self.round_success(status='大世界-普通')

        # 2. 优先检查并推进活跃的剧情/NPC对话（避免处于对话中却误判为大世界已就绪）
        dialogue_res = self._handle_any_dialogue(self.last_screenshot)
        if dialogue_res is not None:
            return dialogue_res


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

        mini_map = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)
        if mini_map.play_mask_found:
            return self.round_success(status='发现地图')

        # 大部分画面都有街区或勘域可以直接返回，“区域”通过 0.5 LCS 匹配“街区”的“区”或“勘域”的“域”
        result = self.round_by_find_and_click_area(self.last_screenshot, '画面-通用', '左上角-区域')
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
        # 需要在"完成"前面，否则在丽都城募app（若购买了大月卡）会误点击“已完成购买” issue #2005
        result = self.round_by_find_and_click_area(self.last_screenshot, '画面-通用', '返回')
        if result.is_success:
            return self.round_retry(result.status, wait=1)

        # 部分画面有关闭按钮
        result = self.round_by_find_and_click_area(self.last_screenshot, '画面-通用', '关闭')
        if result.is_success:
            return self.round_retry(result.status, wait=1)

        # 通用完成按钮
        result = self.round_by_find_and_click_area(self.last_screenshot, '画面-通用', '完成')
        if result.is_success:
            return self.round_retry(result.status, wait=1)

        # 在空洞内
        result = hollow_event_utils.check_in_hollow(self.ctx, self.last_screenshot)
        if result is not None:
            op = HollowExitByMenu(self.ctx)
            op.execute()
            return self.round_retry(result, wait=1)

        # 通用对话框：优先点击确认推进流程，确认未出现时才点击取消
        result = self.round_by_find_and_click_area(self.last_screenshot, '大世界', '对话框确认')
        if result.is_success:
            return self.round_retry(result.status, wait=1.5)
        result = self.round_by_find_and_click_area(self.last_screenshot, '大世界', '对话框取消')
        if result.is_success:
            return self.round_retry(result.status, wait=1.5)

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
            if self.allow_battle:
                # 锄大地传送后落地即进入战斗，直接返回成功让调用方处理战斗
                return self.round_success(status='大世界-战斗')
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

    def _handle_modal_dialog(self, screen: MatLike) -> OperationRoundResult | None:
        """
        检查并处理界面上的模态确认/提示弹窗（单按钮居中确定、双按钮确认/取消、关闭按钮）。
        始终优先确认（前往/确定），确保传送及交互操作能正常继续。
        """
        if screen is None or screen.size == 0:
            return None

        # 弹窗按钮通常位于屏幕中下方水平居中区域，限定此范围避免误扫外围 HUD 或文本
        dialog_rect = Rect(700, 560, 1280, 720)
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(screen, rect=dialog_rect, crop_first=False)
        if not ocr_result_list:
            self._dialog_confirm_times = 0
            self._last_dialog_key = None
            return None

        confirm_items = []
        cancel_items = []

        confirm_kws = ['确认', '确定', '好的', '前往', '知道了', '传送']
        cancel_kws = ['取消']
        if i18_utils.get_game_lang() == 'en':
            confirm_kws.extend(['Confirm', 'OK', 'Yes', 'Understood', 'Travel'])
            cancel_kws.extend(['Cancel'])

        for item in ocr_result_list:
            text_clean = item.data.strip()
            # 按钮文本绝不会是长句子、描述文本或技能说明（过滤 > 10 个字符）
            if len(text_clean) == 0 or len(text_clean) > 10:
                continue
            is_cancel = False
            for kw in cancel_kws:
                if str_utils.find_by_lcs(kw, text_clean, percent=0.6) or kw.lower() == text_clean.lower():
                    cancel_items.append(item)
                    is_cancel = True
                    break
            if is_cancel:
                continue
            for kw in confirm_kws:
                if str_utils.find_by_lcs(kw, text_clean, percent=0.6) or kw.lower() == text_clean.lower():
                    confirm_items.append(item)
                    break

        if not confirm_items and not cancel_items:
            self._dialog_confirm_times = 0
            self._last_dialog_key = None
            return None

        # 双按钮弹窗：始终优先点击确认（前往/确定），连续多次确认无效时才尝试取消兜底
        if confirm_items and cancel_items:
            # 以弹窗区域内全部文本作为弹窗标识，换了弹窗就重新计数，避免计数跨弹窗累加后误点取消
            dialog_key = tuple(sorted(item.data.strip() for item in ocr_result_list))
            if dialog_key != self._last_dialog_key:
                self._last_dialog_key = dialog_key
                self._dialog_confirm_times = 0
            if self._dialog_confirm_times < 3:
                target = confirm_items[0]
                self._dialog_confirm_times += 1
            else:
                target = cancel_items[0]
            self.ctx.controller.click(target.center)
            return self.round_retry(status=f'点击双选弹窗 {target.data}', wait=1.5)

        # 单按钮居中弹窗：直接点击确认/知道了
        if confirm_items:
            target = confirm_items[0]
            self.ctx.controller.click(target.center)
            return self.round_retry(status=f'点击确认弹窗 {target.data}', wait=1.5)

        # 仅有取消按钮
        if cancel_items:
            target = cancel_items[0]
            self.ctx.controller.click(target.center)
            return self.round_retry(status=f'点击取消弹窗 {target.data}', wait=1.5)

        return None

    def _handle_any_dialogue(self, screen: MatLike) -> OperationRoundResult | None:
        """
        检查并推进任何处于大世界中的剧情/NPC对话（包括好感度事件、吼吼先生等NPC对话）。
        """
        if screen is None or screen.size == 0:
            return None

        # 若界面存在通用的返回或关闭按钮，说明正处于菜单、编队或详情页面，绝非大世界NPC对话
        back_btn = self.round_by_find_area(screen, '画面-通用', '返回')
        if back_btn.is_success:
            return None
        close_btn = self.round_by_find_area(screen, '画面-通用', '关闭')
        if close_btn.is_success:
            return None

        # 若小地图存在，说明已处于大世界正常行动状态，绝非对话状态
        mini_map = self.ctx.world_patrol_service.cut_mini_map(screen)
        if mini_map is not None and getattr(mini_map, 'play_mask_found', False):
            return None

        # 1. 检查底部剧情字幕/对话框（是否有灰度遮罩或正在说话的文本）
        dialogue_text_rect = Rect(400, 770, 1520, 980)
        has_gray_mask = cv2_utils.is_in_gray_mask(screen, rect=dialogue_text_rect)
        text_ocr = self.ctx.ocr_service.get_ocr_result_list(screen, rect=dialogue_text_rect, crop_first=False)
        has_dialogue_text = any(str_utils.with_chinese(i.data) or len(i.data.strip()) > 3 for i in text_ocr)
        # 菜单、战斗等画面底部也可能有中文 只有底部文字不能说明处于对话 需同时有对话框灰色遮罩
        is_dialogue_active = has_gray_mask and has_dialogue_text

        # 2. 检查右侧对话选项区域
        options_rect = Rect(1400, 480, 1920, 850)
        options_ocr = self.ctx.ocr_service.get_ocr_result_list(screen, rect=options_rect, crop_first=False)
        valid_options = []
        if options_ocr and len(options_ocr) > 0:
            for item in options_ocr:
                if item.center.y <= 500:
                    continue
                t = item.data.strip()
                # 排除非对话选项：纯数字、等级标识、槽位分数、单字符等
                if len(t) < 2 or len(t) > 30:
                    continue
                if re.match(r'^(等级.*|Lv\.?.*|\d+/\d+|\d+P?|[0-9\W_]+|SE\w*)$', t, re.IGNORECASE):
                    continue
                valid_options.append(item)

        # 选项必须有对话特征（标记符如 ▶ / 「 / 」，或者底部对话框处于活跃状态），防止误点街景文字
        dialogue_markers = ['▶', '◀', '「', '」', '『', '』', '►', '>', '·', '•']
        has_marked_option = any(any(m in item.data for m in dialogue_markers) for item in valid_options)

        if valid_options and (is_dialogue_active or has_marked_option):
            self.last_dialog_idx = (self.last_dialog_idx + 1) % len(valid_options)
            chosen = valid_options[self.last_dialog_idx]
            self.ctx.controller.click(chosen.center)
            return self.round_retry(status=f'点击对话选项 {chosen.data}', wait=1)

        # 底部有字幕/遮罩但无右侧选项：推进剧情对话
        if is_dialogue_active:
            self.ctx.controller.click(Point(960, 880))
            return self.round_retry(status='推进剧情对话', wait=0.5)

        return None

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
        ocr_result_map = self.ctx.ocr.crop_and_run_ocr(screen, area.rect)
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


def _debug() -> None:
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    op = BackToNormalWorld(ctx)
    op.execute()


if __name__ == '__main__':
    _debug()
