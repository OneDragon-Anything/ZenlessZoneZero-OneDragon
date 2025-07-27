import time

from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.transport import Transport


class BooboxApp(ZApplication):
    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='boobox',
            op_name=gt('邦巢'),
            run_record=ctx.boobox_run_record,
            retry_in_od=True,  # 传送落地有可能会歪 重试,
            need_notify=True,
        )
        self.bought_bangboo: bool = False  # 是否已购买邦布
        self.bought_count: int = 0  # 已购买邦布数量
        self.refresh_count: int = 0  # 刷新次数计数
        self.max_refresh_count: int = 30  # 最大刷新次数限制

    @operation_node(name='识别初始画面', is_start_node=True)
    def check_initial_screen(self) -> OperationRoundResult:
        # 检查邦巢功能和总开关是否启用
        if not self.ctx.suibian_temple_config.overall_enabled:
            log.info('随便观总开关已禁用，跳过邦巢执行')
            return self.round_success(status='随便观总开关已禁用，邦巢功能已跳过')

        if not self.ctx.suibian_temple_config.boobox_enabled:
            log.info('邦巢功能已禁用，跳过执行')
            return self.round_success(status='邦巢功能已跳过')

        screen = self.screenshot()

        # 检测是否已经在邦巢界面
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        for text in ocr_result_map.keys():
            if '聘用' in text:
                return self.round_success(status='已在邦巢界面')

        # 使用预定义区域检测邦巢界面
        result = self.round_by_find_area(screen, '邦巢', '聘用')
        if result.is_success:
            return self.round_success(status='已在邦巢界面')

        current_screen_name, can_go = self.check_screen_with_can_go(screen, '快捷手册-目标')
        if can_go is not None and can_go == True:
            return self.round_by_goto_screen(screen, '快捷手册-目标',
                                             success_wait=1, retry_wait=1)

        current_screen_name, can_go = self.check_screen_with_can_go(screen, '随便观-入口')
        if can_go is not None and can_go == True:
            return self.round_success(status='随便观-入口')

        return self.round_retry(status='未识别初始画面', wait=1)

    @node_from(from_name='识别初始画面', status='未识别初始画面', success=False)
    @operation_node(name='开始前返回大世界')
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别初始画面', status='快捷手册-目标')
    @node_from(from_name='开始前返回大世界')
    @operation_node(name='前往快捷手册-目标')
    def goto_category(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_goto_screen(screen, '快捷手册-目标')

    @node_from(from_name='前往快捷手册-目标')
    @operation_node(name='前往随便观', node_max_retry_times=10)
    def goto_suibian_temple(self) -> OperationRoundResult:
        screen = self.screenshot()

        target_cn_list: list[str] = [
            '前往随便观',
            '确认',
        ]

        result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list)
        if result.is_success:
            if result.status == '累计获得称愿':
                self.round_by_find_and_click_area(screen, '菜单', '返回')
            return self.round_wait(status=result.status or '操作成功', wait=1)

        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        result = self.round_by_find_and_click_area(screen, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status or '返回菜单', wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)
    @node_from(from_name='识别初始画面', status='随便观-入口')
    @node_from(from_name='前往随便观')
    @operation_node(name='点击邻里街坊')
    def click_neighbor(self) -> OperationRoundResult:
        screen = self.screenshot()

        # 检查是否已经在邦巢界面
        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['邦巢'])
        if current_screen_name is not None:
            return self.round_success(status='已在邦巢界面')

        # 检查是否有邦巢界面的特征，优先检查"聘用"
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        for text in ocr_result_map.keys():
            if '聘用' in text:  # 检查文本中是否包含'聘用'字样
                return self.round_success(status='已进入邦巢界面')

        # 尝试点击邻里街坊
        neighbor_list: list[str] = ['邻里街坊']
        result = self.round_by_ocr_and_click_by_priority(screen, neighbor_list)
        if result.is_success:
            return self.round_success(status='点击邻里街坊', wait=2)

        return self.round_retry(status='未找到邻里街坊按钮', wait=1)

    @node_from(from_name='点击邻里街坊', status='点击邻里街坊')
    @operation_node(name='点击邦巢')
    def click_boobox(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '邦巢', '次数用尽')
        if result.is_success:
            op = BackToNormalWorld(self.ctx)
            return self.round_by_op_result(op.execute())
        result = self.round_by_find_area(screen, '邦巢', '聘用')
        if result.is_success:
            return self.round_success(status='已进入邦巢界面')

        # 如果都没有检测到邦巢界面特征，尝试点击邦巢
        boobox_list: list[str] = ['邦巢']
        result = self.round_by_ocr_and_click_by_priority(screen, boobox_list)
        if result.is_success:
            return self.round_wait(status='点击邦巢', wait=3)

        return self.round_retry(status='未找到邦巢按钮', wait=1)

    @node_from(from_name='识别初始画面', status='已在邦巢界面')
    @node_from(from_name='点击邻里街坊', status='已在邦巢界面')
    @node_from(from_name='点击邻里街坊', status='已进入邦巢界面')
    @node_from(from_name='点击邦巢', status='已进入邦巢界面')
    @node_from(from_name='点击邦巢', status='点击邦巢')
    @node_from(from_name='检查邦布', status='刷新邦布完成')
    @node_from(from_name='返回界面', status='继续检查邦布')
    @node_from(from_name='处理购买动画', status='确认后继续检查邦布')
    @node_from(from_name='处理购买动画', status='已返回邦巢界面')
    @operation_node(name='检查邦布')
    def check_bangboo(self) -> OperationRoundResult:
        """
        检查邦布的主逻辑：有S级就购买，没有S级就刷新
        :return:
        """
        screen = self.screenshot()

        # 确认是否在邦巢界面
        in_boobox_interface = False

        # 首先进行OCR检测
        ocr_result_map = self.ctx.ocr.run_ocr(screen)

        if not in_boobox_interface:
            result = self.round_by_find_area(screen, '邦巢', '聘用')
            if result.is_success:
                in_boobox_interface = True

        # 检查刷新按钮作为补充（降级方案）
        if not in_boobox_interface:
            for text in ocr_result_map.keys():
                if '刷新' in text:
                    in_boobox_interface = True
                    break

        # 如果确实不在邦巢界面，等待重试
        if not in_boobox_interface:
            return self.round_retry(status='不在邦巢界面，等待加载', wait=2)

        # 检查是否有次数用尽
        for text in ocr_result_map.keys():
            if '次数用尽' in text:
                op = BackToNormalWorld(self.ctx)
                return self.round_by_op_result(op.execute())

        # 检查是否有S级邦布 - 通过识别高价格，选中所有符合条件的邦布
        s_found = False
        s_click_positions = []
        found_prices = []  # 记录找到的价格

        # S级邦布可能的价格列表（从高到低检测，优先购买更稀有的）
        s_rank_prices = ['40000', '35000', '30000', '25000']

        # 按价格优先级搜索S级邦布，找到所有符合条件的
        for price in s_rank_prices:
            for text, mrl in ocr_result_map.items():
                if price in text and mrl.max is not None:
                    s_found = True
                    found_prices.append(price)
                    # 找到S级价格，点击对应的邦布位置
                    # 计算邦布卡片的点击位置（价格上方的邦布图像区域）
                    price_center = mrl.max.center
                    # 邦布卡片通常在价格上方，向上偏移约150像素
                    bangboo_click_pos = Point(price_center.x, price_center.y - 150)
                    s_click_positions.append(bangboo_click_pos)

        # 如果找到S级邦布，依次点击选中所有符合条件的邦布
        if s_found and len(s_click_positions) > 0:
            # 记录找到的价格信息到日志
            price_info = ','.join(found_prices)
            print(f"找到S级邦布，价格: {price_info}")

            # 依次点击所有符合条件的邦布进行选中
            for pos in s_click_positions:
                self.ctx.controller.click(pos)
                time.sleep(0.5)  # 点击间隔
            # 选中所有S级邦布后进入购买流程
            return self.round_success(status='开始购买S级邦布')

        # 如果没有S级邦布，尝试刷新邦布
        refresh_result = self.round_by_find_and_click_area(screen, '邦巢', '刷新区域', retry_wait=1)
        if refresh_result.is_success:
            self.refresh_count += 1
            return self.round_wait(status='刷新邦布完成', wait=1.5)

    @node_from(from_name='检查邦布', status='开始购买S级邦布')
    @operation_node(name='点击聘用')
    def click_hire(self) -> OperationRoundResult:
        """
        点击右下角的聘用按钮
        :return:
        """

        click_result = self.round_by_find_and_click_area(
            self.screenshot(),
            '邦巢',
            '聘用',
            retry_wait=1
        )

        if click_result.is_success:
            self.bought_bangboo = True
            self.bought_count += 1
            print(f"成功购买第{self.bought_count}个S级邦布")
            return self.round_success(status='点击聘用', wait=2)
        else:
            return self.round_retry(status='未找到聘用按钮', wait=1)


    @node_from(from_name='点击聘用', status='点击聘用')
    @operation_node(name='处理购买动画')
    def handle_purchase_animation(self) -> OperationRoundResult:
        """
        处理购买流程：点击跳过按钮，然后检测确认按钮
        """
        screen = self.screenshot()
        ocr_result_map = self.ctx.ocr.run_ocr(screen)

        # 检测是否出现"获得"界面，说明跳过成功
        if any('获得' in text for text in ocr_result_map.keys()):
            # 检测到"获得"界面，寻找确认按钮
            word, mrl = ocr_utils.match_word_list_by_priority(ocr_result_map, ['确认'])
            if word == '确认' and mrl.max is not None:
                self.ctx.controller.click(mrl.max.center)
                return self.round_wait(status='确认后继续检查邦布', wait=2)

        # 检测是否已经返回邦巢界面（通过聘用按钮判断）
        if any('聘用' in text for text in ocr_result_map.keys()):
            return self.round_success(status='已返回邦巢界面')

        # 检测是否有返回按钮
        if any('返回' in text for text in ocr_result_map.keys()):
            return self.round_success(status='出现返回按钮')

        # 使用预定义区域点击跳过按钮，这个点击很怪 需要多点几次
        result = self.round_by_find_and_click_area(screen, '邦巢', '跳过')
        if result.is_success:
            return self.round_wait(status='点击跳过', wait=0.5)

    @node_from(from_name='处理购买动画', status='点击确认完成')
    @node_from(from_name='处理购买动画', status='跳过动画完成')
    @node_from(from_name='处理购买动画', status='出现返回按钮')
    @node_from(from_name='处理购买动画', status='点击跳过')
    @operation_node(name='返回界面')
    def return_interface(self) -> OperationRoundResult:
        """
        返回邦巢界面
        :return:
        """
        screen = self.screenshot()
        ocr_result_map = self.ctx.ocr.run_ocr(screen)

        target_word_list: list[str] = ['返回']
        word, mrl = ocr_utils.match_word_list_by_priority(ocr_result_map, target_word_list)

        if word == '返回' and mrl.max is not None:
            self.ctx.controller.click(mrl.max.center)
            return self.round_wait(status='继续检查邦布', wait=2)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = BooboxApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
