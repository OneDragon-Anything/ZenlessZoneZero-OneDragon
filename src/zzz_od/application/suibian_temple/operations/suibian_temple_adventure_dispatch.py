from enum import StrEnum

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleAdventureDispatchDuration(StrEnum):

    MIN_3 = '3分钟'
    MIN_15 = '15分钟'
    HOUR_1 = '1小时'
    HOUR_2 = '2小时'
    HOUR_6 = '6小时'
    HOUR_12 = '12小时'
    HOUR_20 = '20小时'


class SuibianTempleAdventureDispatch(ZOperation):

    """
    随便观-游历派遣
    已经选择了副本之后使用

    1. 选择时间
    2. 自动选择邦布
    3. 派遣

    """

    STATUS_CANT_DISPATCH: str = '无法完成派遣'

    def __init__(self, ctx: ZContext, duration: SuibianTempleAdventureDispatchDuration):
        ZOperation.__init__(self, ctx, op_name=gt('随便观-游历派遣', 'game'))

        self.duration: SuibianTempleAdventureDispatchDuration = duration
        self.chosen_duration: bool = False

    @operation_node(name='检查画面', is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        screen = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-游历'])
        if screen is None:
            return self.round_retry(status='未识别当前画面', wait=1)
        else:
            return self.round_success()

    @node_from(from_name='检查画面')
    @operation_node(name='选择游历时间')
    def choose_period(self) -> OperationRoundResult:
        target_word_list = []
        ignore_word_list = []
        if not self.chosen_duration:
            target_word_list.append(str(self.duration))
            for i in SuibianTempleAdventureDispatchDuration:
                if i != self.duration:
                    target_word_list.append(str(i))
                    ignore_word_list.append(str(i))

        target_word_list.append('确认')

        result = self.round_by_ocr_and_click_by_priority(
            target_cn_list=target_word_list,
            ignore_cn_list=ignore_word_list,
            area=self.ctx.screen_loader.get_area('随便观-游历', '弹窗-游历时间选择')
        )
        if result.is_success:
            if result.status == '确认':
                return self.round_success(status=result.status, wait=1)
            else:
                self.chosen_duration = True

            return self.round_wait(status=result.status, wait=1)

        result = self.round_by_ocr(
            screen=self.last_screenshot,
            target_cn='提前收获',
        )
        if result.is_success:
            return self.round_success(status=result.status, wait=1)

        # 没有弹窗相关点击时 点击按钮显示弹窗
        self.round_by_click_area('随便观-游历', '按钮-选择时间')
        return self.round_retry(status='未识别弹窗', wait=2)

    @node_from(from_name='选择游历时间', status='确认')
    @operation_node(name='游历时间弹窗确认', node_max_retry_times=1)
    def choose_period_confirm_dialog(self) -> OperationRoundResult:
        target_word_list = [
            '确认'
        ]
        return self.round_by_ocr_and_click_by_priority(
            target_cn_list=target_word_list,
            success_wait=1,
            retry_wait=0.3,
        )

    @node_from(from_name='游历时间弹窗确认')
    @node_from(from_name='游历时间弹窗确认', success=False)
    @operation_node(name='点击自动选择邦布')
    def click_auto_choose(self) -> OperationRoundResult:
        # 邦布电量不足 会不显示自动选择邦布 因此直接点击图标 issue 1179
        return self.round_by_click_area(screen_name='随便观-游历', area_name='按钮-自动选择邦布',
                                        success_wait=1, retry_wait=1)

    @node_from(from_name='点击自动选择邦布')
    @operation_node(name="点击派遣")
    def click_dispatch(self) -> OperationRoundResult:
        target_word_list = [
            '邦布电量不足',
            '派遣',
            '可派遣小队',
        ]
        ignore_word_list = [
            '可派遣小队',
        ]
        return self.round_by_ocr_and_click_by_priority(
            target_cn_list=target_word_list,
            ignore_cn_list=ignore_word_list,
            success_wait=1,
            retry_wait=1,
        )

    @node_from(from_name='点击派遣', status='派遣')
    @operation_node(name='点击派遣弹窗确认', node_max_retry_times=1)
    def click_dispatch_confirm_dialog(self) -> OperationRoundResult:
        target_word_list = [
            '确认'
        ]
        return self.round_by_ocr_and_click_by_priority(
            target_cn_list=target_word_list,
            success_wait=1,
            retry_wait=0.3,
        )

    @node_from(from_name='选择游历时间', status='提前收获')
    @operation_node(name='已派遣')
    def already_dispatch(self) -> OperationRoundResult:
        return self.round_success(status='已派遣')

    @node_from(from_name='点击派遣', status='邦布电量不足')
    @node_from(from_name='点击派遣弹窗确认', status='确认')
    @operation_node(name='无法派遣')
    def cant_dispatch(self) -> OperationRoundResult:
        return self.round_success(status=SuibianTempleAdventureDispatch.STATUS_CANT_DISPATCH)

    @node_from(from_name='点击派遣弹窗确认', success=False)  # 没有出现对话框的确认就是成功
    @operation_node(name='派遣成功')
    def dispatch_success(self) -> OperationRoundResult:
        return self.round_success(status='派遣成功')


def __debug() -> None:
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()

    op = SuibianTempleAdventureDispatch(ctx, SuibianTempleAdventureDispatchDuration.HOUR_20)
    op.execute()
    ctx.run_context.stop_running()
    ctx.after_app_shutdown()


if __name__ == '__main__':
    __debug()