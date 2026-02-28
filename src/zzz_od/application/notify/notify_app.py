from datetime import datetime, timedelta

from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.charge_plan.charge_plan_run_record import ChargePlanRunRecord
from zzz_od.application.notify import notify_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class NotifyApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx,
            notify_const.APP_ID,
            op_name=notify_const.APP_NAME,
            need_check_game_win=True,
        )

    @operation_node(name='发送通知', is_start_node=True)
    def notify(self) -> OperationRoundResult:
        """
        发送通知
        :return:
        """
        self.exist_failure = False

        message = self.format_message()

        self.ctx.push_service.push(
            title=self.ctx.notify_config.title,
            content=message,
            image=self.last_screenshot
        )

        if self.exist_failure:
            return self.round_fail(wait=5)
        else:
            return self.round_success(wait=5)

    # 消息格式化
    def format_message(self) -> str:
        success = []
        failure = []
        charge_power_text = None

        group_config = self.ctx.app_group_manager.get_one_dragon_group_config(instance_idx=self.ctx.current_instance_idx)
        for app_config in group_config.app_list:
            run_record: AppRunRecord = self.ctx.run_context.get_run_record(
                app_id=app_config.app_id,
                instance_idx=self.ctx.current_instance_idx
            )
            if run_record is None:
                continue
            if not self.is_within_time(run_record.run_time):
                continue
            if isinstance(run_record, ChargePlanRunRecord):
                charge_power = run_record.get_estimated_charge_power()
                if charge_power is not None:
                    charge_power_text = (
                        f'当前体力：{charge_power}/{ChargePlanRunRecord.MAX_CHARGE_POWER}'
                    )
            if run_record.run_status_under_now == AppRunRecord.STATUS_SUCCESS:
                success.append(app_config.app_name)
            if run_record.run_status_under_now == AppRunRecord.STATUS_FAIL:
                failure.append(app_config.app_name)
                self.exist_failure = True

        parts = ["一条龙运行完成："]
        if charge_power_text is not None:
            parts.append(charge_power_text)
        has_failure = bool(failure)
        has_success = bool(success)

        if has_failure:
            parts.append(f"❌ 失败指令：{', '.join(failure)}")
        elif has_success:
            parts.append("全部成功✅")

        if has_success:
            parts.append(f"✅ 成功指令：{', '.join(success)}")
        elif not has_failure:
            parts.append("全部失败❌")

        return "\n".join(parts)

    def is_within_time(self, time_str: str) -> bool:
        end_time = datetime.now()
        try:
            # 解析输入的时间字符串，格式为月-日 时:分
            parsed_time = datetime.strptime(time_str, "%m-%d %H:%M")
        except ValueError:
            # 时间格式不正确
            return False

        candidates = []
        # 生成当前年份和前一年的候选时间
        for year in [end_time.year, end_time.year - 1]:
            try:
                candidate = parsed_time.replace(year=year)
                candidates.append(candidate)
            except ValueError:
                # 处理无效日期（如闰年的2月29日）
                continue

        start_time = end_time - timedelta(hours=3)
        # 检查候选时间是否在最近三小时内且不超过当前时间
        return any(start_time <= candidate <= end_time for candidate in candidates)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = NotifyApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
