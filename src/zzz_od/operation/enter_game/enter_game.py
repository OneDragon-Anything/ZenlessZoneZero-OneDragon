import time

from one_dragon.base.config.basic_game_config import TypeInputWay
from one_dragon.base.config.game_account_config import GameRegionEnum
from one_dragon.base.config.one_dragon_config import InstanceRun
from one_dragon.base.controller.pc_clipboard import PcClipboard
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.zzz_operation import ZOperation


class EnterGame(ZOperation):

    def __init__(self, ctx: ZContext, switch: bool = False):
        ZOperation.__init__(self, ctx,
                            op_name=gt('进入游戏', 'ui')
                            )

        self.force_login: bool = (self.ctx.one_dragon_config.instance_run == InstanceRun.ALL.value.value
            and len(self.ctx.one_dragon_config.instance_list_in_od) > 1)

        # 切换账号的情况下 一定需要登录
        if switch:
            self.force_login = True

        self.already_login: bool = False  # 是否已经登录了
        self.use_clipboard: bool = self.ctx.game_config.type_input_way == TypeInputWay.CLIPBOARD.value.value  # 使用剪切板输入

    @node_from(from_name='国服-输入账号密码')
    @node_from(from_name='B服-输入账号密码')
    @node_from(from_name='国际服-换服')
    @operation_node(name='画面识别', node_max_retry_times=60, is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        screen = self.screenshot()

        if self.force_login and not self.already_login:
            result = self.round_by_find_area(screen, '打开游戏', '点击进入游戏')
            if result.is_success:
                self.round_by_click_area('打开游戏', '切换账号')
                return self.round_wait(result.status, wait=1)

            result = self.round_by_find_and_click_area(screen, '打开游戏', '切换账号确定')
            if result.is_success:
                return self.round_wait(result.status, wait=5)
        else:
            result = self.round_by_find_and_click_area(screen, '打开游戏', '点击进入游戏')
            if result.is_success:
                return self.round_success(result.status, wait=5)

        result = self.round_by_find_area(screen, '打开游戏', '标题-退出登录')
        if result.is_success:
            result2 = self.round_by_find_and_click_area(screen, '打开游戏', '按钮-退出登录-确定')
            if result2.is_success:
                return self.round_wait(result2.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '打开游戏', '国服-账号密码')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '打开游戏', '国服-账号密码-新')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '打开游戏', '按钮-登陆其他账号')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '打开游戏', 'B服-登陆')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '打开游戏', '重试')
        if result.is_success:
            return self.round_wait(result.status, wait=5)

        if self.ctx.game_account_config.game_region != GameRegionEnum.CN.value.value:
            return self.check_screen_intl()

        return self.round_retry(wait=1)

    def check_screen_intl(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '打开游戏', '国际服-点击登录')
        if result.is_success:
            time.sleep(2) # 已登录的状态也可能出现几秒“点击登录”
            result = self.round_by_find_and_click_area(screen, '打开游戏', '国际服-点击登录')
            if result.is_success:
                return self.round_wait(result.status, wait=1)

        # 未登录时会直接弹出登录窗口
        result = self.round_by_find_area(screen, '打开游戏', '国际服-密码输入区域')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        return self.round_retry(wait=1)

    @node_from(from_name='画面识别', status='国服-账号密码')
    @operation_node(name='国服-输入账号密码')
    def input_account_password(self) -> OperationRoundResult:
        if self.ctx.game_account_config.account == '' or self.ctx.game_account_config.password == '':
            return self.round_fail('未配置账号密码')

        self.round_by_click_area('打开游戏', '国服-账号输入区域')
        time.sleep(0.5)
        if self.use_clipboard:
            PcClipboard.copy_and_paste(self.ctx.game_account_config.account)
        else:
            self.ctx.controller.keyboard_controller.keyboard.type(self.ctx.game_account_config.account)
        time.sleep(1.5)

        self.round_by_click_area('打开游戏', '国服-密码输入区域')
        time.sleep(0.5)
        if self.use_clipboard:
            PcClipboard.copy_and_paste(self.ctx.game_account_config.password)
        else:
            self.ctx.controller.keyboard_controller.keyboard.type(self.ctx.game_account_config.password)
        time.sleep(1.5)

        self.round_by_click_area('打开游戏', '国服-同意按钮')
        time.sleep(0.5)

        screen = self.screenshot()
        self.already_login = True
        return self.round_by_find_and_click_area(screen, '打开游戏', '国服-账号密码进入游戏',
                                                 success_wait=5, retry_wait=1)

    @node_from(from_name='画面识别', status='国服-账号密码-新')
    @operation_node(name='国服-输入账号密码-新')
    def input_account_password_new(self) -> OperationRoundResult:
        """
        1.6版本后 部分账号灰度了保留账号记录的功能
        所有按钮跟原来的有偏差
        @return:
        """
        if self.ctx.game_account_config.account == '' or self.ctx.game_account_config.password == '':
            return self.round_fail('未配置账号密码')

        self.round_by_click_area('打开游戏', '国服-账号输入区域-新')
        time.sleep(0.5)
        if self.use_clipboard:
            PcClipboard.copy_and_paste(self.ctx.game_account_config.account)
        else:
            self.ctx.controller.keyboard_controller.keyboard.type(self.ctx.game_account_config.account)
        time.sleep(1.5)

        self.round_by_click_area('打开游戏', '国服-密码输入区域-新')
        time.sleep(0.5)
        if self.use_clipboard:
            PcClipboard.copy_and_paste(self.ctx.game_account_config.password)
        else:
            self.ctx.controller.keyboard_controller.keyboard.type(self.ctx.game_account_config.password)
        time.sleep(1.5)

        self.round_by_click_area('打开游戏', '国服-同意按钮-新')
        time.sleep(0.5)

        screen = self.screenshot()
        self.already_login = True
        return self.round_by_find_and_click_area(screen, '打开游戏', '国服-账号密码进入游戏-新',
                                                 success_wait=5, retry_wait=1)

    @node_from(from_name='画面识别', status='B服-登陆')
    @operation_node(name='B服-输入账号密码')
    def input_bilibili_account_password(self) -> OperationRoundResult:
        if self.ctx.game_account_config.account == '' or self.ctx.game_account_config.password == '':
            return self.round_fail('未配置账号密码')

        self.round_by_click_area('打开游戏', 'B服-账号输入区域')
        time.sleep(0.5)
        self.round_by_click_area('打开游戏', 'B服-账号删除区域')
        time.sleep(0.5)
        if self.use_clipboard:
            PcClipboard.copy_and_paste(self.ctx.game_account_config.account)
        else:
            self.ctx.controller.keyboard_controller.keyboard.type(self.ctx.game_account_config.account)
        time.sleep(1.5)

        self.round_by_click_area('打开游戏', 'B服-密码输入区域')
        time.sleep(0.5)
        for _ in range(30):
            self.ctx.controller.btn_controller.tap('backspace')
        time.sleep(2)
        # return self.round_fail()
        if self.use_clipboard:
            PcClipboard.copy_and_paste(self.ctx.game_account_config.password)
        else:
            self.ctx.controller.keyboard_controller.keyboard.type(self.ctx.game_account_config.password)
        time.sleep(1.5)

        # self.round_by_click_area('打开游戏', 'B服-同意按钮')
        # time.sleep(0.5)

        screen = self.screenshot()
        self.already_login = True
        return self.round_by_find_and_click_area(screen, '打开游戏', 'B服-登陆',
                                                 success_wait=5, retry_wait=1)

    @node_from(from_name='画面识别', status='国际服-密码输入区域')
    @operation_node(name='国际服-输入账号密码')
    def input_account_password_intl(self) -> OperationRoundResult:
        if self.ctx.game_account_config.account == '' or self.ctx.game_account_config.password == '':
            return self.round_fail('未配置账号密码')

        self.round_by_click_area('打开游戏', '国际服-账号输入区域')
        time.sleep(0.5)
        if self.use_clipboard:
            PcClipboard.copy_and_paste(self.ctx.game_account_config.account)
        else:
            self.ctx.controller.keyboard_controller.keyboard.type(self.ctx.game_account_config.account)
        time.sleep(1.5)

        self.round_by_click_area('打开游戏', '国际服-密码输入区域')
        time.sleep(0.5)
        if self.use_clipboard:
            PcClipboard.copy_and_paste(self.ctx.game_account_config.password)
        else:
            self.ctx.controller.keyboard_controller.keyboard.type(self.ctx.game_account_config.password)
        time.sleep(1.5)

        screen = self.screenshot()
        self.already_login = True

        return self.round_by_find_and_click_area(screen, '打开游戏', '国际服-账号密码进入游戏',
                                                 success_wait=1)

    @node_from(from_name='国际服-输入账号密码', status='国际服-账号密码进入游戏')
    @operation_node(name='国际服-换服')
    def check_server(self) -> OperationRoundResult:
        self.round_by_click_area('打开游戏', '国际服-换服', success_wait=1)

        game_region = self.ctx.game_account_config.game_region
        if game_region == GameRegionEnum.EUROPE.value.value:
            area_name = '国际服-换服-欧洲'
        elif game_region == GameRegionEnum.AMERICA.value.value:
            area_name = '国际服-换服-美国'
        elif game_region == GameRegionEnum.ASIA.value.value:
            area_name = '国际服-换服-亚洲'
        else:
            area_name = '国际服-换服-港澳台'

        # 滑动
        area = self.ctx.screen_loader.get_area('打开游戏', '国际服-换服-美国')
        start = area.center
        end = start + Point(0, 200)
        self.ctx.controller.drag_to(start=start, end=end)
        time.sleep(1)

        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '打开游戏', area_name, success_wait=1)

    @node_from(from_name='画面识别', status='点击进入游戏')
    @operation_node(name='等待画面加载')
    def wait_game(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.start_running()
    ctx.ocr.init_model()
    op = EnterGame(ctx, switch=True)
    op.execute()


if __name__ == '__main__':
    __debug()
