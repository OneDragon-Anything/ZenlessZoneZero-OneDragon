import time

from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
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
        self.refresh_count: int = 0  # 刷新次数计数
        self.max_refresh_count: int = 30  # 最大刷新次数限制

    @operation_node(name='识别初始画面', is_start_node=True)
    def check_initial_screen(self) -> OperationRoundResult:
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

        # 方式1：使用预定义的聘用按钮区域检测
        result = self.round_by_find_area(screen, '邦巢', '聘用')
        if result.is_success:
            return self.round_success(status='已进入邦巢界面')

        # 方式2：使用OCR检测聘用按钮
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        for text in ocr_result_map.keys():
            if '次数用尽' in text:
                op = BackToNormalWorld(self.ctx)
                return self.round_by_op_result(op.execute())
            if '聘用' in text:  # 检查文本中是否包含'聘用'字样
                return self.round_success(status='已进入邦巢界面')

        # 方式3：检查是否有刷新按钮（也是邦巢界面的特征）
        refresh_result = self.round_by_find_area(screen, '邦巢', '刷新')
        if refresh_result.is_success:
            return self.round_success(status='已进入邦巢界面')

        # 方式4：使用OCR检测刷新按钮
        for text in ocr_result_map.keys():
            if '刷新' in text:
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
    @operation_node(name='检查邦布')
    def check_bangboo(self) -> OperationRoundResult:
        """
        检查邦布的主逻辑：有S级就购买，没有S级就刷新
        :return:
        """
        screen = self.screenshot()
        
        # 确认是否在邦巢界面 - 主要依靠"聘用"按钮检测
        in_boobox_interface = False
        
        # 首先进行OCR检测
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        
        # 方式1：OCR检测聘用按钮（最可靠的方式）
        for text in ocr_result_map.keys():
            if '聘用' in text:
                in_boobox_interface = True
                break
        
        # 方式2：如果OCR没有检测到聘用，尝试预定义区域检测
        if not in_boobox_interface:
            result = self.round_by_find_area(screen, '邦巢', '聘用')
            if result.is_success:
                in_boobox_interface = True
        
        # 方式3：最后检查刷新按钮作为补充（降级方案）
        if not in_boobox_interface:
            for text in ocr_result_map.keys():
                if '刷新' in text:
                    in_boobox_interface = True
                    break
        
        # 如果确实不在邦巢界面，等待重试
        if not in_boobox_interface:
            return self.round_retry(status='不在邦巢界面，等待加载', wait=2)
        
        # 初始化OCR结果映射（如果之前没有初始化）
        if 'ocr_result_map' not in locals():
            ocr_result_map = self.ctx.ocr.run_ocr(screen)
        
        # 检查是否已达到最大刷新次数
        if self.refresh_count >= self.max_refresh_count:
            op = BackToNormalWorld(self.ctx)
            return self.round_by_op_result(op.execute())

        # 检查是否有次数用尽
        for text in ocr_result_map.keys():
            if '次数用尽' in text:
                op = BackToNormalWorld(self.ctx)
                return self.round_by_op_result(op.execute())

        # 检查是否有S级邦布 - 通过识别价格25000
        s_found = False
        s_click_positions = []
        
        # 使用OCR在全屏搜索25000价格
        for text, mrl in ocr_result_map.items():
            if '25000' in text and mrl.max is not None:
                s_found = True
                # 找到25000价格，点击对应的邦布位置
                # 计算邦布卡片的点击位置（价格上方的邦布图像区域）
                price_center = mrl.max.center
                # 邦布卡片通常在价格上方，向上偏移约150像素
                bangboo_click_pos = Point(price_center.x, price_center.y - 150)
                s_click_positions.append(bangboo_click_pos)
        
        # 如果找到S级邦布（25000价格），依次点击
        if s_found and len(s_click_positions) > 0:
            for pos in s_click_positions:
                self.ctx.controller.click(pos)
                time.sleep(0.5)  # 点击间隔
            return self.round_success(status='点击S级邦布完成')

        # 如果没有S级邦布，尝试刷新邦布
        refresh_result = self.round_by_find_and_click_area(screen, '邦巢', '刷新区域', retry_wait=1)
        if refresh_result.is_success:
            self.refresh_count += 1
            return self.round_wait(status='刷新邦布完成', wait=3)
        
        # 如果刷新区域失败，尝试原来的刷新按钮
        refresh_result2 = self.round_by_find_and_click_area(screen, '邦巢', '刷新', retry_wait=1)
        if refresh_result2.is_success:
            self.refresh_count += 1
            return self.round_wait(status='刷新邦布完成', wait=3)
        
        # 都失败的话，使用固定坐标点击
        refresh_pos = Point(1309, 996)
        self.ctx.controller.click(refresh_pos)
        self.refresh_count += 1
        return self.round_wait(status='刷新邦布完成', wait=3)

    @node_from(from_name='检查邦布', status='点击S级邦布完成')
    @operation_node(name='点击聘用')
    def click_hire(self) -> OperationRoundResult:
        """
        点击右下角的聘用按钮
        :return:
        """
        screen = self.screenshot()
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        
        target_word_list: list[str] = ['聘用']
        word, mrl = ocr_utils.match_word_list_by_priority(ocr_result_map, target_word_list)
        
        if word == '聘用':
            if mrl.max is not None:
                self.ctx.controller.click(mrl.max.center)
                self.bought_bangboo = True
                return self.round_success(status='点击聘用', wait=4)
            else:
                return self.round_retry(status='聘用按钮位置异常', wait=1)
        
        return self.round_retry(status='未找到聘用按钮', wait=1)

    @node_from(from_name='点击聘用', status='点击聘用')
    @operation_node(name='跳过动画')
    def skip_animation(self) -> OperationRoundResult:
        """
        等待动画播放完成，或尝试跳过动画
        :return:
        """
        screen = self.screenshot()
        
        # 方法1：先等待2秒让动画加载，然后尝试点击跳过
        time.sleep(2)
        screen = self.screenshot()
        
        # 使用OCR查找跳过按钮
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        target_word_list: list[str] = ['跳过']
        word, mrl = ocr_utils.match_word_list_by_priority(ocr_result_map, target_word_list)
        
        if word == '跳过' and mrl.max is not None:
            self.ctx.controller.click(mrl.max.center)
            return self.round_wait(status='跳过动画完成', wait=1)
        
        # 方法2：如果找不到跳过按钮，尝试使用预定义坐标
        result = self.round_by_find_and_click_area(screen, '邦巢', '跳过', retry_wait=1)
        if result.is_success:
            return self.round_wait(status='跳过动画完成', wait=1)
        
        # 方法3：如果都找不到跳过按钮，直接等待动画播放完成（约8秒）
        return self.round_wait(status='等待动画播放完成', wait=8)

    @node_from(from_name='跳过动画', status='跳过动画完成')
    @node_from(from_name='跳过动画', status='等待动画播放完成')
    @operation_node(name='返回界面')
    def return_interface(self) -> OperationRoundResult:
        """
        返回邦巢界面
        :return:
        """
        # 确保动画完全结束，再多等待2秒
        time.sleep(2)
        screen = self.screenshot()
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        
        target_word_list: list[str] = ['返回']
        word, mrl = ocr_utils.match_word_list_by_priority(ocr_result_map, target_word_list)
        
        if word == '返回' and mrl.max is not None:
            self.ctx.controller.click(mrl.max.center)
            return self.round_wait(status='继续检查邦布', wait=2)
        
        # 如果没有找到返回按钮，尝试按ESC键返回
        self.ctx.controller.btn_controller.tap('esc')
        return self.round_wait(status='继续检查邦布', wait=2)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = BooboxApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()