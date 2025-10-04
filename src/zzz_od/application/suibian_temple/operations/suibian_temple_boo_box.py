import time
from typing import Optional

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cal_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.suibian_temple.suibian_temple_config import (
    BangbooPrice,
    SuibianTempleConfig,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleBooBox(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 邦巢

        需要在随便观主界面时调用，完成后返回随便观主界面

        操作步骤
        1. 前往邻里街坊
        2. 进入邦巢
        3. 检查邦布，有S级就购买，没有就刷新
        4. 次数用尽后返回随便观主界面

        Args:
            ctx: 上下文
        """
        ZOperation.__init__(self, ctx,
                            op_name=f'{gt("随便观", "game")} {gt("邦巢", "game")}')

        self.config: Optional[SuibianTempleConfig] = self.ctx.run_context.get_config(app_id='suibian_temple')

        self.bought_bangboo: bool = False  # 是否已购买邦布
        self.bought_count: int = 0  # 已购买邦布数量
        self.refresh_count: int = 0  # 刷新次数计数
        self.max_refresh_count: int = 30  # 最大刷新次数限制

        self.done_bangboo_pos: list[Rect] = []  # 已经选择过的邦布位置 点击刷新后重置/购买后需要删除
        self.current_bangboo_pos: Optional[Rect] = None  # 当前选择的邦布位置
        self.current_bangboo_price: str = ''  # 当前选择的邦布的价格 购买后/点击刷新后 重置

    @operation_node(name='前往邦巢', is_start_node=True, node_max_retry_times=5)
    def goto_boo_box(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-邦巢'])
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        target_cn_list: list[str] = [
            '邻里街坊',
            '邦巢',
        ]
        ignore_cn_list: list[str] = [
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='前往邦巢')
    @node_from(from_name='检查邦布类型', success=False)  # 检测邦布类型失败 进入选择下一个
    @node_from(from_name='检查邦布类型', status='不购买该类型邦布')
    @node_from(from_name='检查邦布类型', status='价格低于配置要求')
    @node_from(from_name='检查邦布', status='刷新邦布完成')
    @node_from(from_name='返回界面', status='继续检查邦布')
    @node_from(from_name='处理购买动画', status='确认后继续检查邦布')
    @node_from(from_name='处理购买动画', status='已返回邦巢界面')
    @operation_node(name='检查邦布')
    def check_bangboo(self) -> OperationRoundResult:
        """
        检查邦布的主逻辑：有S级就购买，没有S级就刷新
        """
        # 确认是否在邦巢界面
        in_boobox_interface = False

        if not in_boobox_interface:
            result = self.round_by_find_area(self.last_screenshot, '随便观-邦巢', '按钮-聘用')
            if result.is_success:
                in_boobox_interface = True

        if not in_boobox_interface:
            return self.round_retry(status='不在邦巢界面，等待加载', wait=2)

        # 检查是否有S级邦布 - 通过识别高价格，选中所有符合条件的邦布
        bangboo_ocr_list = self.ctx.ocr_service.get_ocr_result_list(
            self.last_screenshot,
            rect=self.ctx.screen_loader.get_area('随便观-邦巢', '区域-邦布列表').rect,
        )

        s_bangboo_list: list[tuple[str, Rect]] = []

        # S级邦布可能的价格列表（从高到低检测，优先购买更稀有的）
        s_rank_prices = [
            str(i)
            for i in BangbooPrice
            if i != BangbooPrice.NONE
        ]

        # 按价格优先级搜索S级邦布，找到所有符合条件的
        for price in s_rank_prices:
            for ocr_result in bangboo_ocr_list:
                if price not in ocr_result.data:
                    continue
                s_bangboo_list.append((ocr_result.data, ocr_result.rect))

        # 如果找到S级邦布，依次点击选中所有符合条件的邦布
        if len(s_bangboo_list) > 0:
            # 记录找到的价格信息到日志
            price_info = ','.join([i[0] for i in s_bangboo_list])
            log.info(f"找到S级邦布，价格: {price_info}")

            # 依次点击所有符合条件的邦布进行选中
            for bangboo in s_bangboo_list:
                pos = bangboo[1]
                chosen = False  # 之前是否已经点击过
                for done in self.done_bangboo_pos:
                    if cal_utils.cal_overlap_percent(done, pos) > 0.7:
                        chosen = True
                        break

                if chosen:
                    continue

                self.current_bangboo_pos = pos
                self.current_bangboo_price = bangboo[0]
                self.done_bangboo_pos.append(pos)

                # 邦布卡片在价格上方，向上偏移约150像素
                click_pos = pos.center + Point(0, -150)
                self.ctx.controller.click(click_pos)
                time.sleep(0.5)  # 点击间隔
                return self.round_success(status='点击S级邦布', wait=1)

        # 检查是否有次数用尽
        whole_ocr_list = self.ctx.ocr_service.get_ocr_result_list(self.last_screenshot)
        for ocr_result in whole_ocr_list:
            if '次数用尽' in ocr_result.data:
                log.info(f"邦巢购买完成 - 购买邦布数量: {self.bought_count}, 刷新次数: {self.refresh_count}")
                return self.round_success(status='次数用尽')

        # 检查刷新次数限制
        if self.refresh_count >= self.max_refresh_count:
            log.info(f"达到最大刷新次数限制({self.max_refresh_count}) - 购买邦布数量: {self.bought_count}, 刷新次数: {self.refresh_count}")
            return self.round_success(status='次数用尽')

        # 如果没有S级邦布，点击刷新按钮
        self.refresh_count += 1
        log.info(f"尝试点击刷新区域 (第{self.refresh_count}次)")
        # 先检查当前屏幕识别
        current_screen = self.check_and_update_current_screen(self.last_screenshot)
        log.info(f"当前识别的屏幕: {current_screen}")

        self.round_by_click_area('随便观-邦巢', '按钮-刷新')

        # 刷新后清空
        self.done_bangboo_pos.clear()

        return self.round_wait(status="刷新邦布完成", wait=1.5)

    @node_from(from_name="检查邦布", status="点击S级邦布")
    @operation_node(name='检查邦布类型')
    def check_bangboo_type(self) -> OperationRoundResult:
        type_list = [
            '游历',
            '制造',
            '售卖',
        ]
        current_type: str | None = None

        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            self.last_screenshot,
            rect=self.ctx.screen_loader.get_area('随便观-邦巢', '标题-邦布名称').rect,
        )
        for ocr_result in ocr_result_list:
            for t in type_list:
                if t in ocr_result.data:
                    current_type = t
                    break

        if current_type == '游历':
            price = BangbooPrice[self.config.boo_box_adventure_price]
        elif current_type == '制造':
            price = BangbooPrice[self.config.boo_box_craft_price]
        elif current_type == '售卖':
            price = BangbooPrice[self.config.boo_box_sell_price]
        else:
            return self.round_retry(status='未识别邦布类型', wait=0.3)

        if price == BangbooPrice.NONE:
            return self.round_success(status='不购买该类型邦布')
        if str_utils.get_positive_digits(self.current_bangboo_price, err=0) < int(price):
            return self.round_success(status='价格低于配置要求')

        return self.round_success(status='符合购买要求')

    @node_from(from_name='检查邦布类型', status='符合购买要求')
    @operation_node(name='点击聘用')
    def click_hire(self) -> OperationRoundResult:
        """点击右下角的聘用按钮"""
        click_result = self.round_by_find_and_click_area(
            self.last_screenshot,
            '随便观-邦巢',
            '按钮-聘用'
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
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)

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

        self.ctx.controller.click(
            pos=self.ctx.screen_loader.get_area('随便观-邦巢', '按钮-跳过').center,
            press_time=0.5,  # 长按一点
        )
        return self.round_wait(status='点击跳过', wait=0.5)

    @node_from(from_name='处理购买动画', status='点击跳过')
    @operation_node(name='返回界面')
    def return_interface(self) -> OperationRoundResult:
        """返回邦巢界面"""
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)

        target_word_list: list[str] = ['返回']
        word, mrl = ocr_utils.match_word_list_by_priority(ocr_result_map, target_word_list)

        if word == '返回' and mrl.max is not None:
            self.ctx.controller.click(mrl.max.center)
            return self.round_wait(status='继续检查邦布', wait=2)

        return self.round_retry(status='未找到返回按钮', wait=1)

    @node_from(from_name='检查邦布', status='次数用尽')
    @operation_node(name='返回随便观')
    def back_to_entry(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'
    op = SuibianTempleBooBox(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
