from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleAutoManage(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 自动托管

        需要在随便观主界面 或者 打开了自动托管界面时候调用，完成后返回随便观主界面

        Args:
            ctx: 上下文
        """
        ZOperation.__init__(self, ctx,
                            op_name=f'{gt("随便观", "game")} {gt("自动托管", "game")}')

    @operation_node(name='检查并停止托管', is_start_node=True)
    def check_and_stop_hosting(self) -> OperationRoundResult:
        target_cn_list = ['停止托管', '开始托管', '领取收益', '确认', '托管中', '自动托管中', '可关闭自动托管进行手动操作', '经营方针', '经营']
        ignore_cn_list = ['自动托管中', '可关闭自动托管进行手动操作', '经营']
        area = self.ctx.screen_loader.get_area('随便观-入口', '区域-左半屏')
        result = self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list, area=area)
        if result.is_success:
            if result.status == '停止托管':
                return self.round_success(status='点击停止')
            elif result.status == '开始托管' or result.status == '经营方针':
                return self.round_success(status='点击开始托管')
            elif result.status == '领取收益':
                return self.round_wait(status='点击领奖', wait=1)
            elif result.status == '确认':
                return self.round_wait(status='点击确认', wait=1)
            elif result.status == '托管中':
                return self.round_wait(status='点击进入托管详情', wait=1)
            # elif result.status == '经营方针':
            #     return self.round_wait(status='开始新的托管', wait=1)

        return self.round_retry(status='未识别有效按钮', wait=1)

    @node_from(from_name='检查并停止托管', status='点击停止')
    @operation_node(name='确认结算')
    def confirm_stop_1(self) -> OperationRoundResult:
        return self.round_by_ocr_and_click_by_priority(['确认'], success_wait=1, retry_wait=1)

    @node_from(from_name='确认结算')
    @operation_node(name='重新开始托管')
    def start_hosting_after_stop(self) -> OperationRoundResult:
        ocr_result = self.ctx.ocr.run_ocr(self.last_screenshot)
        if '获得奖励' in ocr_result:
            self.round_by_ocr_and_click_by_priority(['确认'], success_wait=1, retry_wait=1)
        return self.round_by_ocr_and_click_by_priority(['开始托管'], success_wait=1, retry_wait=1)

    @node_from(from_name='检查并停止托管', status='点击开始托管')
    @operation_node(name='开始托管')
    def start_hosting(self) -> OperationRoundResult:
        return self.round_by_ocr_and_click_by_priority(['开始托管'], success_wait=1, retry_wait=1)

    # @node_from(from_name='开始托管',status='开始新的托管')
    # @operation_node(name="开始新的托管")
    # def start_new_hosting(self) -> OperationRoundResult:
    #     return self.round_by_ocr_and_click_by_priority(['开始托管'], success_wait=1, retry_wait=1)

    @node_from(from_name='重新开始托管')
    @operation_node(name='返回随便观')
    def back_to_entry(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        target_cn_list = [
            '确认'
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'

    op = SuibianTempleAutoManage(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
