"""贝果收益统计：每局一行日志，任务结束输出总表并生成推送摘要，不参与流程判断。

一局指从「零携带入场」到返回入口。收益取局内 HUD 背包图标旁的调查收益，
游戏只显示到 0.1K 一级，例如「198.5K」记为 198500。失败局的收益也计入合计。
出售所得齿轮硬币只写日志：出售会连同已有库存一起卖，不能摊到单局。

物品只统计红色（Z 品质），按类型汇总件数，见 ``BagelSafeLedger``。
用时按扣除暂停后的时钟计算。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_item_vision import TYPE_RANK

OUTCOME_SUCCESS: str = '成功入仓'
OUTCOME_EMPTY: str = '空箱'
OUTCOME_FAILED: str = '失败局'
OUTCOME_UNSUPPORTED: str = '非支持出生点'
OUTCOME_UNFINISHED: str = '未完成'

QUALITY_RED: str = 'Z'
"""红色品质；只有这一品质计入物品统计。"""

_VALUE_PATTERN: re.Pattern[str] = re.compile(r'(\d+(?:\.\d+)?)([KM]?)')
_VALUE_UNITS: dict[str, int] = {'': 1, 'K': 1_000, 'M': 1_000_000}


def parse_value(text: str) -> int | None:
    """把「198.5K」「3476500」一类读数换成整数；读不出数字时返回 None。"""
    compact = text.replace(',', '').replace(' ', '').upper()
    match = _VALUE_PATTERN.search(compact)
    if match is None:
        return None
    number, unit = match.groups()
    return round(float(number) * _VALUE_UNITS[unit])


def parse_quantity(text: str) -> int:
    """安全箱格子下方的数量；装备显示「Lv.50」之类等级，按 1 件计。"""
    compact = text.replace(' ', '')
    return int(compact) if compact.isdigit() else 1


def format_value(value: int | None) -> str:
    """按游戏习惯缩写成 K / M，未知时显示「未读到」。"""
    if value is None:
        return '未读到'
    if value >= 1_000_000:
        return f'{value / 1_000_000:.2f}M'
    if value >= 1_000:
        return f'{value / 1_000:.1f}K'
    return str(value)


def format_duration(seconds: float) -> str:
    """把秒数写成「1h12m」「5m08s」「42s」。"""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f'{hours}h{minutes:02d}m'
    if minutes:
        return f'{minutes}m{secs:02d}s'
    return f'{secs}s'


@dataclass
class BagelItemRecord:
    """本局带出的一格物品。"""

    item_type: str
    quality: str
    quantity: int | None
    """格子下方读到的数量；只读红色物品，其余品质和装箱中途结束时为 None。"""


class BagelSafeLedger:
    """一局内安全箱各格的物品账本，只用于统计日志。

    拖拽发出前登记拖入的物品；确认入箱时把该格换成这件物品，数量记为未知；
    装箱正常结束后，装箱操作再按画面读数整体覆盖 ``slot_items``。
    这样装箱中途结束时，账本仍是已确认入箱的物品。
    """

    def __init__(self) -> None:
        self.slot_items: dict[int, tuple[str, str, int | None]] = {}
        """安全箱格号 -> （类型, 品质, 数量）。"""
        self._pending: list[tuple[int, tuple[str, str] | None]] = []
        """已发出、尚未确认的拖拽：（安全箱格号, 拖入的物品）。"""

    def start_transfer(self, slot: int, item: tuple[str, str] | None) -> None:
        """拖拽发出前登记。

        Args:
            slot: 安全箱目标格号，从 0 开始。
            item: 拖入的物品（类型, 品质）；不明为 None。
        """
        self._pending.append((slot, item))

    def confirm_transfer(self) -> None:
        """最近一次拖拽已确认入箱，该格换成拖入的物品。"""
        if not self._pending:
            return
        slot, item = self._pending.pop()
        if item is not None:
            self.slot_items[slot] = (*item, None)
        else:
            self.slot_items.pop(slot, None)

    def cancel_transfer(self) -> None:
        """最近一次拖拽没进安全箱，撤销登记。"""
        if self._pending:
            self._pending.pop()

    def report(self) -> list[BagelItemRecord]:
        """按格号列出本局带出的物品。"""
        return [
            BagelItemRecord(item_type, quality, quantity)
            for _, (item_type, quality, quantity) in sorted(self.slot_items.items())
        ]


def red_counts(items: list[BagelItemRecord]) -> dict[str, int]:
    """按类型汇总红色物品件数；数量没读到时按 1 件计。"""
    counts: dict[str, int] = {}
    for item in items:
        if item.quality == QUALITY_RED:
            counts[item.item_type] = counts.get(item.item_type, 0) + (item.quantity or 1)
    return counts


def format_red(counts: dict[str, int]) -> str:
    """按类型排序写成「装备 ×2、蓝图 ×1」；没有时为「无」。"""
    if not counts:
        return '无'
    ordered = sorted(counts.items(), key=lambda pair: -TYPE_RANK.get(pair[0], -99))
    return '、'.join(f'{item_type} ×{count}' for item_type, count in ordered)


@dataclass
class BagelRound:
    """一局的计时、收益与物品。"""

    attempt: int
    started: float
    income: int | None = None
    items: list[BagelItemRecord] = field(default_factory=list)
    outcome: str = OUTCOME_UNFINISHED
    seconds: float = 0.0
    """本局用时，已扣除暂停；收尾时填入。"""


class BagelRunStats:
    """按局累计调查收益与红色物品；每局结束打一行，任务结束输出总表。"""

    def __init__(self) -> None:
        self._paused_total: float = 0.0
        self._paused_since: float | None = None
        self.task_started: float = self._now()
        self.current: BagelRound | None = None
        self.outcome_counts: dict[str, int] = {}
        self.finished_rounds: int = 0
        self.total_income: int = 0
        self.income_unknown_rounds: int = 0
        """调查收益没读到的局数，不计入合计。"""
        self.red_totals: dict[str, int] = {}
        self.sale_count: int = 0
        self.sale_coins: int = 0
        self.sale_unknown: int = 0
        self._finished: bool = False
        """总表已输出；任务收尾的多个入口只输出一次。"""

    def start_round(self, attempt: int) -> None:
        """开始新的一局；上一局没收尾时按未完成记账。

        Args:
            attempt: 本局是第几次入场。
        """
        if self.current is not None:
            self.finish_round()
        self.current = BagelRound(attempt=attempt, started=self._now())

    def pause(self) -> None:
        """任务暂停；重复调用只按第一次计时。"""
        if self._paused_since is None:
            self._paused_since = time.monotonic()

    def resume(self) -> None:
        """任务恢复；暂停期间不计入任何用时。"""
        if self._paused_since is not None:
            self._paused_total += time.monotonic() - self._paused_since
            self._paused_since = None

    def _now(self) -> float:
        """扣除暂停后的时钟，含正在进行的暂停。"""
        ongoing = 0.0 if self._paused_since is None else time.monotonic() - self._paused_since
        return time.monotonic() - self._paused_total - ongoing

    def set_income(self, income: int | None) -> None:
        """记录本局调查收益；读不到时保持未知。"""
        if self.current is not None and income is not None:
            self.current.income = income

    def set_items(self, items: list[BagelItemRecord]) -> None:
        """记录本局安全箱带出的物品。"""
        if self.current is not None:
            self.current.items = list(items)

    def set_outcome(self, outcome: str) -> None:
        """记录本局结果。"""
        if self.current is not None:
            self.current.outcome = outcome

    def finish_round(self) -> BagelRound | None:
        """收尾当前局，输出一行本局统计。

        Returns:
            收尾的这一局；没有进行中的局时为 None。
        """
        current = self.current
        if current is None:
            return None
        self.current = None
        seconds = self._now() - current.started
        current.seconds = seconds
        self.finished_rounds += 1
        self.outcome_counts[current.outcome] = self.outcome_counts.get(current.outcome, 0) + 1
        if current.income is not None:
            self.total_income += current.income
        elif current.outcome != OUTCOME_UNFINISHED:
            self.income_unknown_rounds += 1
        red = red_counts(current.items)
        for item_type, count in red.items():
            self.red_totals[item_type] = self.red_totals.get(item_type, 0) + count
        log.info(
            '贝果本局统计：第 %s 次入场 · %s · 调查收益 %s · 用时 %s · 红色：%s',
            current.attempt, current.outcome, format_value(current.income),
            format_duration(seconds), format_red(red),
        )
        return current

    def finish_task(self) -> None:
        """任务结束：收尾未完成的局，输出总表；重复调用只输出一次。"""
        if self._finished:
            return
        self._finished = True
        if self.current is not None:
            self.finish_round()
        if not self.finished_rounds:
            return
        counts = ' / '.join(
            f'{name} {self.outcome_counts[name]}'
            for name in (OUTCOME_SUCCESS, OUTCOME_EMPTY, OUTCOME_FAILED, OUTCOME_UNSUPPORTED, OUTCOME_UNFINISHED)
            if self.outcome_counts.get(name)
        )
        log.info('贝果收益统计：共 %s 局（%s）· 用时 %s', self.finished_rounds, counts, format_duration(self._elapsed()))
        log.info('贝果收益统计：%s', self._income_text())
        log.info('贝果收益统计：红色物品：%s', format_red(self.red_totals))
        if self.sale_count:
            log.info('贝果出售统计：出售 %s 次，共 %s 齿轮硬币%s', self.sale_count, self.sale_coins,
                     f'（{self.sale_unknown} 次未读到）' if self.sale_unknown else '')

    def summary(self, stop_reason: str | None) -> str | None:
        """推送用的短摘要；一局都没结束时为 None。

        Args:
            stop_reason: 异常停止的原因；正常结束为 None。
        """
        if not self.finished_rounds:
            return None
        lines = [] if stop_reason is None else [f'已停止：{stop_reason}']
        lines.append(
            f'成功 {self.outcome_counts.get(OUTCOME_SUCCESS, 0)} 局 · '
            f'失败 {self.outcome_counts.get(OUTCOME_FAILED, 0)} 局 · '
            f'用时 {format_duration(self._elapsed())}'
        )
        lines.append(self._income_text())
        lines.append(f'红色物品：{format_red(self.red_totals)}')
        return '\n'.join(lines)

    def record_sale(self, coins: int | None) -> None:
        """记录一次出售所得；读不到时只计次数。"""
        self.sale_count += 1
        if coins is None:
            self.sale_unknown += 1
            log.info('贝果出售统计：本次出售获得未读到；累计出售 %s 次', self.sale_count)
            return
        self.sale_coins += coins
        log.info(
            '贝果出售统计：本次获得 %s 齿轮硬币；累计出售 %s 次，共 %s（%s 次未读到）',
            coins, self.sale_count, self.sale_coins, self.sale_unknown,
        )

    def _elapsed(self) -> float:
        """任务开始以来扣除暂停后的秒数。"""
        return self._now() - self.task_started

    def _income_text(self) -> str:
        """写成「调查收益合计 770.0K（每小时约 4.12M）」；括号里另注没读到收益的局数。"""
        notes: list[str] = []
        hours = self._elapsed() / 3600
        if hours > 0:
            notes.append(f'每小时约 {format_value(round(self.total_income / hours))}')
        if self.income_unknown_rounds:
            notes.append(f'{self.income_unknown_rounds} 局未读到，未计入')
        suffix = f'（{"；".join(notes)}）' if notes else ''
        return f'调查收益合计 {format_value(self.total_income)}{suffix}'
