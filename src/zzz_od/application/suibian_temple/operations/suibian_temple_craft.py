from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.suibian_temple.operations.suibian_temple_craft_dispatch import SuibianTempleCraftDispatch
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


MAX_GOTO_CLICK_TIMES: int = 5  # 前往目标画面时最多点击的次数
MAX_BACK_CLICK_TIMES: int = 10  # 返回随便观时最多点击的次数

class SuibianTempleCraft(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 制造

        需要在随便观主界面时候调用，完成后返回随便观主界面

        操作步骤
        0. 前往制造台画面(可看见开工)
        1. 点击开工，没有 -> 最后一步
        2. 所需材料不足 -> 选择新的商品
        3. 没有新的商品 -> 最后一步
        4. 制造
        5. 返回随便观
        Args:
            ctx: 上下文
        """
        ZOperation.__init__(
            self, ctx, op_name=f"{gt('随便观', 'game')} {gt('制造', 'game')}"
        )
        self.config: SuibianTempleConfig = self.ctx.run_context.get_config(
            app_id="suibian_temple",
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.last_item_list: list[str] = []  # 上一次的商品列表
        self.chosen_item_list: list[str] = []  # 已经选择过的商品列表
        self.scroll_after_choose: bool = False  # 选择后是否已经滑动了
        self.drag_times: int = 0  # 下拉次数
        self.goto_click_times: int = 0  # 前往目标画面的点击次数
        self.back_click_times: int = 0  # 返回随便观的点击次数

    def handle_init(self) -> None:
        ZOperation.handle_init(self)
        self.goto_click_times = 0
        self.back_click_times = 0

    @operation_node(name='前往制造', is_start_node=True)
    def goto_craft(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-制造坊'])
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        # 点击后等待不计入重试次数 需要单独限制 防止点击后画面不变时无限循环
        # 在点击前检查 保证最后一次点击后仍能识别到目标画面
        if self.goto_click_times >= MAX_GOTO_CLICK_TIMES:
            return self.round_fail(status='前往制造失败')

        # 每日首次进入可能弹出 经营日志 其中的 经营 会被误认为经营页签 需要先关闭
        result = self.round_by_ocr(self.last_screenshot, '经营日志', lcs_percent=1)
        if result.is_success:
            result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
            if result.is_success:
                self.goto_click_times += 1
                return self.round_wait(status='关闭经营日志', wait=1)

        target_cn_list: list[str] = [
            '经营日志',
            '经营',
            '制造',
        ]
        ignore_cn_list: list[str] = [
            '经营日志',
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            self.goto_click_times += 1
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='前往制造')
    @node_from(from_name='制造派驻', status='已派驻')
    @operation_node(name='点击开工')
    def click_lets_go(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '开工',
            '开物',
            '制造暂停',
        ]
        ignore_cn_list: list[str] = [
            "开物",
        ]
        self.drag_times = 0
        return self.round_by_ocr_and_click_by_priority(
            target_cn_list=target_cn_list, ignore_cn_list=ignore_cn_list,
            success_wait=1, retry_wait=0.5)

    @node_from(from_name='点击开工')
    @operation_node(name='制造派驻')
    def craft_dispatch(self) -> OperationRoundResult:
        op = SuibianTempleCraftDispatch(
            self.ctx,
            from_craft=True,
            chosen_item_list=self.chosen_item_list,
        )
        op_result = op.execute()
        if op_result.success and op_result.data == True:
            return self.round_success(status='已派驻')
        else:
            return self.round_success(status='派驻失败')

    @node_from(from_name='点击开工', success=False)
    @node_from(from_name='制造派驻', status='派驻失败')
    @node_from(from_name='前往制造', success=False)
    @operation_node(name='返回随便观')
    def back_to_entry(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        # 同样需要限制点击次数 防止点击返回后画面不变时无限循环
        if self.back_click_times >= MAX_BACK_CLICK_TIMES:
            return self.round_fail(status='返回随便观失败')

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            self.back_click_times += 1
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'
    op = SuibianTempleCraft(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
