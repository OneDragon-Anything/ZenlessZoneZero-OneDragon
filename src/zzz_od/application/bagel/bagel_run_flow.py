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
from zzz_od.application.bagel.bagel_container import ContainerRecovery, container_state
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_flow import BagelFlow, BagelStep
from zzz_od.application.bagel.bagel_navigate import BagelNavigate
from zzz_od.application.bagel.bagel_open_box import BagelOpenBox
from zzz_od.application.bagel.bagel_operation import (
    BagelOperation,
    BagelRecoverableFailure,
)
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
    """按列表执行勾选动作；正式任务可连续打开和解锁保险箱。"""

    STATUS_SEARCH_PENDING: str = '搜查状态暂未识别，等待下一帧'
    STATUS_LOCATION_PENDING: str = '小地图暂时无法定位，等待下一帧'

    def __init__(
        self,
        ctx: ZContext,
        flow: BagelFlow,
        step_ids: tuple[str, ...] | None = None,
        on_event: Callable[[dict[str, object]], None] | None = None,
        map_snapshot: BagelFixedMap | None = None,
        continuous_safe_unlock: bool = False,
        on_location_wait: Callable[[], None] | None = None,
    ) -> None:
        """校验勾选清单；正式任务可连续执行相邻的保险箱交互与解锁。"""
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
        self._container_recovery: ContainerRecovery | None = None
        self._container_step_id: str | None = None
        self._approach_step: BagelStep | None = None
        self._reapproach_pending: bool = False
        self.continuous_safe_unlock: bool = continuous_safe_unlock
        self.on_location_wait: Callable[[], None] | None = on_location_wait
        self._step_started_at: float = 0

    def handle_init(self) -> None:
        """每次执行从首个勾选步骤开始，提前校验画面资源。"""
        super().handle_init()
        self.cursor = 0
        self._precondition_waits = 0
        self._location_waits = 0
        self.index = self.indices[0]
        self._container_recovery = None
        self._container_step_id = None
        self._approach_step = None
        self._reapproach_pending = False
        self._step_started_at = 0
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
        self.emit('snapshot', flow=self.flow.to_dict(), step_ids=self.step_ids, map_snapshot_id=self.vision.map.snapshot_id)

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
        if step.action in ('approach', 'interact') and container_state(self, step.target) == 'ready':
            return None
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
                if (self._has(prompt) and self._has('交互F键')) or (
                    self._container_step_id == self._container_owner_id(step)
                    and (self._approach_step is not None or (
                        self._container_recovery is not None and self._container_recovery.interactions > 0
                    ))
                )
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

    def _container_owner_id(self, step: BagelStep) -> str:
        """用靠近步骤区分容器；已校验流程中的交互紧接对应靠近。"""
        if step.action == 'approach':
            return step.id
        return self.flow.steps[self.flow.steps.index(step) - 1].id

    def _recovery_for(self, step: BagelStep) -> ContainerRecovery:
        """同一靠近和交互共用预算；另一容器从独立预算开始。"""
        owner_id = self._container_owner_id(step)
        if self._container_recovery is None or self._container_step_id != owner_id:
            self._container_recovery = ContainerRecovery(lambda: self.operation_usage_time)
            self._container_step_id = owner_id
            self._approach_step = None
        return self._container_recovery

    def _can_continue_safe_unlock(self, step: BagelStep) -> bool:
        """仅连续执行相邻且均选中的保险箱交互与解锁，不补未选步骤。"""
        if (
            not self.continuous_safe_unlock
            or step.action != 'interact' or step.target != 'safe'
            or step != self.flow.steps[self.index]
            or self.cursor + 1 >= len(self.indices)
        ):
            return False
        next_index = self.indices[self.cursor + 1]
        next_step = self.flow.steps[next_index]
        return (
            next_index == self.index + 1
            and next_step.action == 'unlock' and next_step.target == 'safe'
        )

    def _start_unlock_step(self) -> None:
        """解锁界面出现即推进事件和失败归属，子操作继续使用当前截图。"""
        self.emit(
            'done', status=BagelUnlockSafe.STATUS_READY,
            elapsed=time.monotonic() - self._step_started_at,
        )
        self.cursor += 1
        self.index = self.indices[self.cursor]
        self._step_started_at = time.monotonic()
        self.emit('start', status=f'连续执行：{self.flow.steps[self.index].name}')

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
                recovery=self._recovery_for(step) if step.action == 'approach' else None,
                recovering=self._reapproach_pending,
                on_location_wait=self.on_location_wait,
            )
        if step.action == 'interact':
            if step.target == 'box':
                return BagelOpenBox(self.ctx, recovery=self._recovery_for(step))
            continuous = self._can_continue_safe_unlock(step)
            return BagelUnlockSafe(
                self.ctx, phase='full' if continuous else 'interact',
                recovery=self._recovery_for(step),
                on_unlock_ready=self._start_unlock_step if continuous else None,
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
        if self._container_recovery is not None and step.action in ('approach', 'interact'):
            reason = self._recovery_for(step).error()
            if reason and container_state(self, step.target) != 'ready':
                self.emit('failed', status=reason, elapsed=0)
                return self.round_fail(self.STATUS_CONTAINER_FAILED, data=reason)
        active_step = step
        if self._reapproach_pending:
            assert self._approach_step is not None
            active_step = self._approach_step
        reason = self.precondition(active_step)
        if reason == self.STATUS_LOCATION_PENDING:
            self._location_waits += 1
            if self._location_waits <= 5:
                if self.on_location_wait is not None:
                    self.on_location_wait()
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
            if step.action in ('approach', 'interact') and self._container_recovery is not None:
                return self.round_fail(self.STATUS_CONTAINER_FAILED, data=reason)
            return self.round_recoverable_fail(reason)
        self._precondition_waits = 0
        self._location_waits = 0
        started = time.monotonic()
        self._step_started_at = started
        recovering = self._reapproach_pending
        operation = self.build_operation(active_step)
        result = operation.execute() if operation is not None else None
        # 连续操作确认界面后已进入解锁步骤，成功事件和失败处理按新阶段执行。
        step = self.flow.steps[self.index]
        started = self._step_started_at
        if operation is not None and operation.last_screenshot is not None:
            self.last_screenshot = operation.last_screenshot
            self.last_screenshot_time = operation.last_screenshot_time
        success = result is None or result.success
        status = result.status if result is not None else '出生位置已确认'
        recoverable = result is not None and (
            isinstance(result.data, BagelRecoverableFailure) or status == self.STATUS_TIMEOUT
        )
        # 框架错误必须原样返回，不能根据新画面改写成受击或容器失败。
        if not success and (
            status in ('人工结束', '初始化失败', '异常')
            or (status is not None and status.startswith('区域未配置'))
        ):
            self.emit('failed', status=status, elapsed=time.monotonic() - started)
            return self.round_by_op_result(result)
        if not success and step.action == 'exit':
            return self.round_fail(self.STATUS_CLEANUP_FAILED, data=f'{status}：{result.data}')
        if not success and status == ContainerRecovery.STATUS_REAPPROACH:
            reason = (
                self._container_recovery.request_approach()
                if self._approach_step is not None and self._container_recovery is not None
                else '未选中并完成本容器靠近步骤，禁止隐式移动'
            )
            if reason is None:
                self._reapproach_pending = True
                self.emit('waiting', status=ContainerRecovery.STATUS_REAPPROACH)
                return self.round_wait(ContainerRecovery.STATUS_REAPPROACH, wait=0.1)
            status = reason
            recoverable = True
        if recovering:
            self._reapproach_pending = False
            if success and status in (BagelNavigate.STATUS_ARRIVED_BOX, BagelNavigate.STATUS_ARRIVED_SAFE):
                return self.round_wait('重新靠近完成，继续当前交互步骤', wait=0.1)
        if (
            not success
            and status != self.STATUS_DEFEATED
            and recoverable
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
            recoverable = recoverable or result.success
        self.emit(
            'done' if success else 'failed',
            status=status,
            elapsed=time.monotonic() - started,
        )
        if not success:
            if step.action in ('approach', 'interact') and status != self.STATUS_DEFEATED and recoverable:
                return self.round_fail(self.STATUS_CONTAINER_FAILED, data=status)
            if status == self.STATUS_INTERRUPTED:
                return self.round_fail(status, data=result.status if result is not None else None)
            if recoverable:
                return self.round_recoverable_fail(status or '局内步骤失败')
            return self.round_by_op_result(result) if result is not None else self.round_fail(status)
        if step.action == 'approach':
            self._approach_step = step
        elif step.action != 'interact':
            self._container_recovery = None
            self._container_step_id = None
            self._approach_step = None
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
