from __future__ import annotations

import re
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_clear_loadout import BagelClearLoadout
from zzz_od.application.bagel.bagel_const import RECOMMENDED_VALUE
from zzz_od.application.bagel.bagel_investment import read_investment
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_return import BagelReturn
from zzz_od.application.bagel.bagel_screen import (
    complete_loadout,
    entry_warning,
    parse_capacity_pair,
    read_area,
    read_loadout,
    warehouse_sale_state,
    zero_loadout,
)
from zzz_od.application.bagel.bagel_store_carried import (
    BagelStoreCarried,
    read_carried_backpack,
)
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.transport import Transport

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelEnter(BagelOperation):
    """从已知安全画面进入贝果，核实高危、零携带和零投资。"""

    def __init__(
        self, ctx: ZContext, *, allow_clear_loadout: bool = False,
        allow_world_recovery: bool = False,
    ) -> None:
        """仅应用首次入场显式允许清空；独立工具默认只核对零携带。"""
        super().__init__(ctx, op_name='贝果-零携带入场', timeout_seconds=660 if allow_clear_loadout else 240)
        self.allow_clear_loadout: bool = allow_clear_loadout
        self.allow_world_recovery: bool = allow_world_recovery
        self.world_recovery_attempted: bool = False
        self.clear_attempted: bool = False
        self.loadout_misses: int = 0
        self.zero_checked: bool = False
        self.confirmed_warnings: set[str] = set()
        self.investment_confirmed: bool = False
        self.investment_retries: int = 0
        self.transport_started: bool = False
        self._pending_warning: str | None = None
        self._warning_started_at: float = 0
        self._warning_reclicked: bool = False
        self._resume_check: bool = False

    def handle_init(self) -> None:
        """重复运行时清除上一局的确认状态。"""
        super().handle_init()
        self.world_recovery_attempted = False
        self.zero_checked = False
        self.confirmed_warnings.clear()
        self.investment_confirmed = False
        self.investment_retries = 0
        self.transport_started = False
        self.clear_attempted = False
        self.loadout_misses = 0
        self._pending_warning = None
        self._warning_started_at = 0
        self._warning_reclicked = False
        self._resume_check = False

    def handle_pause(self) -> None:
        """暂停后撤销入场资格，不能信任用户可能已改变的携带与选择。"""
        super().handle_pause()
        self._resume_check = True
        self.zero_checked = False

    def _at_reception(self) -> bool:
        """传送后用普通大世界与达塔名称确认交互位置。"""
        return (
            self.round_by_find_area(self.last_screenshot, '大世界-普通', '快捷手册').is_success
            and self.round_by_find_area(self.last_screenshot, '贝果-研究站', '接待员名称').is_success
        )

    def _ordinary_warehouse(self) -> str | None:
        """普通仓库是其他应用的局部画面，按标题限定识别。"""
        for screen_name, area_name in (
            ('仓库-材料道具', '标题-材料道具'),
            ('仓库-音擎仓库', '标题-音擎仓库'),
            ('仓库-驱动仓库', '标题-驱动仓库'),
        ):
            area = self.ctx.screen_loader.get_area(screen_name, area_name)
            if area is None:
                continue
            title = read_area(self.ctx, self.last_screenshot, screen_name, area_name)
            if area.text in title:
                return screen_name
        return None

    @operation_node(name='处理启动仓库', is_start_node=True)
    def handle_starting_warehouse(self) -> OperationRoundResult:
        """首次启动恢复仓库遗留物，包括上次清空途中停下的备战仓库。"""
        sale_state = warehouse_sale_state(self.ctx, self.last_screenshot)
        if sale_state is not None:
            return self.round_fail(f'检测到仓库出售状态（{sale_state}），停止并保留现场')
        if not self.round_by_find_area(self.last_screenshot, '贝果-仓库', '放入仓库').is_success:
            return self.round_success()
        if not self.allow_clear_loadout:
            return self.round_fail('本次入场不允许清空仓库遗留物资')
        if (read_carried_backpack(self.ctx, self.last_screenshot) is None
                or parse_capacity_pair(read_area(self.ctx, self.last_screenshot, '贝果-仓库', '仓库数量')) is None):
            return self.round_retry('无法核对启动仓库数量', wait=0.5)
        settlement = self.round_by_find_area(self.last_screenshot, '贝果-仓库', '返回研究站').is_success
        stored = BagelStoreCarried(self.ctx).execute()
        self.screenshot()
        if not stored.success:
            return self.round_by_op_result(stored)
        if not settlement:
            return self.round_success('启动仓库返回')
        result = BagelReturn(self.ctx).execute()
        self.screenshot()
        return self.round_by_op_result(result)

    @node_from(from_name='处理启动仓库', status='启动仓库返回')
    @operation_node(name='返回启动仓库上一页', timeout_seconds=20)
    def leave_starting_warehouse(self) -> OperationRoundResult:
        """已转存的非结算仓库回上一页，重新识别后再执行选图核验。"""
        sale_state = warehouse_sale_state(self.ctx, self.last_screenshot)
        if sale_state is not None:
            return self.round_fail(f'检测到仓库出售状态（{sale_state}），停止并保留现场')
        if self.round_by_find_area(self.last_screenshot, '贝果-备战', '预设组合').is_success:
            return self.round_success()
        if all(self.round_by_find_area(self.last_screenshot, '贝果-研究站', name).is_success
               for name in ('标题', '前往空洞')):
            return self.round_success()
        if self.node_clicked:
            return self.round_retry('等待仓库返回备战或研究站入口', wait=0.5)
        if not self.round_by_find_area(self.last_screenshot, '贝果-仓库', '放入仓库').is_success:
            return self.round_retry('未识别可返回的启动仓库', wait=0.5)
        result = self.round_by_click_area('菜单', '返回')
        if result.is_success:
            self.node_clicked = True
            return self.round_wait('已点击启动仓库返回', wait=0.5)
        return result

    @node_from(from_name='处理启动仓库')
    @node_from(from_name='返回启动仓库上一页')
    @operation_node(name='打开贝果主界面', timeout_seconds=120)
    def open_hub(self) -> OperationRoundResult:
        """优先使用现有贝果入口；安全画面才允许传送到研究站。"""
        if self.round_by_find_area(self.last_screenshot, '贝果-备战', '预设组合').is_success:
            return self.round_success('已在备战')
        if self.round_by_find_area(self.last_screenshot, '贝果-选图', '前往备战').is_success:
            return self.round_success()
        if (
            self.round_by_find_area(self.last_screenshot, '贝果-研究站', '标题').is_success
            and self.round_by_find_area(self.last_screenshot, '贝果-研究站', '前往空洞').is_success
        ):
            return self.round_success()
        at_dialog = (
            self.round_by_find_area(self.last_screenshot, '贝果-研究站', '对话人').is_success
            and self.round_by_find_area(self.last_screenshot, '贝果-研究站', '出发对话').is_success
        )
        if self.transport_started:
            if at_dialog:
                result = self.round_by_find_and_click_area(
                    self.last_screenshot, '贝果-研究站', '出发对话', retry_wait=1,
                )
                if result.is_success:
                    return self.round_wait('等待贝果主界面', wait=1)
                return result
            if self._at_reception():
                if self.node_clicked:
                    return self.round_wait('等待达塔对话或贝果主界面', wait=1)
                self.ctx.controller.interact(press=True, press_time=0.2, release=True)
                self.node_clicked = True
                return self.round_wait('等待达塔对话', wait=1)
            if self.round_by_find_area(self.last_screenshot, '大世界-普通', '快捷手册').is_success:
                return self.round_fail('传送落地后未识别达塔，停止并留现场')
            return self.round_wait('等待传送后识别达塔', wait=1)
        current = self.check_and_update_current_screen(self.last_screenshot)
        if current is None:
            current = self._ordinary_warehouse()
        # 达塔前按普通大世界处理；达塔对话也交给通用返回与传送，不从原地继续。
        allowed = at_dialog or current == '大世界-普通' or current in {
            '菜单', '菜单-更多功能', '快捷手册', '仓库-材料道具',
            '仓库-驱动仓库', '仓库-音擎仓库', '地图',
        } or (current is not None and current.startswith('快捷手册-'))
        if not allowed:
            if (
                self.allow_world_recovery and not self.world_recovery_attempted
                and current is None
                and not self._has('按键-普通攻击', '战斗画面')
            ):
                self.world_recovery_attempted = True
                operation = BackToNormalWorld(self.ctx)
                operation.timeout_seconds = min(30, max(0, self.timeout_seconds - self.operation_usage_time))
                result = operation.execute()
                if not result.success:
                    return self.round_by_op_result(result)
                return self.round_wait('已返回大世界，重新检查贝果入场', wait=0.5)
            return self.round_fail(f'当前画面 {current or "未知"} 不支持自动进入贝果，已留现场')
        if current in {'仓库-材料道具', '仓库-音擎仓库', '仓库-驱动仓库'}:
            self.ctx.screen_loader.update_current_screen_name(current)
        result = Transport(self.ctx, '奥蒙德研究站', '迷宫诡域').execute()
        if not result.success:
            return self.round_by_op_result(result)
        self.transport_started = True
        return self.round_wait('等待研究站传送落地', wait=1)

    @node_from(from_name='打开贝果主界面')
    @operation_node(name='打开贝果选图', timeout_seconds=20)
    def open_map(self) -> OperationRoundResult:
        """只接受研究站主界面或选图页，不从未知备战直接进局。"""
        if self.round_by_find_area(self.last_screenshot, '贝果-选图', '前往备战').is_success:
            return self.round_success()
        if not self.round_by_find_area(self.last_screenshot, '贝果-研究站', '标题').is_success:
            return self.round_retry('请从贝果研究站主界面开始', wait=1)
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-研究站', '前往空洞',
            until_find_all=[('贝果-选图', '前往备战')], success_wait=1, retry_wait=1,
        )

    @node_from(from_name='打开贝果主界面', status='已在备战')
    @node_from(from_name='核对零携带', status='重新核对选图')
    @node_from(from_name='打开备战', status='重新核对选图')
    @operation_node(name='备战返回选图', timeout_seconds=15)
    def return_to_map(self) -> OperationRoundResult:
        """直接从备战启动时先返回选图，不能沿用未经核对的地图和难度。"""
        if self.round_by_find_area(self.last_screenshot, '贝果-选图', '前往备战').is_success:
            return self.round_success()
        if not self.round_by_find_area(self.last_screenshot, '贝果-备战', '预设组合').is_success:
            return self.round_retry('等待备战返回选图', wait=0.5)
        return self.round_by_find_and_click_area(
            self.last_screenshot, '菜单', '返回',
            until_find_all=[('贝果-选图', '前往备战')], success_wait=1, retry_wait=0.5,
        )

    @node_from(from_name='备战返回选图')
    @node_from(from_name='打开贝果选图')
    @operation_node(name='选择雅努斯', timeout_seconds=15)
    def choose_map(self) -> OperationRoundResult:
        """每局读取实际选中地图；已正确则免点击，读数不明不操作。"""
        selected = read_area(self.ctx, self.last_screenshot, '贝果-选图', '选中地图')
        if selected == '雅努斯幻境':
            return self.round_success('已核对雅努斯')
        if self.node_clicked or selected != '城郊幻境':
            return self.round_wait('等待核对选中地图', wait=0.25)
        result = self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-选图', '雅努斯',
            pre_delay=0.15, retry_wait=0.25,
        )
        if result.is_success:
            return self.round_wait('等待雅努斯选择生效', wait=0.25)
        return result

    @node_from(from_name='选择雅努斯')
    @operation_node(name='选择高危', timeout_seconds=15)
    def choose_difficulty(self) -> OperationRoundResult:
        """选中后用对应推荐价值与地图名复核，不能只检测页签文字存在。"""
        selected = read_area(self.ctx, self.last_screenshot, '贝果-选图', '选中地图')
        value = read_area(self.ctx, self.last_screenshot, '贝果-选图', '推荐价值')
        if selected == '雅努斯幻境' and value == RECOMMENDED_VALUE:
            self._resume_check = False
            return self.round_success()
        if self.node_clicked or selected != '雅努斯幻境' or not value.isdecimal():
            return self.round_wait('等待核对雅努斯难度', wait=0.25)
        result = self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-选图', '高危', pre_delay=0.15, retry_wait=0.25,
        )
        if result.is_success:
            return self.round_wait('等待高危选择生效', wait=0.25)
        return result

    @node_from(from_name='选择高危')
    @operation_node(name='打开备战', timeout_seconds=20)
    def open_prepare(self) -> OperationRoundResult:
        """地图和难度确认之后才打开备战。"""
        if self.round_by_find_area(self.last_screenshot, '贝果-备战', '预设组合').is_success:
            return self.round_success()
        selected = read_area(self.ctx, self.last_screenshot, '贝果-选图', '选中地图')
        value = read_area(self.ctx, self.last_screenshot, '贝果-选图', '推荐价值')
        if (self._resume_check or selected == '城郊幻境'
                or (selected == '雅努斯幻境' and value.isdecimal() and value != RECOMMENDED_VALUE)):
            return self.round_success('重新核对选图')
        if selected != '雅努斯幻境' or value != RECOMMENDED_VALUE:
            return self.round_wait('等待重新核对地图和难度', wait=0.25)
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-选图', '前往备战',
            until_find_all=[('贝果-备战', '预设组合')], success_wait=1, retry_wait=1,
        )

    @node_from(from_name='打开备战')
    @node_from(from_name='清空启动战备')
    @operation_node(name='核对零携带', timeout_seconds=15)
    def verify_zero_loadout(self) -> OperationRoundResult:
        """未知先重读；首次非零转入清空，其余入场继续拒绝残留。"""
        if self._resume_check:
            return self.round_success('重新核对选图')
        if not self.round_by_find_area(self.last_screenshot, '贝果-备战', '预设组合').is_success:
            return self.round_retry('未识别备战页', wait=1)
        values = read_loadout(self.ctx, self.last_screenshot)
        if not complete_loadout(values):
            self.loadout_misses += 1
            if self.loadout_misses < 5:
                return self.round_wait(f'五项携带识别不完整，重新核对 {values}', wait=0.5)
            return self.round_fail(f'无法完整识别五项携带，停止并保留现场 {values}')
        self.loadout_misses = 0
        if not zero_loadout(values):
            if self.allow_clear_loadout and not self.clear_attempted:
                return self.round_success('需要清空启动战备')
            return self.round_fail('无法确认零携带，请先清空武备、装备、道具、背包和安全箱')
        result = self.round_by_find_and_click_area(self.last_screenshot, '贝果-备战', '前往空洞')
        if result.is_success:
            self.zero_checked = True
            return self.round_success(wait=1)
        return result

    @node_from(from_name='核对零携带', status='需要清空启动战备')
    @operation_node(name='清空启动战备', screenshot_before_round=False)
    def clear_starting_loadout(self) -> OperationRoundResult:
        """清空成功后重新截图核对五项，不能直接设置已核验或跳过投资。"""
        if not self.allow_clear_loadout or self.clear_attempted:
            return self.round_fail('本次入场不允许再次清空战备')
        self.clear_attempted = True
        result = BagelClearLoadout(self.ctx).execute()
        self.screenshot()
        return self.round_by_op_result(result)

    @node_from(from_name='核对零携带')
    @operation_node(name='确认入场并等待加载', timeout_seconds=90, node_max_retry_times=3)
    def confirm_entry(self) -> OperationRoundResult:
        """仅处理核实零携带之后出现的三类确认，未知弹窗保留现场。"""
        if self._resume_check:
            return self.round_fail('入场暂停后需重新核对选图与携带，请从入口重新运行')
        if not self.zero_checked:
            return self.round_fail('尚未核对零携带，禁止确认入场')
        if self.investment_confirmed and self.is_bagel_result():
            # 入场加载期间已经死亡也属于本局，让正式任务的出生检查进入失败结算。
            return self.round_success('已进入雅努斯高危')
        # 开局会自动弹出局内大地图；识别后主动关闭，不空等约 30 秒自动关掉。
        if self.round_by_find_area(self.last_screenshot, '贝果-局内', '大地图图例').is_success:
            result = self.round_by_click_area('贝果-局内', '大地图返回')
            if result.is_success:
                return self.round_wait('关闭开局大地图', wait=1)
            return self.round_retry('已识别开局大地图但未能关闭', wait=1)
        if self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击').is_success:
            if not self.investment_confirmed:
                return self.round_fail('未核对高危零投资，停止并保留现场')
            return self.round_success('已进入雅努斯高危')
        if self.round_by_find_area(self.last_screenshot, '贝果-入场确认', '投资标题').is_success:
            self._pending_warning = None
            if self.investment_confirmed:
                return self.round_retry('零投资入场未生效', wait=1)
            amount = read_investment(self.ctx, self.last_screenshot)
            if amount != '0':
                # WAIT 会重置框架重试次数，单独限次以防 MIN 无效时反复点击。
                if self.investment_retries >= 3:
                    return self.round_fail('无法确认零投资，停止并保留现场')
                self.investment_retries += 1
                valid_amount = re.fullmatch(r'[0-9]+(?:\.[0-9]+)?[KM]|[0-9]+', amount) is not None
                if not valid_amount or float(amount.rstrip('KM')) <= 0:
                    return self.round_retry('投资金额识别不明，重新核对', wait=1)
                result = self.round_by_find_and_click_area(
                    self.last_screenshot, '贝果-入场确认', '投资最小值', retry_wait=1,
                )
                if result.is_success:
                    return self.round_wait('已点击 MIN，等待重新核对投资金额', wait=1)
                return result
            result = self.round_by_find_and_click_area(
                self.last_screenshot, '贝果-入场确认', '零投资前往空洞',
            )
            if result.is_success:
                self.investment_confirmed = True
                return self.round_wait('等待零投资入场', wait=1)
            return result
        text = read_area(self.ctx, self.last_screenshot, '贝果-入场确认', '提示')
        warning = entry_warning(text)
        if warning is not None:
            if warning == self._pending_warning:
                elapsed = self.operation_usage_time - self._warning_started_at
                if elapsed >= 6:
                    return self.round_fail('入场确认持续未消失，停止并保留现场')
                if elapsed < 3 or self._warning_reclicked:
                    return self.round_wait('等待入场确认切换', wait=0.25)
            elif warning in self.confirmed_warnings:
                return self.round_fail('已处理的入场提示再次出现，停止并保留现场')
            result = self.round_by_find_and_click_area(
                self.last_screenshot, '贝果-入场确认', '确认',
                pre_delay=0.15, retry_wait=0.25,
            )
            if result.is_success:
                if warning == self._pending_warning:
                    self._warning_reclicked = True
                else:
                    self._pending_warning = warning
                    self._warning_started_at = self.operation_usage_time
                    self._warning_reclicked = False
                self.confirmed_warnings.add(warning)
                return self.round_wait(warning, wait=0.25)
            return result
        if text and self.round_by_find_area(self.last_screenshot, '贝果-入场确认', '确认').is_success:
            return self.round_fail('未知入场确认，停止并保留现场')
        if self._pending_warning is not None:
            if self.operation_usage_time - self._warning_started_at >= 6:
                return self.round_fail('入场提示切换后未识别下一画面，停止并保留现场')
            return self.round_wait('等待入场提示切换', wait=0.25)
        return self.round_wait('等待贝果加载完成', wait=1)
