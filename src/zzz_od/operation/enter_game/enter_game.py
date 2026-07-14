import time
from typing import ClassVar

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.config.basic_game_config import TypeInputWay
from one_dragon.base.config.game_account_config import GameRegionEnum
from one_dragon.base.config.one_dragon_config import InstanceRun
from one_dragon.base.controller.pc_clipboard import PcClipboard
from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
)
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class EnterGame(ZOperation):

    STATUS_GAME_DATA_UPDATED: ClassVar[str] = '游戏数据已更新'
    STATUS_LOGIN_SUCCESS: ClassVar[str] = '登录成功'
    STATUS_LOADING: ClassVar[str] = '加载中'
    MAX_LOADING_SECONDS: ClassVar[float] = 180
    MAX_RESOURCE_DOWNLOAD_SECONDS: ClassVar[float] = 1200

    def __init__(self, ctx: ZContext, switch: bool = False):
        ZOperation.__init__(self, ctx, op_name=gt('进入游戏'))

        self.force_login: bool = (
            self.ctx.one_dragon_config.instance_run == InstanceRun.ALL.value.value
            and len(self.ctx.one_dragon_config.instance_list_in_od) > 1
            or self.ctx.game_account_config.force_login_before_run
        )

        # 切换账号的情况下 一定需要登录
        if switch:
            self.force_login = True

        # 未配置账号密码时，无法主动切换账号，依赖游戏保存的登录状态直接进入
        # switch=True 时前置流程已执行游戏内登出，不能跳过 force_login
        cfg = self.ctx.game_account_config
        if not switch and not cfg.account and not cfg.password and not cfg.bilibili_account_name:
            self.force_login = False

        self.already_login: bool = False  # 是否已经提交账号登录
        self.after_first_enter_click: bool = False  # 是否已经完成第一次进入游戏点击
        self.after_second_enter_click: bool = False  # 是否已经完成加载配置后的第二次进入游戏点击
        self.resource_download_start_time: float | None = None  # 资源下载开始时间
        self.use_clipboard: bool = self.ctx.game_config.type_input_way == TypeInputWay.CLIPBOARD.value.value  # 使用剪切板输入

        self.interact_ignore_word_list: list[str] = []  # 进入游戏时 交互需要忽略的文本

    def handle_init(self):
        # 本OP会被复用 多次登录时重置这个记录
        self.already_login = False
        self.after_first_enter_click = False
        self.after_second_enter_click = False
        self.resource_download_start_time = None
        self.interact_ignore_word_list.clear()

    @node_from(from_name='国服-输入账号密码')
    @node_from(from_name='国服-输入账号密码-新')
    @node_from(from_name='B服新-选择登录过的账号')
    @node_from(from_name='国际服-换服')
    @node_from(from_name='点击进入游戏', status=STATUS_GAME_DATA_UPDATED)
    @node_from(from_name='点击进入游戏', status='切换账号确定')
    @node_from(from_name='画面识别', status='B服新-同意隐私政策')
    @operation_node(name='画面识别', node_max_retry_times=60, is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        # self.screenshot()
        # cv2_utils.show_image(self.last_screenshot, win_name='debug', wait=1)

        if self.last_screenshot is None:
            return self.round_retry('未获取到游戏截图', wait=1)

        data_updated_result = self.check_game_data_updated(self.last_screenshot, back_to_check_screen=False)
        if data_updated_result is not None:
            return data_updated_result

        match_word, _ = self.check_enter_click_status_text(self.last_screenshot)
        if match_word is not None:
            return self.round_success('点击进入游戏', wait=1)

        login_result = self.check_login_related(self.last_screenshot)
        if login_result is not None:
            return login_result

        login_result = self.match_login_error(self.last_screenshot)
        if login_result is not None:
            return login_result

        # 处理国服登录时账号密码输入有误的情况 通过登录按钮文本判断可能没登录成功 尝试返回重试
        result = self.round_by_find_area(self.last_screenshot, '打开游戏', '国服-账号密码进入游戏-新')
        if result.is_success:
            self.round_by_click_area('打开游戏', '国服-返回按钮')
            return self.round_retry(status='返回重试', wait=1)

        return self.round_retry(status='未知画面', wait=1)

    def check_login_related(self, screen: MatLike) -> OperationRoundResult | None:
        """
        判断登陆相关的出现内容
        :param screen: 游戏画面
        :return: 是否有相关操作 有的话返回对应操作结果
        """
        # 先识别国服的退出 '按钮-退出登录-确定', 再识别 'B服新-登录记录'
        result = self.round_by_find_area(screen, '打开游戏', '标题-退出登录')
        if result.is_success:
            result2 = self.round_by_find_and_click_area(screen, '打开游戏', '按钮-退出登录-确定')
            if result2.is_success:
                return self.round_wait(result2.status, wait=1)

        # B服切换账号时会直接弹出这个框, 此时不需要点击切换账号
        result = self.round_by_find_area(screen, '打开游戏', 'B服新-登录记录')
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_area(screen, '打开游戏', '点击进入游戏')
        if result.is_success:
            self.resource_download_start_time = None
            return self.round_success('点击进入游戏', wait=1)

        result = self.round_by_find_and_click_area(screen, '打开游戏', '国服-账号密码')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '打开游戏', '国服-账号密码-新')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '打开游戏', '按钮-登陆其他账号')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        # region 当B服弹出这些提示的时候, 就代表需要重新输账号密码和验证码了, 脚本搞不定, 直接终止脚本运行最容易让用户发现问题
        result = self.round_by_find_area(screen, '打开游戏', 'B服新-手机号登录')
        if result.is_success:
            return self.round_fail(result.status)
        # B服账号过期会提示同意隐私政策
        result = self.round_by_find_area(screen, '打开游戏', 'B服新-隐私政策提示')
        if result.is_success:
            return self.round_by_find_and_click_area(screen, '打开游戏', 'B服新-同意隐私政策')
        # endregion

        if self.ctx.game_account_config.game_region != GameRegionEnum.CN.value.value \
                and self.ctx.game_account_config.game_region != GameRegionEnum.CNB.value.value:
            return self.check_screen_intl(screen)

        return None

    def check_screen_intl(self, screen: MatLike) -> OperationRoundResult | None:
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
    ''' B服登录需要验证码, 先不处理
    @node_from(from_name='画面识别', status='B服-登录')
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
        return self.round_by_find_and_click_area(screen, '打开游戏', 'B服-登录',
                                                 success_wait=5, retry_wait=1)
    '''

    @node_from(from_name='画面识别', status='B服新-登录记录')
    @operation_node(name='B服新-点击下拉菜单')
    def click_drop_button(self) -> OperationRoundResult:
        name = self.ctx.game_account_config.bilibili_account_name.strip()
        if not name:
            return self.round_fail('未配置B服用户名, 无法切换已登录的B服账号')

        return self.round_by_find_and_click_area(self.last_screenshot, '打开游戏', 'B服新-切换账号', success_wait=0.8)

    @node_from(from_name='B服新-点击下拉菜单')
    @operation_node(name='B服新-选择登录过的账号')
    def switch_bilibili_account(self) -> OperationRoundResult:
        # region ocr切换账号
        area = self.ctx.screen_loader.get_area('打开游戏', 'B服新-账号列表')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        # cv2_utils.show_image(part, win_name='debug', wait=1)

        mask = cv2.inRange(part,
                           np.array([220, 220, 220], dtype=np.uint8),
                           np.array([255, 255, 255], dtype=np.uint8))
        to_ocr = cv2.bitwise_and(part, part, mask=cv2_utils.dilate(mask, 5))

        striped_name = self.ctx.game_account_config.bilibili_account_name.strip()
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)
        find = False
        for ocr_result, mrl in ocr_result_map.items():
            if striped_name and str_utils.find_by_lcs(striped_name, ocr_result, percent=0.7):
                find = True
                self.ctx.controller.click(mrl.max.center + area.left_top)
                break
        if not find:
            masked = (striped_name[:1] + '*' * max(len(striped_name) - 2, 1) + striped_name[-1:]) if len(striped_name) >= 2 else '*'
            return self.round_retry(f"未找到已登录的用户: {masked}")
        # endregion

        screen = self.screenshot()
        self.already_login = True
        return self.round_by_find_and_click_area(screen, '打开游戏', 'B服-登录',
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

    def check_game_data_updated(
        self,
        screen: MatLike,
        back_to_check_screen: bool,
    ) -> OperationRoundResult | None:
        """
        处理资源更新完成后要求重新登录的提示。

        Args:
            screen: 游戏画面。
            back_to_check_screen: 点击确认后是否回到画面识别节点。

        Returns:
            有处理结果时返回对应结果，否则返回 None。
        """
        message_result = self.round_by_find_area(
            screen,
            '打开游戏',
            '游戏数据更新提示',
        )
        if not message_result.is_success:
            return None

        confirm_result = self.round_by_find_and_click_area(
            screen,
            '打开游戏',
            '游戏数据更新-确定',
            retry_wait=1,
        )
        if not confirm_result.is_success:
            return confirm_result

        self.after_second_enter_click = False
        self.resource_download_start_time = None
        if back_to_check_screen:
            return self.round_success(EnterGame.STATUS_GAME_DATA_UPDATED, wait=3)
        return self.round_wait(EnterGame.STATUS_GAME_DATA_UPDATED, wait=3)

    def check_screen_to_interact(self, screen: MatLike) -> OperationRoundResult | None:
        """
        判断画面 处理可能出现的需要交互的情况
        :param screen: 游戏画面
        :return: 是否有相关操作 有的话返回对应操作结果
        """
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        back_btn_result = self.round_by_find_area(screen, '菜单', '返回')

        target_word_list: list[str] = [
            '取消', # 上一次战斗还没结束 出现是否继续的对话框 issue #957 '确定'/'确认' 要放在'取消'之后 因为有对话框同时出现这两个词
            '确认', # 每个版本出现的10连抽奖励 点击领取后确认
            '领取01', # 每个版本出现的10连抽奖励 注意原文中间有一个符号 识别有时是字母x有时是符号* 所以不在这里写了 issue #893
            '已领取01', # 需要有这个词 防止画面出现"已领取x01"也匹配到"领取x01"
            '领取02', # 同上
            '已领取02', # 同上
            '领取03', # 同上
            '已领取03', # 同上
            '领取60', # 同上
            '已领取60', # 同上
            '领取120', # 同上
            '已领取120', # 同上
            '01', # 需要有这个词 版本奖励显示的天数 防止匹配到 领取01 领取02 这种
            '02', # 同上
            '03', # 同上
            '04', # 同上
            '05', # 同上
            '06', # 同上
            '07', # 同上
            '领取',  # 每个版本出现的10连抽奖励 issue #893
            '已领取',  # 需要有这个词 防止画面出现"已领取"也匹配到"领取"
            '待领取',  # 需要有这个词 防止画面出现"待领取"也匹配到"领取"
            '今日到账',  # 小月卡 issue #893
            '惊喜补给',  # 免费月卡 issue #1996
        ]
        ignore_list: list[str] = [
            '已领取',  # 需要有这个词 防止画面出现"已领取"也匹配到"领取"
            '待领取',  # 需要有这个词 防止画面出现"待领取"也匹配到"领取"
            '已领取01', # 需要有这个词 防止画面出现"已领取x01"也匹配到"领取x01"
            '已领取02', # 同上
            '已领取03', # 同上
            '已领取60', # 同上
            '已领取120', # 同上
            '01', # 需要有这个词 版本奖励显示的天数 防止匹配到 领取01 领取02 这种
            '02', # 同上
            '03', # 同上
            '04', # 同上
            '05', # 同上
            '06', # 同上
            '07', # 同上
        ] + self.interact_ignore_word_list

        match_word, match_word_mrl = ocr_utils.match_word_list_by_priority(
            ocr_result_map,
            target_word_list,
            ignore_list=ignore_list
        )
        if match_word is not None and match_word_mrl is not None and match_word_mrl.max is not None:
            # 新版本的10连奖励 有滑动条导致左边"已领取"在画面上只显示了"领取"
            # 因此这部分的文本都设置只点击一次 后续忽略
            if match_word.find('领取') != -1:
                self.interact_ignore_word_list.append(match_word)

            time.sleep(0.5) # 等待画面稳定
            self.ctx.controller.click(match_word_mrl.max.center)
            return self.round_wait(status=match_word, wait=1)

        if back_btn_result.is_success:
            # 左上角的返回
            self.round_by_click_area('菜单', '返回')
            return self.round_wait(status=back_btn_result.status, wait=1)

        return None

    def match_login_error(self, screen: MatLike) -> OperationRoundResult | None:
        """
        识别登录可能出现的问题
        :param screen: 游戏画面
        :return: 是否有相关操作 有的话返回对应操作结果
        """
        ocr_result_map = self.ctx.ocr.run_ocr(screen)

        target_word_list: list[str] = [
            '确定',  # 游戏更新时出现的确定按钮 issue #991
            '重试',  # 登陆时可能出现登陆超时问题 merge request #886
        ]

        match_word, match_word_mrl = ocr_utils.match_word_list_by_priority(
            ocr_result_map,
            target_word_list
        )
        if match_word is not None and match_word_mrl is not None and match_word_mrl.max is not None:
            time.sleep(0.5) # 等待画面稳定
            self.ctx.controller.click(match_word_mrl.max.center)
            return self.round_wait(status=match_word, wait=1)

        return None

    def is_in_big_world(self, screen: MatLike) -> OperationRoundResult | None:
        # 判定是否进入大世界
        world_screens = ['大世界-普通', '大世界-勘域']
        current_screen = self.check_and_update_current_screen(
            screen,
            screen_name_list=world_screens,
        )
        if current_screen in world_screens:
            return self.round_success('大世界', wait=1)
        return None

    def is_gray_loading_screen(self, screen: MatLike) -> bool:
        """
        通过整屏低饱和度判断黑白灰加载界面。

        Returns:
            画面几乎没有彩色时返回 True。
        """
        if screen.ndim < 3 or screen.shape[2] < 3:
            return False

        height, width = screen.shape[:2]
        to_check = screen[
            height // 10: height * 9 // 10,
            width // 10: width * 9 // 10,
        ]
        hsv = cv2.cvtColor(to_check, cv2.COLOR_RGB2HSV)
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]

        visible_mask = value > 20
        visible_count = int(np.count_nonzero(visible_mask))
        if visible_count == 0:
            return True

        colorful_mask = (saturation > 40) & visible_mask
        colorful_ratio = float(np.count_nonzero(colorful_mask)) / visible_count
        return colorful_ratio < 0.03

    def wait_resource_download(self) -> OperationRoundResult:
        """
        资源下载中时等待，超过上限后失败。

        Returns:
            等待或失败结果。
        """
        now = time.time()
        if self.resource_download_start_time is None:
            self.resource_download_start_time = now

        downloading_seconds = now - self.resource_download_start_time
        if downloading_seconds < EnterGame.MAX_RESOURCE_DOWNLOAD_SECONDS:
            return self.round_wait('资源下载中', wait=2)

        self.resource_download_start_time = None
        return self.round_fail('资源下载超时')

    def check_enter_click_status_text(
            self,
            screen: MatLike,
            include_enter_click: bool = False,
    ) -> tuple[str | None, MatchResultList | None]:
        """
        识别进入游戏点击后的状态文本。

        只负责 OCR 匹配，不点击、不修改标志位、不决定节点流转。

        Args:
            screen: 游戏画面。
            include_enter_click: 是否把进入游戏按钮也作为目标状态。

        Returns:
            状态文本和对应匹配结果；未识别时返回 None。
        """
        area = self.ctx.screen_loader.get_area('打开游戏', '进入游戏点击后状态')
        ocr_result_map = self.ctx.ocr_service.get_ocr_result_map(
            image=screen,
            rect=area.rect,
            color_range=area.color_range,
            crop_first=True,
        )
        target_word_list: list[str] = [
            '加载配置数据中',
            '版本校对中',
            '登录游戏服务器中',
            EnterGame.STATUS_LOGIN_SUCCESS,
            '资源下载中',
        ]
        if include_enter_click:
            target_word_list.insert(0, '点击进入游戏')

        return ocr_utils.match_word_list_by_priority(
            ocr_result_map,
            target_word_list,
        )

    @node_from(from_name='画面识别', status='点击进入游戏')
    @operation_node(name='点击进入游戏', node_max_retry_times=15)
    def check_enter_click_status(self) -> OperationRoundResult:
        """
        识别进入游戏点击后的加载状态。

        国服账号密码登录按钮会自动完成第一次进入点击，可能直接进入加载配置阶段；
        也可能因为截图时机直接进入第二次点击后的登录阶段。
        """
        # 第一次点击进入游戏后，普通加载和资源更新都在这里分流。
        data_updated_result = self.check_game_data_updated(self.last_screenshot, back_to_check_screen=True)
        if data_updated_result is not None:
            return data_updated_result

        if self.force_login and not self.already_login:
            result = self.round_by_find_and_click_area(self.last_screenshot, '打开游戏', '切换账号确定')
            if result.is_success:
                self.after_first_enter_click = False
                self.after_second_enter_click = False
                self.resource_download_start_time = None
                return self.round_success(result.status, wait=5)

            result = self.round_by_find_and_click_area(self.last_screenshot, '打开游戏', '切换账号')
            if result.is_success:
                self.after_second_enter_click = False
                self.resource_download_start_time = None
                return self.round_wait(result.status, wait=1)

            return self.round_retry('等待切换账号', wait=1)

        match_word, _ = self.check_enter_click_status_text(
            self.last_screenshot,
            include_enter_click=True,
        )
        if match_word is not None:
            if match_word == '资源下载中':
                return self.wait_resource_download()

            self.resource_download_start_time = None
            if match_word == '点击进入游戏':
                click_result = self.round_by_click_area('打开游戏', '点击进入游戏')
                if click_result.is_success:
                    if self.after_first_enter_click:
                        self.after_second_enter_click = True
                    else:
                        self.after_first_enter_click = True
                    return self.round_wait(status=match_word, wait=2)
                return click_result

            if match_word == '加载配置数据中':
                self.after_first_enter_click = True

            if match_word == '登录游戏服务器中':
                self.after_second_enter_click = True

            if match_word == EnterGame.STATUS_LOGIN_SUCCESS:
                self.after_second_enter_click = True
                return self.round_success(match_word, wait=1)

            return self.round_wait(status=match_word, wait=1)

        if self.after_second_enter_click:
            # 登录失败只会出现在加载配置后的第二次进入游戏点击之后。
            login_error_result = self.match_login_error(self.last_screenshot)
            if login_error_result is not None:
                return login_error_result
            return self.round_success(EnterGame.STATUS_LOADING)

        return self.round_retry('进入游戏点击后等待', wait=1)

    @node_from(from_name='点击进入游戏', status=STATUS_LOGIN_SUCCESS)
    @node_from(from_name='点击进入游戏', status=STATUS_LOADING)
    @operation_node(name='登录成功', timeout_seconds=MAX_LOADING_SECONDS)
    def wait_loading(self) -> OperationRoundResult:
        """
        等待加载场景结束，并处理加载后的弹窗和大世界识别。

        Returns:
            仍在加载时等待；识别到弹窗时处理；识别到大世界时结束。
        """
        result = self.round_by_find_area(self.last_screenshot, '加载中', '加载中')
        if result.is_success:
            return self.round_wait(result.status, wait=2)

        # 识别并点击弹窗
        interact_result = self.check_screen_to_interact(self.last_screenshot)
        if interact_result is not None:
            return interact_result

        # 判定是否进入大世界
        interact_result = self.is_in_big_world(self.last_screenshot)
        if interact_result is not None:
            return interact_result

        if self.is_gray_loading_screen(self.last_screenshot):
            return self.round_wait(EnterGame.STATUS_LOADING, wait=2)

        # 如果既不在大世界也没有已知弹窗, 游戏界面可能是被其他未知弹窗覆盖了, 尝试点击左上角关闭弹窗
        return_result = self.round_by_click_area('菜单', '返回')
        if not return_result.is_success:
            return return_result

        return self.round_retry('登录成功后等待加载中或大世界', wait=2)


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    op = EnterGame(ctx, switch=False)
    op.execute()
    ctx.run_context.stop_running()


if __name__ == '__main__':
    # 因为检查是否否在大世界的逻辑被移到 '点击进入游戏' 了, 故进入游戏后调用 EnterGame 会一直识别失败,
    # 从而如果在游戏关闭的时候运行这个debug, 脚本会从 openAndEnterGame 调用一次 EnterGame,
    # 导致进入游戏后再调用 EnterGame 时画面一直识别失败, 属于正常现象.
    # 将游戏打开后再运行这个debug就不会产生上述现象.
    __debug()
