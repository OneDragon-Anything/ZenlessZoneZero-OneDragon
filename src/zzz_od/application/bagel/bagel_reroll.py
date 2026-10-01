from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import cv2

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils import cv2_utils, debug_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_enter import BagelEnter
from zzz_od.application.bagel.bagel_exit import BagelExit
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_return import BagelReturn
from zzz_od.application.bagel.bagel_route_vision import BagelSpawnMatcher

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelReroll(BagelOperation):
    """重复零携带入场，支持出生点原地停止，其余退出重开。"""

    STATUS_FOUND: str = '已抽到支持出生点，原地停止'
    STATUS_SKIP: str = '非支持出生点，退出重开'

    def __init__(
        self, ctx: ZContext, start: str = 'entry', max_attempts: int = 0,
    ) -> None:
        """选择已知起点；零局数上限表示持续抽取，子操作各自限时。"""
        if start not in ('entry', 'warehouse', 'spawn'):
            raise ValueError('起点必须是 entry、warehouse 或 spawn')
        if type(max_attempts) is not int or max_attempts < 0:
            raise ValueError('尝试局数上限必须为非负整数')
        super().__init__(ctx, op_name='贝果-抽到支持点即停', node_max_retry_times=0)
        self.start: str = start
        self.max_attempts: int = max_attempts
        self.attempts: int = 0
        self.matcher: BagelSpawnMatcher = BagelSpawnMatcher()

    def handle_init(self) -> None:
        """重复执行时清空本次尝试计数。"""
        super().handle_init()
        self.attempts = 0

    @operation_node(name='检查抽取起点', is_start_node=True, screenshot_before_round=False)
    def prepare(self) -> OperationRoundResult:
        """按指定起点继续；开新局时由入场操作确认当前零携带。"""
        return self.round_success(self.start)

    @node_from(from_name='检查抽取起点', status='entry')
    @node_from(from_name='返回抽取入口')
    @operation_node(name='零携带重开', screenshot_before_round=False)
    def enter(self) -> OperationRoundResult:
        """达到上限时留在入口；入场失败直接结束，不循环重试。"""
        if self.max_attempts and self.attempts >= self.max_attempts:
            return self.round_fail(f'已检查 {self.attempts} 次出生点，达到尝试上限')
        log.info('贝果抽点：准备第 %s 次入场', self.attempts + 1)
        return self.round_by_op_result(BagelEnter(self.ctx).execute(), wait=1)

    @node_from(from_name='检查抽取起点', status='spawn')
    @node_from(from_name='零携带重开')
    @operation_node(name='识别支持点后停止')
    def check_spawn(self) -> OperationRoundResult:
        """只读取局内小地图；命中支持点后没有退出或移动的后续节点。"""
        if not self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击').is_success:
            return self.round_fail('未识别贝果局内画面，停止抽点')
        area = self.ctx.screen_loader.get_area('贝果-局内', '定位小地图')
        if area is None:
            return self.round_fail('缺少贝果定位小地图区域')
        crop = cv2_utils.crop_image_only(self.last_screenshot, area.pc_rect)
        crop = cv2.cvtColor(crop, cv2.COLOR_RGB2BGR)
        self.attempts += 1
        map_id = self.matcher.match(crop)
        if map_id is not None:
            name = self.save_screenshot(prefix=f'bagel_spawn_{map_id}')
            path = debug_utils.get_debug_image_path(name)
            log.info('第 %s 次抽到 %s，已停止；截图：%s', self.attempts, map_id, path)
            return self.round_success(
                self.STATUS_FOUND,
                data={'attempts': self.attempts, 'screenshot': path, 'map_id': map_id},
            )
        log.info('第 %s 次未识别为支持出生点，退出重开', self.attempts)
        return self.round_success(self.STATUS_SKIP)

    @node_from(from_name='识别支持点后停止', status=STATUS_SKIP)
    @operation_node(name='退出非支持局', screenshot_before_round=False)
    def exit_unsupported(self) -> OperationRoundResult:
        """只对未命中的出生点退出；失败时保留现场。"""
        return self.round_by_op_result(BagelExit(self.ctx).execute())

    @node_from(from_name='检查抽取起点', status='warehouse')
    @node_from(from_name='退出非支持局')
    @operation_node(name='返回抽取入口', screenshot_before_round=False)
    def return_to_entry(self) -> OperationRoundResult:
        """空局返回研究站并打开入口，下一轮再次核对零携带。"""
        return self.round_by_op_result(BagelReturn(self.ctx).execute())


def main() -> int:
    """独立运行抽点任务；沿用框架停止键并在结束时释放控制器。"""
    parser = argparse.ArgumentParser(description='贝果高危雅努斯：非 A 重开，抽到 A 原地停止')
    parser.add_argument('--start', choices=('entry', 'warehouse', 'spawn'), default='entry',
                        help='入口、已处理物资的结算仓库，或未移动且无待保留物资的出生点')
    parser.add_argument('--max-attempts', type=int, default=0, help='最多检查几次出生点；0 表示不限')
    args = parser.parse_args()
    if args.max_attempts < 0:
        parser.error('--max-attempts 不能为负数')

    from zzz_od.context.zzz_context import ZContext

    ctx = ZContext()
    try:
        ctx.init()
        if not ctx.ready_for_application or not ctx.run_context.start_running():
            return 1
        log.info('抽到 A 后原地停止；手动停止键：%s，也可在终端按 Ctrl+C', ctx.key_stop_running)
        result = BagelReroll(ctx, start=args.start, max_attempts=args.max_attempts).execute()
        log.info('抽点任务结束：%s', result.status)
        return 0 if result.success else 1
    except KeyboardInterrupt:
        log.info('用户在终端停止抽点')
        return 130
    finally:
        ctx.run_context.stop_running()
        ctx.after_app_shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
