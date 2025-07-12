import time

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import resonium_utils
from zzz_od.operation.zzz_operation import ZOperation


class DropResoniumBase(ZOperation):

    def __init__(self, ctx: ZContext, drop_cn: str):
        """
        在选择鸣徽的画面了 选择一个
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name=gt('丢弃鸣徽', 'game')
        )

        self.drop_cn: str = drop_cn

    @operation_node(name='选择', is_start_node=True)
    def choose_one(self) -> OperationRoundResult:
        screen = self.screenshot()

        item_list = resonium_utils.get_to_choose_list(self.ctx, screen, self.drop_cn)
        if len(item_list) == 0:
            return self.round_retry(status='识别不到选项', wait=0.5)

        idx_list = resonium_utils.choose_resonium_by_priority([i.data for i in item_list],
                                                              self.ctx.hollow_zero_challenge_config.resonium_priority)
        if len(idx_list) == 0:
            return self.round_retry(status='优先级无返回', wait=0.5)

        mr = item_list[idx_list[-1]]  # 丢弃优先级最低的
        self.ctx.controller.click(mr.center)
        time.sleep(0.1)
        return self.round_by_click_area('零号空洞-事件', '空白', success_wait=0.9)

    @node_from(from_name='选择', success=False)  # 防止识别有问题 兜底随便选一个
    @operation_node(name='兜底选择')
    def choose_default(self):
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('零号空洞-事件', '底部-选择列表')
        return self.round_by_ocr_and_click(screen, self.drop_cn, area=area,
                                           success_wait=1, retry_wait=1)


class DropResonium(DropResoniumBase):

    def __init__(self, ctx: ZContext):
        DropResoniumBase.__init__(self, ctx, '丢弃')


class DropResonium2(DropResoniumBase):

    def __init__(self, ctx: ZContext):
        DropResoniumBase.__init__(self, ctx, '抵押欠款')