from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
import zzz_od.application.notify.push as Push
from typing import List
from datetime import datetime, timedelta
import zzz_od.application.zzz_one_dragon_app as app
from one_dragon.base.operation.application_run_record import AppRunRecord

class NotifyApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(self, ctx, 'notify',
                              op_name=gt('通知', 'ui'),
                              need_check_game_win=False,
                               run_record=ctx.notify_record)

    @operation_node(name='发送通知', is_start_node=True)
    def notify(self) -> OperationRoundResult:
        """
        发送通知
        :return:
        """
        if self.ctx.notify_config.notify_method == 'DISABLED':
            return self.round_fail('未启用通知')
        Push.push_config['HITOKOTO'] = 'false'

        def is_within_time(time_str):
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
            for candidate in candidates:
                # 检查候选时间是否在最近三小时内且不超过当前时间
                if start_time <= candidate <= end_time:
                    return True
            return False

        # 消息格式化
        def format_message(results: List[ZApplication]) -> str:
            success = []
            failure = []

            for item in results:
                if is_within_time(item.run_record.run_time):
                    if item.run_record.run_status_under_now == AppRunRecord.STATUS_SUCCESS:
                        success.append(item.op_name)
                    if item.run_record.run_status_under_now == AppRunRecord.STATUS_FAIL:
                        failure.append(item.op_name)

            parts = [f"OneDragon执行完成："]
            if failure:
                parts.append(f"❌ 失败指令：{', '.join(failure)}")
            else:
                parts.append(f"全部成功✅")
            if success:
                parts.append(f"成功指令：{', '.join(success)}")
            else:
                parts.remove(f"全部成功✅")
                parts.append(f"全部失败❌")
            return "\n".join(parts) if parts else "⚠️ 未检测到有效指令状态"  
        
        message = format_message(app.ZOneDragonApp.get_app_list(self))


        for k in Push.push_config:
            if self.ctx.notify_config.get(k.lower()) and k.lower().startswith(self.ctx.notify_config.notify_method.lower()):
                Push.push_config[k] = self.ctx.notify_config.get(k.lower())
        Push.send("绝区零一条龙运行通知",message,Push.push_config)
        

        
        return self.round_success(wait=5)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = NotifyApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()