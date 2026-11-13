"""仅为战斗画面加载节点提供机械硬盘等待额度。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)

if TYPE_CHECKING:
    from one_dragon.base.operation.operation import Operation


def apply_battle_loading_wait(
    op: Operation,
    result: OperationRoundResult,
) -> OperationRoundResult:
    """将机械硬盘加载重试改为限时等待，保留原识别和轮询间隔。

    Args:
        op: 正在等待战斗画面的操作。
        result: 原节点识别结果；原方法已完成这一轮的等待。

    Returns:
        默认模式透传原结果；机械硬盘模式在额度内等待，耗尽后失败。
    """
    if result.result != OperationRoundResultEnum.RETRY:
        return result
    config = op.ctx.game_config
    if not config.hdd_mode or op._current_node_start_time is None:
        return result

    # 框架在新节点、重复执行时重置开始时间，恢复暂停时补偿暂停时间。
    elapsed = time.time() - op._current_node_start_time
    if elapsed >= config.hdd_battle_loading_timeout:
        return op.round_fail(status=result.status, data=result.data)

    # round_retry / round_by_find_area 已经等待过，不再次 sleep。
    return OperationRoundResult(
        OperationRoundResultEnum.WAIT, result.status, result.data
    )
