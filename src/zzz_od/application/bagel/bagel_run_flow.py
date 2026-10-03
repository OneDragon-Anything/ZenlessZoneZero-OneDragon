"""正式任务与开发试跑共用的贝果局内步骤执行器。"""

from __future__ import annotations

import ctypes
import time
from typing import TYPE_CHECKING

import cv2
from pynput import mouse

from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils import cv2_utils
from zzz_od.application.bagel.bagel_close_search import BagelCloseSearch
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_flow import BagelFlow, BagelStep
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_open_box import BagelOpenBox
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_route_vision import BagelRouteVision
from zzz_od.application.bagel.bagel_store import BagelStoreSafe
from zzz_od.application.bagel.bagel_unlock_safe import BagelUnlockSafe

if TYPE_CHECKING:
    from collections.abc import Callable

    from one_dragon.base.operation.operation_base import OperationResult
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.application.bagel.bagel_fixed_map import BagelFixedMap
    from zzz_od.context.zzz_context import ZContext


def release_flow_inputs(ctx: ZContext) -> None:
    """收回本流程使用的前进、交互与拖拽输入。"""
    controller = ctx.controller
    controller.is_moving = False
    controller.btn_controller.reset()
    controller.keyboard_controller.reset()
    # 定时按键和拖拽不在持续按下集合里，需要额外释放。
    keys = controller.game_config.get_action_keys('keyboard')
    for action in ('move_w', 'interact'):
        key = keys[action]
        if pc_button_utils.is_mouse_button(key):
            controller.keyboard_controller.mouse.release(pc_button_utils.get_mouse_button(key))
        else:
            controller.keyboard_controller.keyboard.release(pc_button_utils.get_keyboard_button(key))
    controller.keyboard_controller.mouse.release(mouse.Button.left)
    if controller.background_mode:
        hwnd = controller.game_win.get_hwnd()
        if hwnd is not None:
            ctypes.windll.user32.PostMessageW(hwnd, 0x0202, 0, 0)  # WM_LBUTTONUP


class BagelRunFlow(BagelOperation):
    """按列表顺序执行勾选的独立动作；未选步骤不隐式补做。"""

    STATUS_SEARCH_PENDING: str = '搜查状态暂未识别，等待下一帧'
    STATUS_LOCATION_PENDING: str = '小地图暂时无法定位，等待下一帧'

    def __init__(
        self,
        ctx: ZContext,
        flow: BagelFlow,
        step_ids: tuple[str, ...] | None = None,
        on_event: Callable[[dict[str, object]], None] | None = None,
        map_snapshot: BagelFixedMap | None = None,
    ) -> None:
        """校验完整流程和勾选清单；正式任务未传清单时执行全部。"""
        super().__init__(ctx, op_name=f'贝果流程-{flow.name}', node_max_retry_times=0)
        self.flow: BagelFlow = BagelFlow.from_dict(flow.to_dict())
        known = {step.id for step in self.flow.steps}
        chosen = known if step_ids is None else set(step_ids)
        if (
            not chosen
            or not chosen <= known
            or (step_ids is not None and len(chosen) != len(step_ids))
        ):
            raise ValueError('请勾选有效且不重复的步骤')
        self.indices: tuple[int, ...] = tuple(
            i for i, step in enumerate(self.flow.steps) if step.id in chosen
        )
        self.step_ids: tuple[str, ...] = tuple(
            self.flow.steps[i].id for i in self.indices
        )
        self.on_event: Callable[[dict[str, object]], None] | None = on_event
        self.cursor: int = 0
        self.index: int = self.indices[0]
        self._precondition_waits: int = 0
        self._location_waits: int = 0
        self.vision: BagelRouteVision | None = None
        self._map_snapshot: BagelFixedMap | None = map_snapshot

    def handle_init(self) -> None:
        """每次执行从首个勾选步骤开始，提前校验画面资源。"""
        super().handle_init()
        self.cursor = 0
        self._precondition_waits = 0
        self._location_waits = 0
        self.index = self.indices[0]
        if self.ctx.screen_loader.get_area('战斗画面', '按键-普通攻击') is None:
            raise ValueError('缺少画面区域：战斗画面/按键-普通攻击')
        for area in (
            '定位小地图',
            '武备箱交互',
            '电子保险箱交互',
            '交互F键',
            '搜查容器标题',
            '电子保险箱标题',
            '搜查安全箱',
            '搜查进行中',
            '搜查完成',
            '大保险解锁提示',
            '搜查返回',
        ):
            if self.ctx.screen_loader.get_area('贝果-局内', area) is None:
                raise ValueError(f'缺少画面区域：{area}')
        self.vision = BagelRouteVision(self.flow.map_id, map_snapshot=self._map_snapshot)
        self.emit('snapshot', flow=self.flow.to_dict(), step_ids=self.step_ids, map_version=self.vision.map.version)

    def emit(self, kind: str, **details: object) -> None:
        """同一事件用于界面与持久化记录。"""
        if self.on_event is not None:
            self.on_event(
                {
                    'kind': kind,
                    'time': time.time(),
                    'step_id': self.flow.steps[self.index].id,
                    'index': self.index,
                    **details,
                }
            )

    def _has(self, area: str, screen_name: str = '贝果-局内') -> bool:
        """用当前帧核对既有画面区域。"""
        return self.round_by_find_area(
            self.last_screenshot, screen_name, area
        ).is_success

    def precondition(self, step: BagelStep) -> str | None:
        """返回不能执行的原因；不通过时不发送游戏输入。"""
        if self.is_bagel_result():
            return self.STATUS_DEFEATED
        if self.container_interrupted(step):
            return self.STATUS_INTERRUPTED
        if step.action == 'unlock':
            return (
                None
                if self._has('大保险解锁提示') or (
                    self._has('电子保险箱标题')
                    and self._has('搜查安全箱')
                    and (self._has('搜查进行中') or self._has('搜查完成'))
                )
                else '请先打开电子保险箱光圈解锁界面'
            )
        if step.action in ('store', 'close'):
            title = '搜查容器标题' if step.target == 'box' else '电子保险箱标题'
            if not self._has(title):
                return '未识别对应容器搜查面板'
            return (
                None
                if (
                    self._has('搜查安全箱')
                    and (self._has('搜查进行中') or self._has('搜查完成'))
                )
                else self.STATUS_SEARCH_PENDING
            )
        if self._has('搜查容器标题') or self._has('电子保险箱标题'):
            return '请先执行关闭搜查面板步骤'
        if self._has('大保险解锁提示'):
            return '请先完成电子保险箱解锁并关闭搜查面板'
        if not self._has('按键-普通攻击', '战斗画面'):
            return '未识别贝果局内画面'
        if step.action == 'interact':
            prompt = '武备箱交互' if step.target == 'box' else '电子保险箱交互'
            return (
                None
                if self._has(prompt) and self._has('交互F键')
                else f'未发现{prompt}及F图标'
            )
        if step.action in ('spawn', 'move', 'approach'):
            area = self.ctx.screen_loader.get_area('贝果-局内', '定位小地图')
            crop = cv2.cvtColor(
                cv2_utils.crop_image_only(self.last_screenshot, area.pc_rect),
                cv2.COLOR_RGB2BGR,
            )
            position = self.vision.locate(crop)
            self.emit(
                'observation',
                position=position,
                angle=self.vision.player_angle(crop),
                target=0,
            )
            if position is None:
                location = self.vision.last_location
                if location is not None and location.reason == 'insufficient_geometry':
                    return self.STATUS_LOCATION_PENDING
                return '当前小地图无法定位'
            if (
                step.action == 'spawn'
                and (
                    (position[0] - self.vision.spawn[0]) ** 2
                    + (position[1] - self.vision.spawn[1]) ** 2
                )
                > 25
            ):
                return '当前不在所选出生点'
        return None

    def container_interrupted(self, step: BagelStep) -> bool:
        """只在预期容器操作中确认面板已消失且回到局内；未知画面不自动退出。"""
        return (
            step.action in ('store', 'close', 'unlock')
            and not any(self._has(area) for area in (
                '搜查容器标题', '电子保险箱标题', '大保险解锁提示',
            ))
            and self._has('按键-普通攻击', '战斗画面')
        )

    def build_operation(self, step: BagelStep) -> BagelOperation | None:
        """业务动作只有一个执行来源，工具不复制游戏交互。"""
        if step.action in ('move', 'approach'):
            if self.vision is None:
                self.vision = BagelRouteVision(self.flow.map_id, map_snapshot=self._map_snapshot)
            return BagelNavigate(
                self.ctx,
                destination='move' if step.action == 'move' else step.target,
                map_id=self.flow.map_id,
                route_data=step.route(self.flow.map_id),
                map_snapshot=self.vision.map,
                navigation=step.navigation,
                require_spawn=False,
                check_target_position=True,
                coordinate_only=step.action == 'move',
                final_approach=step.action == 'approach',
                on_observation=lambda data: self.emit('observation', **data),
            )
        if step.action == 'interact':
            return (
                BagelOpenBox(self.ctx)
                if step.target == 'box'
                else BagelUnlockSafe(self.ctx, phase='interact')
            )
        if step.action == 'unlock':
            return BagelUnlockSafe(self.ctx, phase='unlock')
        if step.action == 'store':
            return BagelStoreSafe(self.ctx)
        if step.action == 'close':
            return BagelCloseSearch(self.ctx)
        return BagelExit(self.ctx) if step.action == 'exit' else None

    @operation_node(name='执行局内步骤', is_start_node=True, node_max_retry_times=0)
    def run_step(self) -> OperationRoundResult:
        """只推进到下一项勾选动作，执行前检查当下画面。"""
        step = self.flow.steps[self.index]
        self.emit('start', status=f'核对前置画面：{step.name}')
        reason = self.precondition(step)
        if reason == self.STATUS_LOCATION_PENDING:
            self._location_waits += 1
            if self._location_waits <= 5:
                self.emit('waiting', status=reason)
                return self.round_wait(reason, wait=0.3)
            reason = '小地图持续无法定位，停止并保留现场'
        if reason == self.STATUS_SEARCH_PENDING:
            self._precondition_waits += 1
            if self._precondition_waits <= 5:
                self.emit('waiting', status=reason)
                return self.round_wait(reason, wait=0.3)
            reason = '搜查状态持续未识别，停止并保留现场'
        if reason:
            self.emit('failed', status=reason, elapsed=0)
            return self.round_fail(reason)
        self._precondition_waits = 0
        self._location_waits = 0
        started = time.monotonic()
        operation = self.build_operation(step)
        result = operation.execute() if operation is not None else None
        success = result is None or result.success
        status = result.status if result is not None else '出生位置已确认'
        if (
            not success
            and status != self.STATUS_DEFEATED
            and step.action in ('store', 'close', 'unlock')
        ):
            self.screenshot()
            if self.container_interrupted(step):
                status = self.STATUS_INTERRUPTED
        if (
            step.action in ('move', 'approach')
            and result is not None
            and result.status
            not in (
                BagelNavigate.STATUS_WAYPOINT
                if step.action == 'move'
                else (
                    BagelNavigate.STATUS_ARRIVED_BOX
                    if step.target == 'box'
                    else BagelNavigate.STATUS_ARRIVED_SAFE
                ),
            )
        ):
            success = False
        self.emit(
            'done' if success else 'failed',
            status=status,
            elapsed=time.monotonic() - started,
        )
        if not success:
            return self.round_fail(status)
        if self.cursor == len(self.indices) - 1:
            return self.round_success('勾选步骤执行完成')
        self.cursor += 1
        self.index = self.indices[self.cursor]
        return self.round_wait('执行下一步骤', wait=0.1)

    def handle_pause(self) -> None:
        """框架暂停时释放输入。"""
        release_flow_inputs(self.ctx)
        super().handle_pause()

    def after_operation_done(self, result: OperationResult) -> None:
        """最后释放输入，失败现场由已有公共操作保存。"""
        try:
            release_flow_inputs(self.ctx)
            self.emit('finished', success=result.success, status=result.status)
        finally:
            super().after_operation_done(result)
