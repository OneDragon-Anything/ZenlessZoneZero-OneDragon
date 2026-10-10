from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_const import CONTAINER_TITLE_AREAS
from zzz_od.application.bagel.bagel_operation import BagelOperation

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelExit(BagelOperation):
    """从贝果局内退出到结算仓库；物资核对和入仓交给调用者。"""

    def __init__(self, ctx: ZContext) -> None:
        """创建有界退出流程，不自动出售或返回研究站。"""
        super().__init__(ctx, op_name='贝果-退出到仓库', timeout_seconds=120)

    @operation_node(name='打开贝果暂停菜单', is_start_node=True, timeout_seconds=15)
    def open_menu(self) -> OperationRoundResult:
        """由调用方确认贝果流程；普通攻击按钮出现后打开菜单，再核对专用退出提示。"""
        if all(self._has(area, '贝果-仓库') for area in ('放入仓库', '返回研究站')):
            return self.round_success('已到结算仓库')
        if self._has('提示', '贝果-退出确认'):
            return self.round_success('已到退出确认')
        if self._has('按钮-退出战斗', '战斗-菜单'):
            return self.round_success('已到暂停菜单')
        if self.is_bagel_result():
            return self.round_success('已到贝果结算')
        if any(self._has(area) for area in (*CONTAINER_TITLE_AREAS.values(), '大保险解锁提示')):
            self.ctx.controller.btn_press('esc', press_time=0.1)
            return self.round_wait('关闭局内面板后重新检查退出画面', wait=0.5)
        if self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击').is_success:
            self.ctx.controller.btn_press('esc', press_time=0.1)
            return self.round_success(wait=1)
        return self.round_retry('未识别贝果局内画面', wait=1)

    @node_from(from_name='打开贝果暂停菜单')
    @operation_node(name='点击贝果退出', timeout_seconds=15)
    def click_exit(self) -> OperationRoundResult:
        """从已确认的贝果局内菜单点击退出。"""
        if self.is_bagel_result():
            return self.round_success('已到贝果结算')
        return self.round_by_find_and_click_area(
            self.last_screenshot, '战斗-菜单', '按钮-退出战斗',
            until_find_all=[('贝果-退出确认', '提示')], success_wait=1, retry_wait=1,
        )

    @node_from(from_name='打开贝果暂停菜单', status='已到退出确认')
    @node_from(from_name='点击贝果退出')
    @operation_node(name='确认贝果退出', timeout_seconds=15)
    def confirm_exit(self) -> OperationRoundResult:
        """必须看到仅保留安全箱的专用提示，不能确认普通战斗弹窗。"""
        if self.is_bagel_result():
            return self.round_success('已到贝果结算')
        if not self.round_by_find_area(self.last_screenshot, '贝果-退出确认', '提示').is_success:
            if self.node_clicked:
                return self.round_success('退出确认已消失')
            return self.round_retry('未识别贝果退出提示', wait=1)
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-退出确认', '确认',
            until_not_find_all=[('贝果-退出确认', '提示')], success_wait=1, retry_wait=1,
        )

    @node_from(from_name='确认贝果退出')
    @node_from(from_name='打开贝果暂停菜单', status='已到贝果结算')
    @node_from(from_name='点击贝果退出', status='已到贝果结算')
    @operation_node(name='等待贝果结算', timeout_seconds=60)
    def wait_result(self) -> OperationRoundResult:
        """失败结算要点到「继续」消失，再交给下一节点等仓库。"""
        if self.is_bagel_result():
            return self.round_by_find_and_click_area(
                self.last_screenshot, '贝果-结算', '继续',
                until_not_find_all=[('贝果-结算', '继续')],
                success_wait=1, retry_wait=1,
            )
        if self.node_clicked:
            return self.round_success('结算已继续')
        return self.round_wait('等待贝果结算', wait=1)

    @node_from(from_name='打开贝果暂停菜单', status='已到结算仓库')
    @node_from(from_name='等待贝果结算')
    @operation_node(name='等待结算仓库', timeout_seconds=30)
    def wait_warehouse(self) -> OperationRoundResult:
        """到达后保留现场，由调用者核对安全箱再决定如何入仓。"""
        if all(self.round_by_find_area(self.last_screenshot, '贝果-仓库', area).is_success
               for area in ('放入仓库', '返回研究站')):
            return self.round_success('已到结算仓库')
        return self.round_wait('等待结算仓库', wait=1)
