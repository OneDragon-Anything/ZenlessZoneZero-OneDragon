import time
from collections import deque

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.base.operation.one_dragon_context import ContextKeyboardEventEnum
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
)
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.commission_assistant import commission_assistant_const
from zzz_od.application.commission_assistant.commission_assistant_config import (
    CommissionAssistantConfig,
    DialogOptionEnum,
    StoryMode,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.operation.wait_normal_world import WaitNormalWorld


class CommissionAssistantApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=commission_assistant_const.APP_ID,
            op_name=commission_assistant_const.APP_NAME,
        )
        self.config: CommissionAssistantConfig = self.ctx.run_context.get_config(
            app_id=commission_assistant_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        # self.last_recorded_time: float = self.last_screenshot_time  # 用于性能分析
        self.withered_domain_inited: bool = False  # 空洞初始化标志

        self.run_mode: int = 0  # 0=对话 1=闪避 2=自动战斗

        self.last_dialog_opts: set[str] = set()  # 上一次对话的全部选项

        self.chosen_opt_history_max_len: int = 4
        self.chosen_opt_history: deque[str] = deque(maxlen=self.chosen_opt_history_max_len)  # 如果一直卡在选择选项, 记录选择的对话选项历史记录

        self.fishing_btn_pressed: str | None = None  # 钓鱼在按下的按键
        self.fishing_done: bool = False  # 钓鱼是否结束 通常是比赛类 最后会有挑战结果显示
        self.is_skip_in_main_story: bool = False  # 跳过主线时, 添加一个标记 以加快ocr效率和增加代码可读性
        self.option_click_interval_min = max(self.config.OPTION_CLICK_INTERVAL_MIN,
                                             self.config.dialog_click_interval)  # 选项的最小点击间隔(需要等待点击动画结束)
        self.dialog_clicked: bool = False  # 有些对话框内容为'......', ocr不识别, 故引进这个参数, 使得结束对话框点击之后的3次识别不到任何内容时也点击屏幕

    def handle_init(self):
        self._listen_btn()

    def _unlisten_btn(self) -> None:
        self.ctx.unlisten_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)

    def _listen_btn(self) -> None:
        self.ctx.listen_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)

    def _on_key_press(self, event: ContextEventItem):
        if not self.ctx.run_context.is_context_running:
            return
        key = event.data
        if key == self.config.dodge_switch:
            if self.run_mode == 0:
                self.run_mode = 1
            else:  # 防止并发有问题导致值错乱 最后兜底成初始值
                self.run_mode = 0
        elif key == self.config.auto_battle_switch:
            if self.run_mode == 0:
                self.run_mode = 2
            else:  # 防止并发有问题导致值错乱 最后兜底成初始值
                self.run_mode = 0

    @node_from(from_name='委托助手')
    @node_from(from_name='自动战斗模式')
    @node_from(from_name='剧情模式')
    @node_from(from_name='未知画面')
    @node_from(from_name='钓鱼')
    @node_from(from_name='钓鱼', success=False)
    @operation_node(name='委托助手', is_start_node=True)
    def dialog_mode(self) -> OperationRoundResult:
        if self.run_mode in [1, 2]:
            self._load_auto_op()
            return self.round_success('战斗模式')

        result = self.round_by_find_and_click_area(self.screenshot(), '委托助手', '对话框确认', pre_delay=0)
        if result.is_success:
            # 一些对话时出现确认
            return self.round_wait(result.status, wait=0.1)

        # start = datetime.now()

        # 邀约同行移动时 下面的current_screen会识别不到
        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
        if result.is_success:
            return self.round_wait(status='战斗画面-按键-交互', wait=1)

        current_screen = self.check_and_update_current_screen(screen_name_list=['大世界-普通', '大世界-勘域'])
        if current_screen is not None:
            return self.round_wait(status=current_screen, wait=1)

        # 判断二级菜单
        result = self.round_by_find_area(self.last_screenshot, '委托助手', '左上角返回')
        if result.is_success:
            return self.round_wait('处于二级界面, 等待用户操作', wait=1)

        # 判断是否在空洞中
        result = hollow_event_utils.check_in_hollow(self.ctx, self.last_screenshot)
        if result is not None:
            result = self._handle_hollow(self.last_screenshot_time)
            return self.round_wait(result.status, wait=0.5)

        # 判断是否空洞内完成
        result = self.round_by_find_and_click_area(self.last_screenshot, '零号空洞-事件', '通关-完成', pre_delay=0)
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        # elapsed = timedelta.total_seconds(datetime.now() - start)
        # log.debug('判断游戏模式耗时: ' + str(elapsed))

        # 剧情模式 以及一些检测优先级在剧情模式之后的界面
        return self.round_success('检测剧情模式')

    def _do_dialog_click(self, check_center_words: bool = True) -> OperationRoundResult:
        """
        普通的对话点击：选项、对话框标题/中间区域
        """
        if self._click_dialog_options(self.last_screenshot, '右侧选项区域',
                                      color_range=[[240, 240, 240], [255, 255, 255]]):
            return self.round_wait(status='点击右方选项', wait=self.option_click_interval_min)

        center_area = self.ctx.screen_loader.get_area('委托助手', '中间选项区域')
        if not check_center_words:
            # 不检查中间的字, 但是识别中间区域是否为黑屏, 黑屏就点. 适用于跳过剧情
            # 这种检测方式不会在中间为花色区域时抢鼠标导致需要暂停才能手动与游戏交互
            center_image, _ = cv2_utils.crop_image(self.last_screenshot, center_area.rect)
            if not cv2_utils.is_colorful(center_image, saturation_threshold=1, color_ratio_threshold=0.01):
                self.ctx.controller.click(pos=center_area.left_top)
                return self.round_wait(status='黑屏点击中间区域', wait=self.config.dialog_click_interval)
        elif self._click_dialog_options(self.last_screenshot, '中间选项区域',
                                        color_range=[[240, 240, 240], [255, 255, 255]]):
            # 中间有白色的字, 一般是主线的中间选项
            return self.round_wait(status='点击中间选项', wait=self.option_click_interval_min)

        # 对话框检测和处理 (右上角有主线标志且识别不到对话框内容时大概率是对话框出现'......'了)
        with_dialog = self._check_dialog(self.last_screenshot)
        if with_dialog or (
                self.check_main_story() and self.config.story_mode != StoryMode.SKIP.value.value):
            # 因为前面的检测也需要时间, 所以这里的点击需要尽可能快, 不然跳过效果在视觉上就慢了
            self.ctx.controller.click(pos=center_area.left_top, press_time=0.001, low_delay=True)
            self.dialog_clicked = True
            return self.round_wait(status='对话中点击空白', wait=self.config.dialog_click_interval)

        # 对话框替换期间或者对话内容为 '......' 时是无法识别出内容的
        # 如果前几帧识别到对话框则需要继续点击屏幕, 但是不能一直点, 所以这里是retry
        if self.dialog_clicked:
            self.ctx.controller.click(pos=center_area.left_top, press_time=0.001, low_delay=True)
            return self.round_retry(status='点击未知画面 (对话后)', wait=0.2)
        else:
            return self.round_retry(status='未知画面', wait=0.2)

    def _check_dialog(self, screen: MatLike) -> bool:
        """
        识别当前是否有对话
        """
        # 对话框内容不为黑白配色, 不是对话
        area = self.ctx.screen_loader.get_area('委托助手', '对话框内容')
        if not cv2_utils.is_in_gray_mask(screen, rect=area.rect):
            return False

        # 检测对话框中的中文 (字刚蹦出来的时候是灰色所以不能加rgb颜色蒙版)
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            image=screen,
            rect=area.rect
        )
        for ocr_result in ocr_result_list:
            if str_utils.with_chinese(ocr_result.data):
                return True
        return False

    def _click_dialog_options(self, screen: MatLike, area_name: str,
                              color_range: list[list[int]] | None = None) -> bool:
        """
        点击对话选项
        """
        area = self.ctx.screen_loader.get_area('委托助手', area_name)
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            image=screen,
            rect=area.rect,
            color_range=color_range
        )
        if len(ocr_result_list) == 0:
            return False

        to_click: Point | None = None
        to_choose_opt: str | None = None

        for mr in ocr_result_list:
            opt_point = mr.center

            if len(self.chosen_opt_history) == self.chosen_opt_history_max_len \
                    and mr.data == self.chosen_opt_history[0] \
                    and self.check_same_opts(set([i.data for i in ocr_result_list])):
                # 忽略一直选择但是仍然存在的选项
                continue

            if self.config.dialog_option == DialogOptionEnum.LAST.value.value:
                if to_click is None or opt_point.y > to_click.y:  # 最后一个选项 找y轴最大的
                    to_click = opt_point
                    to_choose_opt = mr.data
            else:
                if to_click is None or opt_point.y < to_click.y:  # 第一个选项 找y轴最小的
                    to_click = opt_point
                    to_choose_opt = mr.data

        if to_click is None:
            return False
        self.chosen_opt_history.append(to_choose_opt)
        self.ctx.controller.click(to_click)
        return True

    def check_same_opts(self, ocr_results: set[str]) -> bool:
        """
        @param ocr_results: 本次对话选项
        @return: 判断跟上一次对话选项是否完全一致
        """
        is_same: bool = True
        if len(self.last_dialog_opts) != len(ocr_results):
            is_same = False
        else:
            for ocr_result in ocr_results:
                if ocr_result not in self.last_dialog_opts:
                    is_same = False
                    break

        if not is_same:
            self.last_dialog_opts.clear()
            for ocr_result in ocr_results:
                self.last_dialog_opts.add(ocr_result)

        return is_same

    def _handle_hollow(self, screenshot_time: float) -> OperationRoundResult:
        """
        处理在空洞里的情况
        :param screen: 游戏画面
        :param screenshot_time: 截图时间
        """
        # 空洞内不好处理事件
        # return self.round_wait(status='空洞中', wait=1) # Original line, commented out as per previous logic.
        self.ctx.withered_domain.map_service.init_event_yolo()
        if not self.withered_domain_inited:
            self.ctx.withered_domain.init_before_run()
            self.withered_domain_inited = True

        # 判断当前邦布是否存在
        hollow_map = self.ctx.withered_domain.map_service.cal_current_map_by_screen(self.last_screenshot, screenshot_time)
        if hollow_map is None or hollow_map.contains_entry('当前'):
            return self.round_wait(status='空洞走格子中', wait=1)

        # 处理对话
        return hollow_event_utils.check_event_text_and_run(self, self.last_screenshot, [])

    def check_game_tutorial(self) -> OperationRoundResult:
        """
        判断是否在玩法引导中
        """
        area = self.ctx.screen_loader.get_area('委托助手', '玩法引导')
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(image=self.last_screenshot, rect=area.rect)
        for mr in ocr_result_list:
            if mr.data in ['战斗引导', '玩法引导']:
                # 战斗引导不作处理, 等待用户点击
                return self.round_success(mr.data)
        return self.round_fail()

    def check_knock_knock(self) -> OperationRoundResult:
        """
        判断是否在短信中
        """
        result = self.round_by_find_area(self.last_screenshot, '委托助手', '标题-短信')
        if not result.is_success:
            return result

        area = self.ctx.screen_loader.get_area('委托助手', '区域-短信-文本框')
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(image=self.last_screenshot, rect=area.rect)
        bottom_text: str | None = None  # 最下方的文本
        bottom_mr: MatchResult | None = None  # 找到最下方的文本进行点击
        for mr in ocr_result_list:
            if bottom_mr is None or mr.center.y > bottom_mr.center.y:
                bottom_mr = mr
                bottom_text = mr.data

        if bottom_mr is None:
            return self.round_fail()

        if '以上为最新' in bottom_text:
            return self.round_by_find_and_click_area(self.last_screenshot, '委托助手', '按钮-短信-关闭')

        self.ctx.controller.click(bottom_mr.center)
        return self.round_success(bottom_text)

    @node_from(from_name='委托助手', status='战斗模式')
    @operation_node(name='自动战斗模式')
    def auto_mode(self) -> OperationRoundResult:
        if self.run_mode == 0:
            self.ctx.auto_battle_context.stop_auto_battle()
            return self.round_success()

        self.ctx.auto_battle_context.check_battle_state(self.last_screenshot, self.last_screenshot_time)

        return self.round_wait(wait_round_time=self.ctx.battle_assistant_config.screenshot_interval)

    def _load_auto_op(self) -> None:
        """
        加载战斗指令
        """
        self.ctx.auto_battle_context.init_auto_op(
            sub_dir='auto_battle' if self.run_mode == 2 else 'dodge',
            op_name=self.config.auto_battle if self.run_mode == 2 else self.config.dodge_config
        )
        self.ctx.auto_battle_context.start_auto_battle()

    def check_fishing(self) -> OperationRoundResult | None:
        """
        判断是否进入钓鱼画面
        - 左上角有返回
        - 出现了抛竿文本
        """
        result = self.round_by_find_area(self.last_screenshot, '钓鱼', '按键-返回')
        if not result.is_success:
            return None

        area = self.ctx.screen_loader.get_area('钓鱼', '指令文本区域')
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            image=self.last_screenshot,
            rect=area.rect
        )
        ocr_word_list = [i.data for i in ocr_result_list]
        if str_utils.find_best_match_by_difflib(gt('点击按键抛竿', 'game'), ocr_word_list) is None:
            return None

        self.fishing_done = False
        self.ctx.controller.mouse_move(area.left_top)  # 移开鼠标 防止遮挡指令
        return self.round_success('钓鱼', wait=0.1)

    def check_main_story(self) -> bool:
        """
        判断是否进入了剧情模式 右上角有 菜单/跳过/自动
        """
        area = self.ctx.screen_loader.get_area('委托助手', '文本-剧情右上角')
        ocr_result_map = self.ctx.ocr_service.get_ocr_result_map(
            image=self.last_screenshot,
            rect=area.rect
        )
        keywords = ['菜单', '跳过', '自动']
        match_word, _ = ocr_utils.match_word_list_by_priority(ocr_result_map, keywords)
        if match_word is not None:
            return True
        return False

    @node_from(from_name='委托助手', status='检测剧情模式')
    @operation_node(name='剧情模式', node_max_retry_times=5)
    def story_mode(self) -> OperationRoundResult:
        """
        剧情模式：右上角有 菜单/自动/跳过（点击前后显隐性或位置性会改变）
        """
        # 如果按快捷键键切换了别的模式, 跳出循环
        if self.run_mode != 0:
            return self.round_success('切换自动对话模式')
        # log.debug('@@@@@@@@@@@@@@循环耗时:%2f', self.last_screenshot_time - self.last_recorded_time)
        # self.last_recorded_time = self.last_screenshot_time

        area = self.ctx.screen_loader.get_area('委托助手', '文本-剧情右上角')

        # 自动播放模式
        if self.config.story_mode == StoryMode.AUTO.value.value:
            # 优先通过模板定位Y轴，再点击中间选项（模板位置点击无反应）
            result = self.round_by_find_and_click_area(self.last_screenshot, '委托助手', '中间选项区域', center_x=True,
                                                       pre_delay=0)
            if result.is_success:
                return self.round_wait('点击中间选项', wait=self.option_click_interval_min)
            # 文本-剧情右上角，里面显示'自动'
            result = self.round_by_ocr(self.last_screenshot, '自动', area=area)
            if result.is_success:
                # 自动播剧情, 1秒检测一次
                return self.round_wait('剧情自动播放中', wait=1)
            # 文本-剧情右上角，里面显示'菜单'
            result = self.round_by_ocr_and_click(self.last_screenshot, '菜单', area=area, pre_delay=0)
            if result.is_success:
                # 点完会有动画, 需要等待动画结束不然白点
                return self.round_wait('尝试展开剧情菜单', wait=1)
            # 文本-剧情右上角，下面显示'菜单'（展开菜单后）
            result = self.round_by_find_and_click_area(self.last_screenshot, '委托助手', '按钮-自动', pre_delay=0)
            if result.is_success:
                return self.round_wait('尝试切换到自动模式', wait=0.1)

        # 跳过剧情模式
        if self.config.story_mode == StoryMode.SKIP.value.value:
            # (主线和支线) 识别跳过按钮
            result = self.round_by_ocr_and_click(self.last_screenshot, '跳过', area=area, success_wait=0.1,
                                                 color_range=[[240, 240, 240], [255, 255, 255]])
            if self.is_skip_in_main_story:
                # 主线点击跳过会有动画, 额外等待0.25s, 支线跳过不用等
                time.sleep(0.25)
                self.is_skip_in_main_story = False
            if not result.is_success:
                # (主线) 按优先级处理 跳过/菜单/自动, 不识别遮罩后的按钮
                result = self.round_by_ocr_and_click_by_priority(['菜单', '自动'], area=area, pre_delay=0,
                                                                 color_range=[[240, 240, 240], [255, 255, 255]])
                if result.is_success:
                    self.is_skip_in_main_story = True
                    self.chosen_opt_history.clear()
                    return self.round_wait(f'点击剧情按钮 {result.status}', wait=0.1)

            # 识别跳过后的确认框
            result = self.round_by_find_and_click_area(self.screenshot(), '委托助手', '对话框确认', pre_delay=0)
            if result.is_success:
                self.chosen_opt_history.clear()
                return self.round_wait('跳过剧情', wait=0.1)

        # region 容易和剧情模式穿插的界面, 放在剧情模式之后检测
        # 判断二级菜单
        result = self.round_by_find_area(self.last_screenshot, '委托助手', '左上角返回')
        if result.is_success:
            return self.round_wait('处于二级界面, 等待用户操作', wait=1)
        # 判断玩法引导
        result = self.check_game_tutorial()
        if result.is_success:
            return self.round_wait(result.status, wait=1)
        # 判断短信
        result = self.check_knock_knock()
        if result.is_success:
            return self.round_wait(result.status, wait=0.3)
        # 判断钓鱼
        result = self.check_fishing()
        if result is not None:
            return result

        # 跳过剧情模式：没有'确认'弹窗，说明这个'跳过'是无反馈的灰按钮
        # 跳过剧情模式：文本-剧情右上角，很多情况下是没有内容可点击的
        # 自动点击模式
        result = self._do_dialog_click(check_center_words=(self.config.story_mode != StoryMode.SKIP.value.value))
        # endregion

        return result

    @node_from(from_name='剧情模式', success=False)
    @operation_node(name='未知画面', screenshot_before_round=False)
    def sleep_after_empty_screen_func(self) -> OperationRoundResult:
        # 及时重置这个标记以免一直点屏幕中间
        self.dialog_clicked = False
        return self.round_success('等待重新检测', wait=self.config.sleep_after_empty_screen)

    @node_from(from_name='剧情模式', status='钓鱼')
    @operation_node('钓鱼', node_max_retry_times=50)  # 约5s没识别到指令就退出
    def on_finishing(self) -> OperationRoundResult:
        # 判断当前指令
        area = self.ctx.screen_loader.get_area('钓鱼', '指令文本区域')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        ocr_result_list = list(ocr_result_map.keys())

        target_command_list = [
            gt('点击按键抛竿', 'game'),
            gt('等待上鱼', 'game'),
            gt('正确时机点击按键上鱼', 'game'),
            gt('连点', 'game'),
            gt('长按', 'game'),
        ]
        command_idx, _ = str_utils.find_most_similar(target_command_list, ocr_result_list)

        if command_idx != 4:  # 松开按键
            if self.fishing_btn_pressed == 'd':
                self.ctx.controller.move_d(release=True)
            elif self.fishing_btn_pressed == 'a':
                self.ctx.controller.move_a(release=True)
            self.fishing_btn_pressed = None

        if command_idx is not None:
            self.fishing_done = False

        if command_idx == 0:  # 点击按键抛竿
            self.ctx.controller.interact(press=True, press_time=0.2)
            return self.round_wait(target_command_list[command_idx], wait=0.1)
        elif command_idx == 1:  # 等待上鱼
            return self.round_wait(target_command_list[command_idx], wait=0.1)
        elif command_idx == 2:  # 正确时机点击按键上鱼
            result = self.round_by_find_area(self.last_screenshot, '钓鱼', '按键-时机上鱼')
            if result.is_success:
                self.ctx.controller.interact(press=True, press_time=0.2)
                return self.round_wait(target_command_list[command_idx], wait=0.1)
            else:
                return self.round_wait(target_command_list[command_idx], wait_round_time=0.1)  # 这个要尽快按
        elif command_idx == 3:  # 连点
            power = None
            left = self.round_by_find_area(self.last_screenshot, '钓鱼', '按键-左')
            if left.is_success:
                self.ctx.controller.move_a(press=True, press_time=0.05)
                power = self.round_by_find_area(self.last_screenshot, '钓鱼', '按键-强力-左')
            else:
                self.ctx.controller.move_d(press=True, press_time=0.05)
                power = self.round_by_find_area(self.last_screenshot, '钓鱼', '按键-强力-右')

            if power is not None and power.is_success:
                self.ctx.controller.btn_controller.press(key='space', press_time=0.05)
            return self.round_wait(target_command_list[command_idx], wait_round_time=0.1)  # 这个要尽快按
        elif command_idx == 4:  # 长按
            if self.fishing_btn_pressed is None:
                power = None
                left = self.round_by_find_area(self.last_screenshot, '钓鱼', '按键-左')
                if left.is_success:
                    self.fishing_btn_pressed = 'a'
                    self.ctx.controller.move_a(press=True)
                    power = self.round_by_find_area(self.last_screenshot, '钓鱼', '按键-强力-左')

                right = self.round_by_find_area(self.last_screenshot, '钓鱼', '按键-右')
                if right.is_success:
                    self.fishing_btn_pressed = 'd'
                    self.ctx.controller.move_d(press=True)
                    power = self.round_by_find_area(self.last_screenshot, '钓鱼', '按键-强力-右')

                if power is not None and power.is_success:
                    time.sleep(0.05)  # 稍微等待前面长按 避免按键冲突
                    self.ctx.controller.btn_controller.press(key='space', press_time=0.05)
            return self.round_wait(target_command_list[command_idx], wait_round_time=0.1)

        if command_idx is None:
            result = self.round_by_find_and_click_area(self.last_screenshot, '钓鱼', '按钮-点击空白处关闭')
            if result.is_success:
                return self.round_wait(result.status, wait=0.1)

            result = self.round_by_find_area(self.last_screenshot, '钓鱼', '标题-挑战结果')
            if result.is_success:  # 只判断确定有时候会误判 加上标题
                result = self.round_by_find_and_click_area(self.last_screenshot, '钓鱼', '按钮-确定')
                if result.is_success:
                    self.fishing_done = True
                    return self.round_wait(result.status, wait=0.1)

            if self.fishing_done:
                return self.round_success('钓鱼结束')

            op = WaitNormalWorld(self.ctx, check_once=True)
            result = self.round_by_op_result(op.execute())
            if result.is_success:
                return self.round_success('钓鱼结束')

        return self.round_retry('未识别到指令', wait=0.1)

    def handle_pause(self):
        ZApplication.handle_pause(self)
        self._unlisten_btn()
        if self.run_mode != 0:
            self.ctx.auto_battle_context.stop_auto_battle()

    def handle_resume(self) -> None:
        ZApplication.handle_resume(self)
        self._listen_btn()
        if self.run_mode != 0:
            self.ctx.auto_battle_context.resume_auto_battle()

    def after_operation_done(self, result: OperationResult):
        ZApplication.after_operation_done(self, result)
        self._unlisten_btn()


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = CommissionAssistantApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
