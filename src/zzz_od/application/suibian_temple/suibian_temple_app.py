import time

import pyautogui
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import node_notify, NotifyTiming
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.suibian_temple import suibian_temple_const
from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_squad import (
    SuibianTempleAdventureSquad,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_auto_manage import SuibianTempleAutoManage
from zzz_od.application.suibian_temple.operations.suibian_temple_boo_box import (
    SuibianTempleBooBox,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_craft import (
    SuibianTempleCraft,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_good_goods import (
    SuibianTempleGoodGoods,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_sales_stall import (
    SuibianTempleSalesStall,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_yum_cha_sin import (
    SuibianTempleYumChaSin,
)
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.transport_by_quick_nav import TransportByQuickNav


class SuibianTempleApp(ZApplication):

    """随便观:澄辉坪经营玩法自动化(游历/制造/售卖/派驻等)。消耗玩法自有资源(开物秘卷/云纹徽/丁尼等)。"""

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=suibian_temple_const.APP_ID,
            op_name=suibian_temple_const.APP_NAME,
        )
        self.config: SuibianTempleConfig = self.ctx.run_context.get_config(
            app_id=suibian_temple_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.shiye_seen: bool = False  # 本次运行里是否见过狮耶（见过又丢时改用原地扫视）

    def handle_init(self) -> None:
        """每次执行前重置运行期状态"""
        super().handle_init()
        self.shiye_seen = False

    @operation_node(name='识别初始画面', is_start_node=True)
    def check_initial_screen(self) -> OperationRoundResult:
        # 特殊兼容 在入口区域开始
        screen_name, _ = self.check_screen_with_can_go(self.last_screenshot, '随便观-入口')

        if screen_name == '随便观-入口':
            return self.round_success(status='随便观-入口')

        return self.round_success('不在随便观')

    @node_from(from_name='识别初始画面', status='不在随便观')
    @operation_node(name='传送')
    def goto_category(self) -> OperationRoundResult:
        op = TransportByQuickNav(self.ctx, '澄辉坪', '随便观',
                                 wait_at_last=False, dest_alias_list=['随便观外庭'])
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='前往随便观', timeout_seconds=180, node_max_retry_times=999)
    def goto_suibian_temple(self) -> OperationRoundResult:
        target_cn_list: list[str] = [
            '前往随便观',
            '确认',
            '领取收益',
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=[])
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        # 再检查是否已进入入口
        current_screen_name = self.check_and_update_current_screen(
            self.last_screenshot, screen_name_list=['随便观-入口']
        )
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        # 领取收益 -> 确认 -> 开始托管
        if self.config.auto_manage_enabled:
            # 注意需要和 "经营日志" 下的 "自动托管" 区分
            result = self.round_by_ocr(self.last_screenshot, target_cn='开始托管', lcs_percent=0.75)
            if result.is_success:
                return self.round_success(status=result.status)

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        # 经营界面打开后，经营日志每日弹窗会盖住识别特征，先关掉它
        ocr_result = self.ctx.ocr_service.get_ocr_result_map(self.last_screenshot, crop_first=False)
        if any('经营日志' in ocr_str for ocr_str in ocr_result):
            self.ctx.controller.click(Point(119, 60))
            return self.round_retry(status='关闭经营日志弹窗', wait=1)

        # 看到狮耶后的三种情况：
        # 1. 对话已打开（对话标题「狮耶」在屏幕底部居中，与 NPC 头顶名字牌区分）：
        #    按交互键推进对话，推进完直接进入经营界面，不处理的话每轮 F 都在对话里空转
        # 2. NPC 名字牌偏离画面中心：转向对准（盲走解决不了交互所需的朝向）
        # 3. 名字牌居中：短前移贴到石台边，再悬停 NPC 本体（名字牌下方约 420px，
        #    悬停后 F 圆钮才亮）按交互键打开对话
        shiye_match = next((mrl.max for ocr_str, mrl in ocr_result.items() if '狮耶' in ocr_str), None)
        if shiye_match is not None:
            self.shiye_seen = True
            if shiye_match.center.y > 700:
                # NPC 对话要用鼠标左键推进（F 只负责打开对话，在对话里按 F 无效）
                self.ctx.controller.click(Point(960, 930), press_time=0.001)
                return self.round_retry(status='推进狮耶对话', wait=1)

            dx = shiye_match.center.x - 1920 / 2
            if abs(dx) > 250:
                # turn_by_angle_diff 正角度为逆时针（向左转），NPC 偏左时 dx<0 应左转
                angle_diff = max(-25, min(25, -0.04 * dx))
                self.ctx.controller.turn_by_angle_diff(angle_diff)
                return self.round_retry(status='转向狮耶', wait=0.6)

            self.ctx.controller.move_w(press=True, press_time=0.5, release=True)
            # OCR 坐标是游戏内坐标，悬停前先转成屏幕坐标（含窗口位置/缩放/标题栏偏移）
            hover_pos = self.ctx.controller.game_win.game2win_pos(
                Point(shiye_match.center.x + 20, shiye_match.center.y + 420))
            if hover_pos is not None:
                pyautogui.moveTo(hover_pos.x, hover_pos.y, duration=0.2)
            time.sleep(0.4)
            self.ctx.controller.interact(press=True, press_time=0.2, release=True)
            return self.round_retry(status='贴近狮耶并交互', wait=1.2)

        if self.shiye_seen:
            # 见过又丢了说明转向出了画面，原地扫视找回；此时盲走只会越走越远
            self.ctx.controller.turn_by_angle_diff(45)
            return self.round_retry(status='原地扫视找狮耶', wait=0.6)

        # 狮耶还不在画面里（刚落点太远），朝门口方向走一小段
        self.ctx.controller.move_w(press=True, press_time=0.8, release=True)
        return self.round_retry(status='未识别当前画面', wait=0.5)

    @node_from(from_name='识别初始画面', status='随便观-入口')
    @node_from(from_name='前往随便观')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理自动托管')
    def handle_auto_manage(self) -> OperationRoundResult:
        if self.config.auto_manage_enabled:
            op = SuibianTempleAutoManage(self.ctx)
            return self.round_by_op_result(op.execute())
        else:
            return self.round_success(status='未开启自动托管')

    @node_from(from_name='处理自动托管', status='未开启自动托管')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理游历')
    def handle_adventure_squad(self) -> OperationRoundResult:
        op = SuibianTempleAdventureSquad(
            self.ctx,
            claim=True,
            dispatch=not self.config.yum_cha_sin,  # 开启饮茶仙就不收获
        )
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理游历')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理饮茶仙')
    def handle_yum_cha_sin_submit(self) -> OperationRoundResult:
        if self.config.yum_cha_sin:
            op = SuibianTempleYumChaSin(self.ctx)
            return self.round_by_op_result(op.execute())
        else:
            return self.round_success(status='未开启')

    @node_from(from_name='处理饮茶仙')  # 只有开启了饮茶仙 才需要在饮茶仙之后再进一次游历
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='饮茶仙后处理游历')
    def handle_adventure_squad_2(self) -> OperationRoundResult:
        op = SuibianTempleAdventureSquad(self.ctx, claim=False, dispatch=True)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理饮茶仙', status='未开启')
    @node_from(from_name='饮茶仙后处理游历')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理制造坊')
    def handle_craft(self) -> OperationRoundResult:
        op = SuibianTempleCraft(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理制造坊')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理售卖铺')
    def handle_sales_stall(self) -> OperationRoundResult:
        op = SuibianTempleSalesStall(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='处理售卖铺')
    @node_from(from_name='处理自动托管')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理好物铺')
    def handle_good_goods(self) -> OperationRoundResult:
        if self.config.good_goods_purchase_enabled:
            op = SuibianTempleGoodGoods(self.ctx)
            return self.round_by_op_result(op.execute())
        else:
            return self.round_success(status='未开启')

    @node_from(from_name='处理好物铺')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理邦巢')
    def handle_boo_box(self) -> OperationRoundResult:
        """检查是否启用邦巢购买功能，决定后续流程"""
        if self.config.boo_box_purchase_enabled:
            op = SuibianTempleBooBox(self.ctx)
            return self.round_by_op_result(op.execute())
        else:
            return self.round_success(status='未开启')

    @node_from(from_name='处理邦巢')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='处理德丰大押')
    def handle_pawnshop(self) -> OperationRoundResult:
        return self.round_success(status='未开启')

    @node_from(from_name='处理德丰大押')
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'
    app = SuibianTempleApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
