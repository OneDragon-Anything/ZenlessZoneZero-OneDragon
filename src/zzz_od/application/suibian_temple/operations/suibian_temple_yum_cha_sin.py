from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleYumChaSin(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 饮茶仙

        需要在饮茶仙画面时候调用，完成后返回随便观主界面

        操作步骤
        1. 不断点击 提交
        2. 没法提交则尝试切换到 定期采买
        3. 返回随便观
        Args:
            ctx: 上下文
        """
        ZOperation.__init__(self, ctx,
                            op_name=f'{gt("随便观", "game")} {gt("饮茶仙", "game")}')

        self.last_yum_cha_opt: str = ''  # 上一次饮茶仙的选项
        self.last_yum_cha_period: bool = False  # 饮茶仙是否点击过定期采购了

    @operation_node(name='点击提交', is_start_node=True)
    def click_submit(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '确认',
            '提交',
            '定期采办',
        ]
        ignore_cn_list: list[str] = []
        if self.last_yum_cha_opt != '':
            ignore_cn_list.append(self.last_yum_cha_opt)
        if self.last_yum_cha_period:
            ignore_cn_list.append('定期采办')

        result = self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            self.last_yum_cha_opt = result.status
            if result.status == '定期采办':
                self.last_yum_cha_period = True
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未发现可提交委托', wait=1)

    @node_from(from_name='点击提交', success=False)
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
    ctx.start_running()
    op = SuibianTempleYumChaSin(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
