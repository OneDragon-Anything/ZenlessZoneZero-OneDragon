"""从空洞类玩法局内退出来，回到大世界。

用于登录后直接落在玩局内的情况：角色卡在玩法里，一条龙后面的应用都无法开始。
本操作负责把角色带回大世界，链路是：

1. 打开暂停菜单；
2. 点退出，并按玩法的专用提示确认（逃离类玩法是「仅保留安全箱内物资」）；
3. 结算画面点继续；
4. 结算仓库点返回研究站；
5. 交给通用返回大世界兜底。

只处理「离开这局」，不处理物资、不出售、不重开：这些属于各玩法自己的业务。
退出会丢弃安全箱外的物资，这是游戏对主动退出的既定规则，与玩法自己的退出行为一致。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils.log_utils import log
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.zzz_operation import ZOperation

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext

SCREEN_NAME: str = '空洞-局内HUD'


class ExitHollowInside(ZOperation):
    """把卡在空洞类玩法局内的角色带回大世界。"""

    RE_CLICK_INTERVAL: float = 3.0
    """点过继续后至少等这么久，画面还没变化才补点。"""
    MAX_RE_CLICKS: int = 2
    """最多补点几次；仍无效就停止，避免无限循环。"""

    def __init__(self, ctx: ZContext) -> None:
        """整条链有一定时长，超时按失败上报，由调用方决定后续。"""
        super().__init__(
            ctx,
            op_name='退出空洞局内',
            timeout_seconds=180,
            need_check_game_win=False,
        )
        self.menu_presses: int = 0
        """已经按了几次 Esc 打开暂停菜单。"""
        self.confirm_clicked: bool = False
        """是否已经点过退出确认，避免重复点击。"""
        self.confirm_clicked_at: float = 0.0
        """上次点击退出确认时的操作已用时间，用来算补点间隔。"""
        self.confirm_retry: int = 0
        """退出确认已经补点了几次。"""
        self.continue_clicked: bool = False
        """是否已经点过结算的继续，避免重复点击。"""
        self.continue_clicked_at: float = 0.0
        """上次点击继续时的操作已用时间，用来算补点间隔。"""
        self.continue_retry: int = 0
        """继续按钮已经补点了几次。"""

    def handle_init(self) -> None:
        """重复执行时清空本轮的按键计数。"""
        super().handle_init()
        self.menu_presses = 0
        self.confirm_clicked = False
        self.confirm_clicked_at = 0.0
        self.confirm_retry = 0
        self.continue_clicked = False
        self.continue_clicked_at = 0.0
        self.continue_retry = 0

    def _has(self, area_name: str) -> bool:
        """核对本画面里的区域是否出现。"""
        return self.round_by_find_area(self.last_screenshot, SCREEN_NAME, area_name).is_success

    @operation_node(name='打开暂停菜单', is_start_node=True, timeout_seconds=30)
    def open_menu(self) -> OperationRoundResult:
        """按 Esc 打开暂停菜单；已经在退出确认或结算时直接放行。"""
        if self._has('退出确认-提示'):
            return self.round_success('已到退出确认')
        if self._has('结算-继续'):
            return self.round_success('已到结算')
        if self._has('仓库-返回研究站'):
            return self.round_success('已到结算仓库')
        if self._has('菜单-退出战斗'):
            return self.round_success('已到暂停菜单')
        if self.menu_presses >= 3:
            return self.round_fail(f'按了 {self.menu_presses} 次 Esc 仍未打开暂停菜单')
        self.menu_presses += 1
        self.ctx.controller.btn_press('esc', press_time=0.1)
        return self.round_wait(f'按 Esc 打开暂停菜单（第 {self.menu_presses} 次）', wait=1.2)

    @node_from(from_name='打开暂停菜单', status='已到暂停菜单')
    @operation_node(name='点击退出', timeout_seconds=20)
    def click_exit(self) -> OperationRoundResult:
        """点菜单里的退出战斗，等到退出确认出现。"""
        return self.round_by_find_and_click_area(
            self.last_screenshot, SCREEN_NAME, '菜单-退出战斗',
            until_find_all=[(SCREEN_NAME, '退出确认-提示')],
            success_wait=0.5, retry_wait=0.5,
        )

    @node_from(from_name='打开暂停菜单', status='已到退出确认')
    @node_from(from_name='点击退出')
    @operation_node(name='确认退出', timeout_seconds=20)
    def confirm_exit(self) -> OperationRoundResult:
        """只确认玩法自己的专用退出提示，不点普通战斗弹窗。"""
        if self._has('结算-继续'):
            return self.round_success('已到结算')
        if not self._has('退出确认-提示'):
            return self.round_success('退出确认已消失')
        # 点一次就等提示消失，不重复点；隔一段时间还在才补点。
        # 不能点完立刻判失败：关闭提示有动画，下一轮仍可能看得到。
        if self.confirm_clicked:
            if self.operation_usage_time - self.confirm_clicked_at < self.RE_CLICK_INTERVAL:
                return self.round_wait('等待退出确认消失', wait=0.5)
            if self.confirm_retry >= self.MAX_RE_CLICKS:
                return self.round_fail('退出确认点击后仍未关闭，停止重复尝试')
            self.confirm_retry += 1
            log.info('退出确认未关闭，补点第 %s 次', self.confirm_retry)
        result = self.round_by_find_and_click_area(
            self.last_screenshot, SCREEN_NAME, '退出确认-确认',
            pre_delay=0.1, success_wait=0.5, retry_wait=0.5,
        )
        if result.is_success:
            self.confirm_clicked = True
            self.confirm_clicked_at = self.operation_usage_time
            return self.round_wait('已点击确认，等待提示消失', wait=0.5)
        return result

    @node_from(from_name='打开暂停菜单', status='已到结算')
    @node_from(from_name='确认退出', status='已到结算')
    @node_from(from_name='确认退出', status='退出确认已消失')
    @node_from(from_name='确认退出', status='退出确认已关闭')
    @node_from(from_name='确认退出')
    @operation_node(name='等待结算', timeout_seconds=60)
    def wait_result(self) -> OperationRoundResult:
        """结算画面点一次继续，之后只等画面变化，不重复点。"""
        if self._has('菜单-退出战斗') or self._has('退出确认-提示'):
            return self.round_success('退出未生效，重新打开菜单')
        if self._has('仓库-返回研究站'):
            return self.round_success('已到结算仓库')
        if not self._has('结算-继续'):
            return self.round_wait('等待结算画面', wait=1)
        # 点一次就等画面变化；隔一段时间还没变化才补点，避免连点导致一直卡住。
        # 这个按钮点中就有反应，重复点是无效操作。
        if self.continue_clicked:
            if self.operation_usage_time - self.continue_clicked_at < self.RE_CLICK_INTERVAL:
                return self.round_wait('等待结算继续生效', wait=0.5)
            if self.continue_retry >= self.MAX_RE_CLICKS:
                return self.round_fail('结算继续点击后画面仍未变化，停止重复尝试')
            self.continue_retry += 1
            log.info('结算继续未生效，补点第 %s 次', self.continue_retry)
        clicked = self.round_by_find_and_click_area(
            self.last_screenshot, SCREEN_NAME, '结算-继续',
            pre_delay=0.1, success_wait=0.5, retry_wait=0.5,
        )
        if clicked.is_success:
            self.continue_clicked = True
            self.continue_clicked_at = self.operation_usage_time
            return self.round_wait('已点击继续，等待画面变化', wait=0.5)
        return clicked

    @node_from(from_name='打开暂停菜单', status='已到结算仓库')
    @node_from(from_name='等待结算', status='已到结算仓库')
    @node_from(from_name='等待结算', status='结算已继续')
    @operation_node(name='返回研究站', timeout_seconds=30)
    def return_station(self) -> OperationRoundResult:
        """结算仓库点返回研究站，等仓库画面消失。"""
        return self.round_by_find_and_click_area(
            self.last_screenshot, SCREEN_NAME, '仓库-返回研究站',
            until_not_find_all=[(SCREEN_NAME, '仓库-返回研究站')],
            success_wait=1, retry_wait=1,
        )

    @node_from(from_name='等待结算', status='退出未生效，重新打开菜单')
    @node_from(from_name='返回研究站')
    @operation_node(name='回到大世界', timeout_seconds=90, screenshot_before_round=False)
    def back_to_world(self) -> OperationRoundResult:
        """交给通用返回兜底：研究站或大世界落点都能收敛到大世界。"""
        op = BackToNormalWorld(self.ctx, ensure_normal_world=True, timeout_seconds=60)
        result = op.execute()
        if not result.success:
            log.error('退出空洞局内后返回大世界失败：%s', result.status)
            return self.round_fail(f'返回大世界失败：{result.status}', data=result.data)
        return self.round_success('已回到大世界')
