from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_squad import SuibianTempleAdventureSquad
from zzz_od.application.suibian_temple.operations.suibian_temple_craft import SuibianTempleCraft
from zzz_od.application.suibian_temple.operations.suibian_temple_yum_cha_sin import SuibianTempleYumChaSin
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class SuibianTempleApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='suibian_temple',
            op_name=gt('随便观'),
            run_record=ctx.suibian_temple_record,
            retry_in_od=True,  # 传送落地有可能会歪 重试
            need_notify=True,
        )

    @operation_node(name='识别初始画面', is_start_node=True)
    def check_initial_screen(self) -> OperationRoundResult:
        # 检查随便观总开关是否启用
        if not self.ctx.suibian_temple_config.overall_enabled:
            log.info('随便观总开关已禁用，跳过所有随便观相关功能')
            return self.round_success(status='随便观总开关已禁用，所有功能已跳过')

        current_screen_name, can_go = self.check_screen_with_can_go(self.last_screenshot, '快捷手册-目标')
        if can_go is not None and can_go == True:
            return self.round_by_goto_screen(self.last_screenshot, '快捷手册-目标',
                                             success_wait=1, retry_wait=1)

        current_screen_name, can_go = self.check_screen_with_can_go(self.last_screenshot, '随便观-入口')
        if can_go is not None and can_go == True:
            return self.round_success(status='随便观-入口')

        return self.round_retry(status='未识别初始画面', wait=1)

    @node_from(from_name='识别初始画面', status='未识别初始画面', success=False)
    @operation_node(name='开始前返回大世界')
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别初始画面', status='快捷手册-目标')
    @node_from(from_name='开始前返回大世界')
    @operation_node(name='前往快捷手册-目标')
    def goto_category(self) -> OperationRoundResult:
        return self.round_by_goto_screen(self.last_screenshot, '快捷手册-目标')

    @node_from(from_name='前往快捷手册-目标')
    @operation_node(name='前往随便观', node_max_retry_times=10)
    def goto_suibian_temple(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '前往随便观',
            '确认',
        ]

        result = self.round_by_ocr_and_click_by_priority(target_cn_list)
        if result.is_success:
            if result.status == '累计获得称愿':
                self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
            return self.round_wait(status=result.status, wait=1)

        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='识别初始画面', status='随便观-入口')
    @node_from(from_name='前往随便观')
    @operation_node(name='前往游历')
    def goto_adventure(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot, '随便观-入口', '按钮-游历',
            success_wait=1, retry_wait=1,
            until_not_find_all=[('随便观-入口', '按钮-游历')]
        )

    @node_from(from_name='前往游历')
    @operation_node(name='处理游历')
    def handle_adventure_squad(self) -> OperationRoundResult:
        # 检查小队游历功能是否启用
        if not self.ctx.suibian_temple_config.adventure_squad_enabled:
            log.info('小队游历功能已禁用，跳过执行')
            return self.round_success(status='小队游历功能已跳过')

        op = SuibianTempleAdventureSquad(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理游历')
    @operation_node(name='前往经营')
    def goto_business(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot, '随便观-入口', '按钮-经营',
            success_wait=1, retry_wait=1,
            until_not_find_all=[('随便观-入口', '按钮-经营')]
        )

    @node_from(from_name='前往经营')
    @operation_node(name='前往制造')
    def goto_craft(self) -> OperationRoundResult:
        return self.round_by_ocr_and_click(self.last_screenshot, '制造', success_wait=1, retry_wait=1)

    @node_from(from_name='前往制造')
    @operation_node(name='处理制造坊')
    def handle_craft(self) -> OperationRoundResult:
        # 检查制造坊功能是否启用
        if not self.ctx.suibian_temple_config.craft_enabled:
            log.info('制造坊功能已禁用，跳过执行')
            return self.round_success(status='制造坊功能已跳过')

        op = SuibianTempleCraft(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理制造坊')
    @operation_node(name='前往饮茶仙')
    def goto_yum_cha_sin(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-饮茶仙'])
        if current_screen_name is not None:
            # 引入饮茶仙前做一些初始化
            self.last_yum_cha_opt = ''
            self.last_yum_cha_period = False
            return self.round_success(status=current_screen_name)

        target_cn_list: list[str] = [
            '邻里街坊',
            '饮茶仙',
        ]
        ignore_cn_list: list[str] = [
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='前往饮茶仙')
    @operation_node(name='处理饮茶仙')
    def handle_yum_cha_sin_submit(self) -> OperationRoundResult:
        # 检查饮茶仙功能是否启用
        if not self.ctx.suibian_temple_config.yum_cha_sin_enabled:
            log.info('饮茶仙功能已禁用，跳过执行')
            return self.round_success(status='饮茶仙功能已跳过')

        op = SuibianTempleYumChaSin(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理饮茶仙')
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = SuibianTempleApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
