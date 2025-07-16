from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.hollow_runner import HollowRunner


class HollowZeroDebugApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='hollow_zero_debug',
            op_name=gt('零号空洞-调试'),
            run_record=None
        )

        self.mission_name: str = '内部'
        self.mission_type_name: str = '旧都列车'

    def handle_init(self):
        mission_name = self.ctx.hollow_zero_config.mission_name
        idx = mission_name.find('-')
        if idx != -1:
            self.mission_name = mission_name[idx+1:]
            self.mission_type_name = mission_name[:idx]
        else:
            self.mission_name = mission_name
            self.mission_type_name = mission_name

    @operation_node(name='自动运行', is_start_node=True)
    def auto_run(self) -> OperationRoundResult:
        self.ctx.hollow.init_level_info(self.mission_type_name, self.mission_name)
        self.ctx.hollow.init_event_yolo(self.ctx.model_config.hollow_zero_event_gpu)
        op = HollowRunner(self.ctx)
        return self.round_by_op_result(op.execute())
