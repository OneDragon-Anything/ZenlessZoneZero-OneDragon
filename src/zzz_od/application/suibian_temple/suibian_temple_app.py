import cv2

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils
from one_dragon.utils.i18_utils import gt
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

        self.last_squad_opt: str = ''  # 上一次的游历小队选项
        self.chosen_item_list: list[str] = []  # 已经选择过的货品列表
        self.new_item_after_drag: bool = False  # 滑动后是否有新商品

        self.last_yum_cha_opt: str = ''  # 上一次饮茶仙的选项
        self.last_yum_cha_period: bool = False  # 饮茶仙是否点击过定期采购了

    @operation_node(name='识别初始画面', is_start_node=True)
    def check_initial_screen(self) -> OperationRoundResult:
        screen = self.screenshot()

        current_screen_name, can_go = self.check_screen_with_can_go(screen, '快捷手册-目标')
        if can_go is not None and can_go == True:
            return self.round_by_goto_screen(screen, '快捷手册-目标',
                                             success_wait=1, retry_wait=1)

        current_screen_name, can_go = self.check_screen_with_can_go(screen, '随便观-入口')
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
        screen = self.screenshot()
        return self.round_by_goto_screen(screen, '快捷手册-目标')

    @node_from(from_name='前往快捷手册-目标')
    @operation_node(name='前往随便观', node_max_retry_times=10)
    def goto_suibian_temple(self) -> OperationRoundResult:
        screen = self.screenshot()

        target_cn_list: list[str] = [
            '前往随便观',
            '确认',
        ]

        result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list)
        if result.is_success:
            if result.status == '累计获得称愿':
                self.round_by_find_and_click_area(screen, '菜单', '返回')
            return self.round_wait(status=result.status, wait=1)

        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        result = self.round_by_find_and_click_area(screen, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='识别初始画面', status='随便观-入口')
    @node_from(from_name='前往随便观')
    @operation_node(name='前往游历')
    def goto_adventure(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(
            screen, '随便观-入口', '按钮-游历',
            success_wait=1, retry_wait=1,
            until_not_find_all=[('随便观-入口', '按钮-游历')]
        )

    @node_from(from_name='前往游历')
    @operation_node(name='选择游历小队')
    def choose_adventure_squad(self) -> OperationRoundResult:
        screen = self.screenshot()

        target_cn_list: list[str] = [
            '自动选择邦布',
            '邦布电量不足',  # 连续派遣有可能导致电量不足 此时有要跳过 issue 1155
            '派遣',
            '确认',
            '可收获',
            '游历完成',
            '待派遣小队',
            '可派遣小队',  # 空白区域上的提取 用于避免 待派遣小队 匹配错误 需要忽略
            '游历小队',
        ]
        ignore_cn_list: list[str] = [
            '剩余时间',
            '可派遣小队',
        ]
        if self.last_squad_opt == '邦布电量不足':
            # 电量不足的时候不要点派遣
            target_cn_list.remove('派遣')
            target_cn_list.remove('邦布电量不足')

        if self.last_squad_opt in ['游历小队', '自动选择邦布']:  # 不能一直点击
            ignore_cn_list.append(self.last_squad_opt)

        result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            self.last_squad_opt = result.status
            if result.status == '待派遣小队':
                return self.round_retry(status='未识别游历完成小队', wait=1)

            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别游历完成小队', wait=1)

    @node_from(from_name='选择游历小队', success=False)
    @operation_node(name='游历后返回')
    def after_adventure(self) -> OperationRoundResult:
        screen = self.screenshot()

        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        result = self.round_by_find_and_click_area(screen, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='游历后返回')
    @operation_node(name='前往经营')
    def goto_business(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(
            screen, '随便观-入口', '按钮-经营',
            success_wait=1, retry_wait=1,
            until_not_find_all=[('随便观-入口', '按钮-经营')]
        )

    @node_from(from_name='前往经营')
    @operation_node(name='前往制造')
    def goto_craft(self) -> OperationRoundResult:
        self.chosen_item_list = []
        self.new_item_after_drag = False
        screen = self.screenshot()
        return self.round_by_ocr_and_click(screen, '制造', success_wait=1, retry_wait=1)

    @node_from(from_name='前往制造')
    @operation_node(name='开工')
    def click_lets_go(self) -> OperationRoundResult:
        screen = self.screenshot()

        target_cn_list: list[str] = [
            '开工',
            '开物',
        ]
        ignore_cn_list: list[str] = [
            '开物',
        ]
        result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        result = self.round_by_find_area(screen, '随便观-入口', '标题-制造坊')
        if result.is_success:
            target_cn_list: list[str] = [
                '所需材料不足',
                '开始制造',
            ]
            result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list, ignore_cn_list=ignore_cn_list)
            if result.is_success and result.status == '开始制造':
                return self.round_wait(status=result.status, wait=1)

            # 不能制造的 换一个货品
            area = self.ctx.screen_loader.get_area('随便观-入口', '区域-制造坊商品列表')
            part = cv2_utils.crop_image_only(screen, area.rect)
            mask = cv2_utils.color_in_range(part, (230, 230, 230), (255, 255, 255))
            to_ocr_part = cv2.bitwise_and(part, part, mask=mask)
            ocr_result_map = self.ctx.ocr.run_ocr(to_ocr_part)
            for ocr_result, mrl in ocr_result_map.items():
                if mrl.max is None:
                    continue
                if ocr_result in self.chosen_item_list:
                    continue
                self.new_item_after_drag = True
                self.chosen_item_list.append(ocr_result)
                self.ctx.controller.click(area.left_top + mrl.max.right_bottom + Point(50, 0))  # 往右方点击 防止遮挡到货品名称
                return self.round_wait(status='选择下一个货品', wait=1)

            if self.new_item_after_drag:
                # 已经都选择过了 就往下滑动一定距离
                start = area.center
                end = start + Point(0, -300)
                self.ctx.controller.drag_to(start=start, end=end)
                self.new_item_after_drag = False
                return self.round_retry(status='滑动找未选择过的货品', wait=1)

        return self.round_retry(status='未识别开工按钮', wait=1)

    @node_from(from_name='开工', success=False)
    @operation_node(name='制造后返回')
    def after_lets_go(self) -> OperationRoundResult:
        screen = self.screenshot()

        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        result = self.round_by_find_and_click_area(screen, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='制造后返回')
    @operation_node(name='前往饮茶仙')
    def goto_yum_cha_sin(self) -> OperationRoundResult:
        screen = self.screenshot()

        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['随便观-饮茶仙'])
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
        result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)


    @node_from(from_name='前往饮茶仙')
    @operation_node(name='饮茶仙-提交委托')
    def yum_cha_sin_submit(self) -> OperationRoundResult:
        screen = self.screenshot()

        target_cn_list: list[str] = [
            '确认',
            '提交',
            '定期采办',
        ]
        ignore_cn_list: list[str] = []
        if self.last_yum_cha_opt != '':
            ignore_cn_list.append(self.last_yum_cha_opt)
        if self.last_yum_cha_period:
            ignore_cn_list.append('定期采办')

        result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            self.last_yum_cha_opt = result.status
            if result.status == '定期采办':
                self.last_yum_cha_period = True
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未发现可提交委托', wait=1)

    @node_from(from_name='饮茶仙-提交委托', success=False)
    @operation_node(name='饮茶仙后返回')
    def after_yum_cha_sin(self) -> OperationRoundResult:
        screen = self.screenshot()

        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        result = self.round_by_find_and_click_area(screen, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='饮茶仙后返回')
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = SuibianTempleApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
