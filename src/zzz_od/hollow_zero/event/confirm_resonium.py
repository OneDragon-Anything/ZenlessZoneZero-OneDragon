from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class ConfirmResonium(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        在选择鸣徽的画面了 选择一个
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name=gt('确认鸣徽', 'game')
        )

    @operation_node(name='选择', is_start_node=True)
    def choose_one(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('零号空洞-事件', '底部-选择列表')
        result = self.round_by_ocr_and_click(screen, '确认', area=area)
        if result.is_success:
            return self.round_success(wait=1)
        result = self.round_by_ocr_and_click(screen, '确定', area=area)
        if result.is_success:
            return self.round_success(wait=1)

        return self.round_retry(result.status, wait=1)
