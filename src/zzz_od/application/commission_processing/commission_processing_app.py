from zzz_od.application.commission_processing import commission_processing_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.commission_processing.commission_processing import CommissionProcessing
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult

class CommissionProcessingApp(ZApplication):
    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=commission_processing_const.APP_ID,
            op_name=commission_processing_const.APP_NAME,
        )

    @operation_node(name='委托处理', is_start_node=True)
    def commission_processing(self) -> OperationRoundResult:
        op = CommissionProcessing(self.ctx)
        return self.round_by_op_result(op.execute())

def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = CommissionProcessingApp(ctx)
    app.execute()

if __name__ == '__main__':
    __debug()
