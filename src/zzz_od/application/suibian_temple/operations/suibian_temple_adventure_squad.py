from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleAdventureSquad(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 游历

        需要在游历画面时候调用，完成后返回随便观主界面

        操作步骤
        1. 点击游历小队
        2. 点击游历完成，如果有的话
            2.1. 点击 可收获 -> 确认
            2.2. 点击 自动选择邦布
            2.3. 邦布电量不足 -> 进入第3步
            2.4. 派遣 -> 返回第1步
        3. 没有游历完成了，返回到游历的主界面
        4. 点击 可派遣小队，如果有的话
            4.1. 点击自动选择邦布
            4.2. 判断是否有 邦布电量不足，如果没有，则点击 派遣
            4.3. 邦布电量不足 -> 进入第5步
            4.4. 派遣 -> 返回游历主界面，返回第1步
        5. 返回随便观
        Args:
            ctx: 上下文
        """
        ZOperation.__init__(self, ctx,
                            op_name=f'{gt("随便观", "game")} {gt("游历", "game")}')

    @node_from(from_name='点击派遣')
    @operation_node(name='点击游历小队', is_start_node=True)
    def click_squad_team(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '游历小队',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)

    @node_from(from_name='点击游历小队', status='游历小队')
    @operation_node(name='点击游历完成')
    def click_finish(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '游历完成',
            '游历小队',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)

    @node_from(from_name='点击游历完成', status='游历完成')
    @operation_node(name='点击可收获')
    def click_claim(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '可收获',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)

    @node_from(from_name='点击可收获', status='可收获')
    @operation_node(name='点击确认')
    def click_confirm(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '确认',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)

    @node_from(from_name='点击确认', status='确认')
    @operation_node(name='点击自动选择邦布')
    def click_auto_choose(self) -> OperationRoundResult:
        # 邦布电量不足 会不显示自动选择邦布 因此直接点击图标 issue 1179
        return self.round_by_click_area(screen_name='随便观-游历', area_name='按钮-自动选择邦布',
                                        success_wait=1, retry_wait=1)

    @node_from(from_name='点击自动选择邦布')
    @operation_node(name='点击派遣')
    def click_dispatch(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '邦布电量不足',
            '派遣',
            '待派遣小队',
            '可派遣小队',
        ]
        ignore_cn_list: list[str] = [
            '待派遣小队',
            '可派遣小队',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list,
                                                       success_wait=1, retry_wait=1)

    @node_from(from_name='点击游历完成', success=False)
    @node_from(from_name='点击游历完成', status='游历小队')
    @node_from(from_name='可派遣小队点击派遣', status='派遣')
    @operation_node(name='点击可派遣小队')
    def click_dispatch_team(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '可派遣小队',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, success_wait=1, retry_wait=1)

    @node_from(from_name='点击可派遣小队')
    @operation_node(name='可派遣小队点击自动选择邦布')
    def click_auto_choose_2(self) -> OperationRoundResult:
        # 邦布电量不足 会不显示自动选择邦布 因此直接点击图标 issue 1179
        return self.round_by_click_area(screen_name='随便观-游历', area_name='按钮-自动选择邦布',
                                        success_wait=1, retry_wait=1)

    @node_from(from_name='可派遣小队点击自动选择邦布')
    @operation_node(name='可派遣小队点击派遣')
    def click_dispatch_2(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '邦布电量不足',
            '派遣',
            '待派遣小队',
            '可派遣小队',
            '游历小队',  # 用这个来判断没有 '派遣'
        ]
        ignore_cn_list: list[str] = [
            '待派遣小队',
            '可派遣小队',
        ]
        return self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list,
                                                       success_wait=1, retry_wait=1)

    @node_from(from_name='点击可派遣小队', success=False)
    @node_from(from_name='可派遣小队点击派遣', status='邦布电量不足')
    @node_from(from_name='可派遣小队点击派遣', status='游历小队')
    @operation_node(name='返回随便观')
    def back_to_entry(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.start_running()
    op = SuibianTempleAdventureSquad(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()