import time

import cv2

from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils
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

    @operation_node(name='识别初始画面', is_start_node=True)
    def check_initial_screen(self) -> OperationRoundResult:
        screen = self.screenshot()

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

        # 检查是否已经在邦巢界面，优先检查"聘用"
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        for text in ocr_result_map.keys():
            if '次数用尽' in text:
                op = BackToNormalWorld(self.ctx)
                return self.round_by_op_result(op.execute())
            if '聘用' in text:  # 检查文本中是否包含'聘用'字样
                return self.round_success(status='已进入邦巢界面')


        # 尝试点击邦巢
        boobox_list: list[str] = ['邦巢']
        result = self.round_by_ocr_and_click_by_priority(screen, boobox_list)
        if result.is_success:
            return self.round_wait(status='点击邦巢', wait=2)

        return self.round_retry(status='未找到邦巢按钮', wait=1)


    @node_from(from_name='点击邻里街坊', status='已在邦巢界面')
    @node_from(from_name='点击邻里街坊', status='已进入邦巢界面')
    @node_from(from_name='点击邦巢', status='已进入邦巢界面')
    @node_from(from_name='点击邦巢', status='点击邦巢')
    @node_from(from_name='检查邦布', status='刷新邦布')
    @node_from(from_name='跳过动画')
    @node_from(from_name='返回界面')
    @operation_node(name='检查邦布')
    def check_bangboo(self) -> OperationRoundResult:
        """
        检查邦布的主逻辑：有S级就购买，没有S级就刷新
        :return:
        """
        screen = self.screenshot()
        ocr_result_map = self.ctx.ocr.run_ocr(screen)

        # 检查是否有S级邦布
        if 'S' in ocr_result_map:
            s_results = ocr_result_map['S']
            if len(s_results) > 0:
                # 依次点击所有S级邦布
                for s_result in s_results:
                    self.ctx.controller.click(s_result.center)
                    time.sleep(0.5)  # 点击间隔
                return self.round_success(status='点击S级邦布完成')
        
                # 如果没有S级邦布，检查刷新按钮
        refresh_found = False
        refresh_flag=0
        for text, results in ocr_result_map.items():
            if '刷新' in text:  # 检查文本中是否包含'刷新'字样
                 # 第二个刷新才是刷新
                if len(results) > 0:
                    if refresh_flag==0:
                        refresh_flag=1
                        continue
                    else:
                        self.ctx.controller.click(results[0].center)
                        refresh_found = True

                    continue

        if refresh_found:
            return self.round_wait(status='刷新邦布', wait=4)
        else:
            return self.round_retry(status='未找到刷新按钮', wait=1)

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

    @node_from(from_name='点击聘用',status='点击聘用')
    @operation_node(name='跳过动画')
    def skip_animation(self) -> OperationRoundResult:
        """
        OCR点击跳过按钮
        :return:
        """
        screen = self.screenshot()
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        
        target_word_list: list[str] = ['跳过']
        word, mrl = ocr_utils.match_word_list_by_priority(ocr_result_map, target_word_list)
        
        if word == '跳过':
            if mrl.max is not None:
                self.ctx.controller.click(mrl.max.center)
                return self.round_success()
            else:
                return self.round_retry(status='跳过按钮位置异常', wait=1)
        
        return self.round_retry(status='未找到跳过按钮', wait=1)

    @node_from(from_name='跳过动画')
    @operation_node(name='返回界面')
    def return_interface(self) -> OperationRoundResult:
        """
        按下返回按钮
        :return:
        """
        screen = self.screenshot()
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        
        target_word_list: list[str] = ['返回']
        word, mrl = ocr_utils.match_word_list_by_priority(ocr_result_map, target_word_list)
        
        if word == '返回':
            if mrl.max is not None:
                self.ctx.controller.click(mrl.max.center)
                return self.round_success(status='操作完成')
            else:
                return self.round_retry(status='返回按钮位置异常', wait=1)
        
        # 如果没有找到返回按钮，尝试按ESC键
        self.ctx.controller.btn_controller.tap('escape')
        return self.round_success(status='使用ESC返回')

def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = BooboxApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()