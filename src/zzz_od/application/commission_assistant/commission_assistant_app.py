import time

from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.base.operation.one_dragon_context import ContextKeyboardEventEnum
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult, OperationRoundResultEnum
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.commission_assistant.commission_assistant_config import DialogOptionEnum, StoryMode
from zzz_od.application.zzz_application import ZApplication
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import hollow_event_utils


class CommissionAssistantApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='commission_assistant',
            op_name=gt('委托助手'),
        )

        self.run_mode: int = 0  # 0=对话 1=闪避 2=自动战斗
        self.auto_op: Optional[AutoBattleOperator] = None  # 战斗指令

        self.last_dialog_opts: set[str] = set()  # 上一次对话的全部选项
        self.last_chosen_opt: str = ''  # 上一次选择的对话选项

        self.fishing_btn_pressed: Optional[str] = None  # 钓鱼在按下的按键
        self.fishing_done: bool = False  # 钓鱼是否结束 通常是比赛类 最后会有挑战结果显示

    def handle_init(self):
        self._listen_btn()

    def _unlisten_btn(self) -> None:
        self.ctx.unlisten_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)

    def _listen_btn(self) -> None:
        self.ctx.listen_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)

    def _on_key_press(self, event: ContextEventItem):
        if not self.ctx.is_context_running:
            return
        key = event.data
        if key == self.ctx.commission_assistant_config.dodge_switch:
            if self.auto_op is not None and self.ctx.commission_assistant_config.dodge_config != self.auto_op.module_name:
                self.auto_op = None  # 切换过选项
            if self.run_mode == 0:
                self.run_mode = 1
            elif self.run_mode == 1:
                self.run_mode = 0
            else:  # 防止并发有问题导致值错乱 最后兜底成初始值
                self.run_mode = 0
        elif key == self.ctx.commission_assistant_config.auto_battle_switch:
            if self.auto_op is not None and self.ctx.commission_assistant_config.auto_battle != self.auto_op.module_name:
                self.auto_op = None  # 切换过选项
            if self.run_mode == 0:
                self.run_mode = 2
            elif self.run_mode == 2:
                self.run_mode = 0
            else:  # 防止并发有问题导致值错乱 最后兜底成初始值
                self.run_mode = 0

    @node_from(from_name='自动战斗模式')
    @node_from(from_name='钓鱼')
    @node_from(from_name='钓鱼', success=False)
    @operation_node(name='自动对话模式', is_start_node=True)
    def dialog_mode(self) -> OperationRoundResult:
        if self.run_mode in [1, 2]:
            return self.round_success('战斗模式')

        config = self.ctx.commission_assistant_config
        now = time.time()
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '大世界', '信息')
        if result.is_success:
            return self.round_wait(status='大世界', wait=1)

        result = self.round_by_find_area(screen, '委托助手', '左上角返回')
        # 很多二级菜单都有这个按钮
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        result = self.round_by_find_area(screen, '委托助手', '对话框确认')
        # 一些对话时出现确认
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        # 判断是否在空洞中
        result = hollow_event_utils.check_in_hollow(self.ctx, screen)
        if result is not None:
            return self._handle_hollow(screen, now)

        # 判断是否空洞内完成
        result = self.round_by_find_and_click_area(screen, '零号空洞-事件', '通关-完成')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        # 判断短信
        result = self.check_knock_knock(screen)
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        # 判断钓鱼
        result = self.check_fishing(screen)
        if result is not None:
            return result

        # 剧情模式
        result = self.check_story_mode(screen)
        if result is not None:
            return result

        if self._click_dialog_options(screen, '右侧选项区域'):
            return self.round_wait(status='点击右方选项',
                                   wait=config.dialog_click_interval)

        if self._click_dialog_options(screen, '中间选项区域'):
            return self.round_wait(status='点击中间选项',
                                   wait=config.dialog_click_interval)

        with_dialog = self._check_dialog(screen)
        if with_dialog:
            self.round_by_click_area('委托助手', '中间选项区域')
            return self.round_wait(status='对话中点击空白',
                                   wait=config.dialog_click_interval)

        self.round_by_click_area('委托助手', '中间选项区域')
        return self.round_wait(status='未知画面点击空白', wait=1)

    def _check_dialog(self, screen: MatLike) -> bool:
        """
        识别当前是否有对话
        """
        area = self.ctx.screen_loader.get_area('委托助手', '对话框标题')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        for ocr_result in ocr_result_map.keys():
            if str_utils.with_chinese(ocr_result):
                return True
        return False

    def _click_dialog_options(self, screen: MatLike, area_name: str) -> bool:
        """
        点击对话选项
        """
        area = self.ctx.screen_loader.get_area('委托助手', area_name)
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        if len(ocr_result_map) == 0:
            return False

        to_click: Optional[Point] = None
        to_choose_opt: Optional[str] = None

        is_same_opts: bool = self.check_same_opts(set(ocr_result_map.keys()))

        for ocr_result, mrl in ocr_result_map.items():
            opt_point = mrl.max.center + area.left_top

            if is_same_opts and ocr_result == self.last_chosen_opt:
                # 忽略上一次一样的选项 这大概率是背景污染
                continue

            if self.ctx.commission_assistant_config.dialog_option == DialogOptionEnum.LAST.value.value:
                if to_click is None or opt_point.y > to_click.y:  # 最后一个选项 找y轴最大的
                    to_click = opt_point
                    to_choose_opt = ocr_result
            else:
                if to_click is None or opt_point.y < to_click.y:  # 第一个选项 找y轴最小的
                    to_click = opt_point
                    to_choose_opt = ocr_result

        self.ctx.controller.click(to_click)
        self.last_chosen_opt = to_choose_opt
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

    def _handle_hollow(self, screen: MatLike, screenshot_time: float) -> OperationRoundResult:
        """
        处理在空洞里的情况
        :param screen: 游戏画面
        :param screenshot_time: 截图时间
        """
        # 空洞内不好处理事件
        return self.round_wait(status='空洞中', wait=1)
        self.ctx.hollow.init_event_yolo(self.ctx.model_config.hollow_zero_event_gpu)

        # 判断当前邦布是否存在
        hollow_map = self.ctx.hollow.map_service.cal_current_map_by_screen(screen, screenshot_time)
        if hollow_map is None or hollow_map.contains_entry('当前'):
            return self.round_wait(status='空洞走格子中', wait=1)

        # 处理对话
        return hollow_event_utils.check_event_text_and_run(self, screen, [])

    def check_knock_knock(self, screen: MatLike) -> OperationRoundResult:
        """
        判断是否在短信中
        :param screen: 游戏画面
        :return:
        """
        result = self.round_by_find_area(screen, '委托助手', '标题-短信')
        if not result.is_success:
            return result

        area = self.ctx.screen_loader.get_area('委托助手', '区域-短信-文本框')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        bottom_text = None  # 最下方的文本
        bottom_mr = None  # 找到最下方的文本进行点击
        for ocr_result, mrl in ocr_result_map.items():
            if bottom_mr is None or mrl.max.center.y > bottom_mr.center.y:
                bottom_mr = mrl.max
                bottom_text = ocr_result

        if bottom_mr is None:
            result.result = OperationRoundResultEnum.FAIL
            return result

        bottom_mr.add_offset(area.left_top)
        self.ctx.controller.click(bottom_mr.center)

        result.status = bottom_text
        return result

    @node_from(from_name='自动对话模式', status='战斗模式')
    @operation_node(name='自动战斗模式')
    def auto_mode(self) -> OperationRoundResult:
        if self.run_mode == 0:
            auto_battle_utils.stop_running(self.auto_op)
            return self.round_success()
        self._load_auto_op()

        now = time.time()

        screen = self.screenshot()
        self.auto_op.auto_battle_context.check_battle_state(screen, now)

        return self.round_wait(wait_round_time=self.ctx.battle_assistant_config.screenshot_interval)

    def _load_auto_op(self) -> None:
        """
        加载战斗指令
        """
        if self.auto_op is None:
            auto_battle_utils.load_auto_op(self,
                                           'auto_battle' if self.run_mode == 2 else 'dodge',
                                           self.ctx.commission_assistant_config.auto_battle if self.run_mode == 2 else self.ctx.commission_assistant_config.dodge_config)
        self.auto_op.start_running_async()

    def check_fishing(self, screen: MatLike) -> Optional[OperationRoundResult]:
        """
        判断是否进入钓鱼画面
        - 左上角有返回
        - 出现了抛竿文本
        @param screen: 游戏画面
        @return:
        """
        result = self.round_by_find_area(screen, '钓鱼', '按键-返回')
        if not result.is_success:
            return None

        area = self.ctx.screen_loader.get_area('钓鱼', '指令文本区域')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        ocr_result_list = list(ocr_result_map.keys())
        if str_utils.find_best_match_by_difflib(gt('点击按键抛竿', 'game'), ocr_result_list) is None:
            return None

        self.fishing_done = False
        self.ctx.controller.mouse_move(area.left_top)  # 移开鼠标 防止遮挡指令
        return self.round_success('钓鱼')

    def check_story_mode(self, screen: MatLike) -> Optional[OperationRoundResult]:
        """
        判断是否进入了剧情模式 右上角有 等待/自动/跳过
        @param screen:
        @return:
        """
        area = self.ctx.screen_loader.get_area('委托助手', '文本-剧情右上角')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)

        target_word_list = [
            gt(i, 'game')
            for i in ['菜单', '自动', '跳过']
        ]

        idx = -1
        for ocr_result in ocr_result_map.keys():
            idx = str_utils.find_best_match_by_difflib(ocr_result, target_word_list, cutoff=1)
            if idx is not None:
                break

        if idx == -1:  # 不在剧情模式
            return None

        if self.ctx.commission_assistant_config.story_mode == StoryMode.CLICK.value.value:
            return None  # 返回外层点击
        elif self.ctx.commission_assistant_config.story_mode == StoryMode.AUTO.value.value:
            if idx == 1:  # 自动
                return self.round_wait('剧情自动播放中 选项需手动点击', wait=1)
            else:  # 切换到自动
                if idx != 0:
                    self.round_by_click_area('委托助手', '文本-剧情右上角', success_wait=1)  # 切换到菜单
                self.round_by_click_area('委托助手', '文本-剧情右上角', success_wait=1)  # 点击菜单
                self.round_by_click_area('委托助手', '按钮-自动', success_wait=1)  # 点击自动
                return self.round_wait('尝试切换到自动模式')
        else:
            if idx != 0:
                self.round_by_click_area('委托助手', '文本-剧情右上角', success_wait=1)  # 切换到菜单
            self.round_by_click_area('委托助手', '文本-剧情右上角', success_wait=1)  # 点击菜单
            self.round_by_click_area('委托助手', '文本-剧情右上角', success_wait=1)  # 点击跳过
            screen2 = self.screenshot()
            result = self.round_by_find_and_click_area(screen2, '委托助手', '对话框确认')
            if result.is_success:
                return self.round_wait('跳过剧情')

    @node_from(from_name='自动对话模式', status='钓鱼')
    @operation_node('钓鱼', node_max_retry_times=50)  # 约5s没识别到指令就退出
    def on_finishing(self) -> OperationRoundResult:
        screen = self.screenshot()

        # 判断当前指令
        area = self.ctx.screen_loader.get_area('钓鱼', '指令文本区域')
        part = cv2_utils.crop_image_only(screen, area.rect)
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
            result = self.round_by_find_area(screen, '钓鱼', '按键-时机上鱼')
            if result.is_success:
                self.ctx.controller.interact(press=True, press_time=0.2)
                return self.round_wait(target_command_list[command_idx], wait=0.1)
            else:
                return self.round_wait(target_command_list[command_idx], wait_round_time=0.1)  # 这个要尽快按
        elif command_idx == 3:  # 连点
            power = None
            left = self.round_by_find_area(screen, '钓鱼', '按键-左')
            if left.is_success:
                self.ctx.controller.move_a(press=True, press_time=0.05)
                power = self.round_by_find_area(screen, '钓鱼', '按键-强力-左')
            else:
                self.ctx.controller.move_d(press=True, press_time=0.05)
                power = self.round_by_find_area(screen, '钓鱼', '按键-强力-右')

            if power is not None and power.is_success:
                self.ctx.controller.btn_controller.press(key='space', press_time=0.05)
            return self.round_wait(target_command_list[command_idx], wait_round_time=0.1)  # 这个要尽快按
        elif command_idx == 4:  # 长按
            if self.fishing_btn_pressed is None:
                power = None
                left = self.round_by_find_area(screen, '钓鱼', '按键-左')
                if left.is_success:
                    self.fishing_btn_pressed = 'a'
                    self.ctx.controller.move_a(press=True)
                    power = self.round_by_find_area(screen, '钓鱼', '按键-强力-左')

                right = self.round_by_find_area(screen, '钓鱼', '按键-右')
                if right.is_success:
                    self.fishing_btn_pressed = 'd'
                    self.ctx.controller.move_d(press=True)
                    power = self.round_by_find_area(screen, '钓鱼', '按键-强力-右')

                if power is not None and power.is_success:
                    time.sleep(0.05)  # 稍微等待前面长按 避免按键冲突
                    self.ctx.controller.btn_controller.press(key='space', press_time=0.05)
            return self.round_wait(target_command_list[command_idx], wait_round_time=0.1)

        if command_idx is None:
            result = self.round_by_find_and_click_area(screen, '钓鱼', '按钮-点击空白处关闭')
            if result.is_success:
                return self.round_wait(result.status, wait=0.1)

            result = self.round_by_find_area(screen, '钓鱼', '标题-挑战结果')
            if result.is_success:  # 只判断确定有时候会误判 加上标题
                result = self.round_by_find_and_click_area(screen, '钓鱼', '按钮-确定')
                if result.is_success:
                    self.fishing_done = True
                    return self.round_wait(result.status, wait=0.1)

            if self.fishing_done:
                return self.round_success('钓鱼结束')

            result = self.round_by_find_area(screen, '大世界-普通', '按钮-信息')
            if result.is_success:
                return self.round_success('钓鱼结束')

        return self.round_retry('未识别到指令', wait=0.1)

    def handle_pause(self):
        ZApplication.handle_pause(self)
        self._unlisten_btn()
        auto_battle_utils.stop_running(self.auto_op)

    def handle_resume(self) -> None:
        ZApplication.handle_resume(self)
        self._listen_btn()
        auto_battle_utils.resume_running(self.auto_op)

    def after_operation_done(self, result: OperationResult):
        ZApplication.after_operation_done(self, result)
        self._unlisten_btn()
        if self.auto_op is not None:
            self.auto_op.dispose()
            self.auto_op = None


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = CommissionAssistantApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()