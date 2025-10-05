from one_dragon_qt.view.one_dragon.one_dragon_run_interface import OneDragonRunInterface
from zzz_od.context.zzz_context import ZContext


class ZOneDragonRunInterface(OneDragonRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        OneDragonRunInterface.__init__(
            self,
            ctx=ctx,
            parent=parent,
            help_url='https://one-dragon.com/zzz/zh/docs/feat_one_dragon.html'
        )
