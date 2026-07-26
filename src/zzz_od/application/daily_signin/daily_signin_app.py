from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.daily_signin import daily_signin_const
from zzz_od.application.daily_signin.daily_signin_config import (
    DailySignInConfig,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class DailySignInApp(ZApplication):
    """每日签到应用

    流程: 代理运行用户所选的具体每日签到应用（吼吼饼铺、卦象集录、刮刮卡）。
    """

    def __init__(self, ctx: ZContext, instance_idx: int, group_id: str):
        """初始化每日签到应用。

        Args:
            ctx: 运行上下文。
            instance_idx: 账号实例索引。
            group_id: 组ID。
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=daily_signin_const.APP_ID,
            op_name=daily_signin_const.APP_NAME,
        )
        self.instance_idx: int = instance_idx
        self.group_id: str = group_id
        self.config: DailySignInConfig = self.ctx.run_context.get_config(
            app_id=daily_signin_const.APP_ID,
            instance_idx=self.instance_idx,
            group_id=self.group_id,
        )

    @operation_node(name='运行子应用', is_start_node=True)
    def run_sub_app(self) -> OperationRoundResult:
        """根据配置的商店，代理运行具体的签到子应用。"""
        sub_app_id: str = self.config.selected_sign
        if not sub_app_id:
            return self.round_fail(status='未选择子应用')

        app = self.ctx.run_context.get_application(
            app_id=sub_app_id,
            instance_idx=self.instance_idx,
            group_id=self.group_id,
        )
        if app is None:
            return self.round_fail(status=f'未找到应用 {sub_app_id}')

        # 临时切换 current_app_id 以便子应用正常记录和运行
        old_app_id = self.ctx.run_context.current_app_id
        self.ctx.run_context.current_app_id = app.app_id

        try:
            result = app.execute()
            if result.success:
                return self.round_success()
            else:
                return self.round_fail(status=result.status)
        finally:
            self.ctx.run_context.current_app_id = old_app_id


def __debug() -> None:
    """本地调试入口: 初始化上下文并运行。"""
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = DailySignInApp(ctx, ctx.current_instance_idx, application_const.DEFAULT_GROUP_ID)
    app.execute()


if __name__ == '__main__':
    __debug()
