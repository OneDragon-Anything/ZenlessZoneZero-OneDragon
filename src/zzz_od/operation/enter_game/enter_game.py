import time
from typing import Optional

from cv2.typing import MatLike

from one_dragon.base.config.basic_game_config import TypeInputWay
from one_dragon.base.config.game_account_config import GameRegionEnum
from one_dragon.base.config.one_dragon_config import InstanceRun
from one_dragon.base.controller.pc_clipboard import PcClipboard
from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class EnterGame(ZOperation):

    def __init__(self, ctx: ZContext, switch: bool = False):
        ZOperation.__init__(self, ctx,
                            op_name=gt('进入游戏')
                            )

        self.force_login: bool = (self.ctx.one_dragon_config.instance_run == InstanceRun.ALL.value.value
            and len(self.ctx.one_dragon_config.instance_list_in_od) > 1)

        # 切换账号的情况下 一定需要登录
        if switch:
            self.force_login = True

        self.already_login: bool = False  # 是否已经登录了
        self.use_clipboard: bool = self.ctx.game_config.type_input_way == TypeInputWay.CLIPBOARD.value.value  # 使用剪切板输入

    @node_from(from_name='国服-输入账号密码')
    @node_from(from_name='国服-输入账号密码-新')
    @node_from(from_name='B服-输入账号密码')
    @node_from(from_name='国际服-换服')
    @operation_node(name='画面识别', node_max_retry_times=60, is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        screen = self.screenshot()

        login_result = self.check_login_related(screen)
        if login_result is not None:
            return login_result

        interact_result = self.check_screen_to_interact(screen)
        if interact_result is not None:
            return interact_result

        in_game_result = self.round_by_find_area(screen, '大世界', '信息')
        if in_game_result.is_success:
            return self.round_success('大世界', wait=1)

        return self.round_retry(status='未知画面', wait=1)

    def check_login_related(self, screen: MatLike) -> Optional[OperationRoundResult]:
        """
        判断登陆相关的出现内容
        :param screen: 游戏画面
        :return: 是否有相关操作 有的话返回对应操作结果
        """
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
                return self.round_wait(result.status, wait=5)

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

        if self.ctx.game_account_config.game_region != GameRegionEnum.CN.value.value:
            return self.check_screen_intl(screen)

        return None

    def check_screen_intl(self, screen: MatLike) -> Optional[OperationRoundResult]:
        result = self.round_by_find_area(screen, '打开游戏', '国际服-点击登录')
        if result.is_success:
            time.sleep(2)  # 已登录的状态也可能出现几秒“点击登录”
            result = self.round_by_find_and_click_area(screen, '打开游戏', '国际服-点击登录')
            if result.is_success:
                return self.round_wait(result.status, wait=1)

        # 未登录时会直接弹出登录窗口
        result = self.round_by_find_area(screen, '打开游戏', '国际服-密码输入区域')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        return None

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

    def check_screen_to_interact(self, screen: MatLike) -> Optional[OperationRoundResult]:
        """
        判断画面 处理可能出现的需要交互的情况
        :param screen: 游戏画面
        :return: 是否有相关操作 有的话返回对应操作结果
        """
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        back_btn_result = self.round_by_find_area(screen, '菜单', '返回')

        target_word_list: list[str] = [
            '取消',  # 上一次战斗还没结束 出现是否继续的对话框 issue #957 '确定'/'确认' 要放在'取消'之后 因为有对话框同时出现这两个词
            '确认',  # 每个版本出现的10连抽奖励 点击领取后确认
            '领取',  # 每个版本出现的10连抽奖励 issue #893
            '已领取',  # 需要有这个词 防止画面出现"已领取"也匹配到"领取"
            '待领取',  # 需要有这个词 防止画面出现"待领取"也匹配到"领取"
            '确定',  # 游戏更新时出现的确定按钮 issue #991
            '重试',  # 登陆时可能出现登陆超时问题 merge request #886
            '今日到账'  # 小月卡 issue #893
        ]
        ignore_list: list[str] = [
            '已领取',
            '待领取',
        ]
        target_word_idx_map: dict[str, int] = {}
        to_match_list: list[str] = []
        for idx, target_word in enumerate(target_word_list):
            target_word_idx_map[target_word] = idx
            to_match_list.append(gt(target_word, 'game'))

        match_word, match_word_mrl = ocr_utils.match_word_list_by_priority(
            ocr_result_map,
            target_word_list,
            ignore_list=ignore_list
        )
        if match_word is not None and match_word_mrl is not None and match_word_mrl.max is not None:
            self.ctx.controller.click(match_word_mrl.max.center)
            return self.round_wait(status=match_word, wait=1)

        if back_btn_result.is_success:
            # 左上角的返回
            self.round_by_click_area('菜单', '返回')
            return self.round_wait(status=back_btn_result.status, wait=1)

        # 一周年自选奖励 应该在2.1时候删除相关资源
        annual_reward_result = self.round_by_find_and_click_area(screen, '打开游戏', '一周年自选奖励')
        if annual_reward_result.is_success:
            return self.round_wait(status=annual_reward_result.status, wait=1)

        return None


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.start_running()
    ctx.init_ocr()
    op = EnterGame(ctx, switch=False)
    op.execute()


if __name__ == '__main__':
    __debug()
