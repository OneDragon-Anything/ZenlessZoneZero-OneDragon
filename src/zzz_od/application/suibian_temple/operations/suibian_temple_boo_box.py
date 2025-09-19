import time

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleBooBox(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 邦巢

        需要在随便观主界面时调用，完成后返回大世界

        操作步骤
        1. 前往邻里街坊
        2. 进入邦巢
        3. 检查邦布，有S级就购买，没有就刷新
        4. 次数用尽后返回大世界

        Args:
            ctx: 上下文
        """
        ZOperation.__init__(self, ctx,
                            op_name=f'{gt("随便观", "game")} {gt("邦巢", "game")}')

        self.config: SuibianTempleConfig = self.ctx.run_context.get_config(app_id='suibian_temple')

        self.bought_bangboo: bool = False  # 是否已购买邦布
        self.bought_count: int = 0  # 已购买邦布数量
        self.refresh_count: int = 0  # 刷新次数计数
        self.max_refresh_count: int = 30  # 最大刷新次数限制

    @operation_node(name='前往邻里街坊', is_start_node=True, node_max_retry_times=5)
    def goto_linli_jiefang(self) -> OperationRoundResult:
        screen = self.screenshot()

        # 点击邻里街坊按钮
        result = self.round_by_ocr_and_click(screen, '邻里街坊')
        if result.is_success:
            return self.round_success()

        return self.round_retry(status='未找到邻里街坊', wait=1)

    @node_from(from_name='前往邻里街坊')
    @operation_node(name='已在邻里街坊-进入邦巢', node_max_retry_times=5)
    def goto_boo_box(self) -> OperationRoundResult:
        """从邻里街坊进入邦巢"""
        screen = self.screenshot()
        # 首先检查是否已经在邦巢界面
        if self.round_by_ocr(screen, '聘用').is_success:
            return self.round_success(status='已在邦巢-聘用')
        # 点击按钮
        result = self.round_by_ocr_and_click(screen, '邦巢')
        if result.is_success:
            return self.round_wait(status=result.status, wait=2)

        return self.round_retry(status='未找到邦巢', wait=1)

    @node_from(from_name='已在邻里街坊-进入邦巢', status='已在邦巢-聘用')
    @node_from(from_name='已在邻里街坊-进入邦巢')
    @node_from(from_name='检查邦布', status='刷新邦布完成')
    @node_from(from_name='返回界面', status='继续检查邦布')
    @node_from(from_name='处理购买动画', status='确认后继续检查邦布')
    @node_from(from_name='处理购买动画', status='已返回邦巢界面')
    @operation_node(name='检查邦布')
    def check_bangboo(self) -> OperationRoundResult:
        """
        检查邦布的主逻辑：有S级就购买，没有S级就刷新
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

        if not in_boobox_interface:
            return self.round_retry(status='不在邦巢界面，等待加载', wait=2)

        # 检查是否有次数用尽
        for text in ocr_result_map.keys():
            if '次数用尽' in text:
                log.info(f"邦巢购买完成 - 购买邦布数量: {self.bought_count}, 刷新次数: {self.refresh_count}")
                return self.round_success(status='次数用尽')

        # 检查刷新次数限制
        if self.refresh_count >= self.max_refresh_count:
            log.info(f"达到最大刷新次数限制({self.max_refresh_count}) - 购买邦布数量: {self.bought_count}, 刷新次数: {self.refresh_count}")
            return self.round_success(status='次数用尽')

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
                    # 邦布卡片在价格上方，向上偏移约150像素
                    bangboo_click_pos = Point(price_center.x, price_center.y - 150)
                    s_click_positions.append(bangboo_click_pos)

        # 如果找到S级邦布，依次点击选中所有符合条件的邦布
        if s_found and len(s_click_positions) > 0:
            # 记录找到的价格信息到日志
            price_info = ','.join(found_prices)
            log.info(f"找到S级邦布，价格: {price_info}")

            # 依次点击所有符合条件的邦布进行选中
            for pos in s_click_positions:
                self.ctx.controller.click(pos)
                time.sleep(0.5)  # 点击间隔
            # 选中所有S级邦布后进入购买流程
            return self.round_success(status='开始购买S级邦布')

        # 如果没有S级邦布，点击刷新按钮
        self.refresh_count += 1
        log.info(f"尝试点击刷新区域 (第{self.refresh_count}次)")
        # 先检查当前屏幕识别
        current_screen = self.check_and_update_current_screen(screen)
        log.info(f"当前识别的屏幕: {current_screen}")

        refresh_center = Point(1285, 986)
        self.ctx.controller.click(refresh_center)
        return self.round_wait(status='刷新邦布完成', wait=1.5)

    @node_from(from_name='检查邦布', status='开始购买S级邦布')
    @operation_node(name='点击聘用')
    def click_hire(self) -> OperationRoundResult:
        """点击右下角的聘用按钮"""
        click_result = self.round_by_find_and_click_area(
            self.screenshot(),
            '邦巢',
            '聘用'
        )

        if click_result.is_success:
            self.bought_count += 1
            log.info(f"成功购买第{self.bought_count}个S级邦布")
            return self.round_success(status='点击聘用', wait=2)
        else:
            return self.round_retry(status='未找到聘用按钮', wait=1)

    @node_from(from_name='点击聘用', status='点击聘用')
    @operation_node(name='处理购买动画')
    def handle_purchase_animation(self) -> OperationRoundResult:
        """处理购买流程：点击跳过按钮，然后检测确认按钮"""
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

        skip_center = Point(1767, 132)
        self.ctx.controller.click(skip_center)
        return self.round_wait(status='点击跳过', wait=0.5)

    @node_from(from_name='处理购买动画', status='点击跳过')
    @operation_node(name='返回界面')
    def return_interface(self) -> OperationRoundResult:
        """返回邦巢界面"""
        screen = self.screenshot()
        ocr_result_map = self.ctx.ocr.run_ocr(screen)

        target_word_list: list[str] = ['返回']
        word, mrl = ocr_utils.match_word_list_by_priority(ocr_result_map, target_word_list)

        if word == '返回' and mrl.max is not None:
            self.ctx.controller.click(mrl.max.center)
            return self.round_wait(status='继续检查邦布', wait=2)

        return self.round_retry(status='未找到返回按钮', wait=1)

    @node_from(from_name='检查邦布', status='次数用尽')
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        log.info(f"邦巢操作结束 - 总计购买邦布: {self.bought_count}个, 总计刷新: {self.refresh_count}次")
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'
    op = SuibianTempleBooBox(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
