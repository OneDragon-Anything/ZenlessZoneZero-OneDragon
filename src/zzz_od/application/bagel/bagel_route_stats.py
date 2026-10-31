"""贝果路线数据记录：每局一行写入本地文件，任务结束按出生点输出汇总表，不参与流程判断。

记录放在 ``.log/bagel/route_records.jsonl``，所有实例写同一个文件，只保留近 7 天。
汇总表判断每个出生点跑路线好还是直接重开好，判据见 ``extra_hourly``。
口径与限制见 ``docs/develop/zzz/application/bagel.md`` 的「路线数据记录」一节。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_stats import (
    OUTCOME_SUCCESS,
    OUTCOME_UNSUPPORTED,
    format_duration,
    format_value,
)

if TYPE_CHECKING:
    from zzz_od.application.bagel.bagel_route_model import BagelRoute
    from zzz_od.application.bagel.bagel_route_store import BagelRouteCatalog

RECORD_VERSION: int = 1
"""记录格式版本；字段含义变化时递增。"""

RETENTION_DAYS: int = 7
"""记录保留天数，也是汇总表的统计范围。"""

MIN_ROUNDS: int = 5
"""一条路线收益已读到的局数少于它时，标为「样本不足」，不给结论。"""

CONCLUSION_KEEP: str = '保留'
CONCLUSION_DISABLE: str = '建议关闭'
CONCLUSION_FEW: str = '样本不足'
CONCLUSION_UNKNOWN: str = '无法判断'


def route_version(route: BagelRoute) -> str:
    """按路线点内容算出的版本号；点的坐标、类型或顺序一变，版本就变，改名不变。

    Args:
        route: 本局执行的路线。

    Returns:
        8 位十六进制摘要。
    """
    content = json.dumps([point.to_dict() for point in route.points], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(content.encode('utf-8')).hexdigest()[:8]


@dataclass
class BagelRouteRecord:
    """一局的路线数据。"""

    ended_at: str
    """局结束的本地时间，ISO 格式。"""
    instance: int
    map_id: str | None
    """地图；入场后没定位成功时为 None。"""
    spawn_id: str | None
    """出生点；不在已登记出生点范围内时为 None。"""
    route_source: str | None
    """路线来源；没跑路线时为 None，以下三项同。"""
    route_id: str | None
    route_name: str | None
    route_version: str | None
    outcome: str
    seconds: float
    """从零携带入场到返回入口的用时，已扣除暂停，含出售。"""
    income: int | None
    """调查收益；没读到为 None。"""
    red: dict[str, int] = field(default_factory=dict)
    """红色物品：类型 -> 件数。"""

    @classmethod
    def from_json(cls, data: object) -> BagelRouteRecord:
        """从一行记录还原。

        Raises:
            ValueError: 版本不对或字段缺失。
        """
        if not isinstance(data, dict) or data.get('version') != RECORD_VERSION:
            raise ValueError('不支持的记录版本')
        try:
            return cls(**{name: data[name] for name in cls.__dataclass_fields__})
        except (KeyError, TypeError) as error:
            raise ValueError(f'记录字段缺失：{error}') from error


class BagelRouteRecorder:
    """写入、清理和读取路线数据记录；出错只记警告，不影响流程。"""

    def __init__(self, path: Path | None = None) -> None:
        """
        Args:
            path: 记录文件；None 表示 ``.log/bagel/route_records.jsonl``。
        """
        self._path: Path | None = path

    def path(self) -> Path:
        """记录文件路径；首次使用时创建目录。"""
        if self._path is None:
            self._path = Path(os_utils.get_path_under_work_dir('.log', 'bagel')) / 'route_records.jsonl'
        return self._path

    def append(self, record: BagelRouteRecord) -> None:
        """追加一局记录。"""
        try:
            line = json.dumps({'version': RECORD_VERSION, **asdict(record)}, ensure_ascii=False)
            with self.path().open('a', encoding='utf-8') as file:
                file.write(line + '\n')
        except (OSError, TypeError, ValueError):
            log.warning('写入贝果路线数据记录失败，本局不计入路线汇总', exc_info=True)

    def prune(self, now: datetime | None = None) -> None:
        """删除保留期以前的记录和无法读取的行；没有要删的行时不改文件。

        Args:
            now: 当前时间；None 表示本机当前时间。
        """
        try:
            path = self.path()
            if not path.is_file():
                return
            lines = path.read_text(encoding='utf-8').splitlines()
            kept = [line for line in lines if self._parse(line, self._cutoff(now)) is not None]
            if len(kept) == len(lines):
                return
            tmp = path.with_suffix('.tmp')
            tmp.write_text(''.join(f'{line}\n' for line in kept), encoding='utf-8')
            tmp.replace(path)
            log.info('贝果路线数据：删除 %s 条过期或无法读取的记录', len(lines) - len(kept))
        except OSError:
            log.warning('清理贝果路线数据记录失败', exc_info=True)

    def load(self, now: datetime | None = None) -> list[BagelRouteRecord]:
        """读取保留期内的记录；跳过无法读取的行。

        Args:
            now: 当前时间；None 表示本机当前时间。
        """
        try:
            path = self.path()
            if not path.is_file():
                return []
            lines = path.read_text(encoding='utf-8').splitlines()
        except OSError:
            log.warning('读取贝果路线数据记录失败', exc_info=True)
            return []
        cutoff = self._cutoff(now)
        return [record for line in lines if (record := self._parse(line, cutoff)) is not None]

    @staticmethod
    def _cutoff(now: datetime | None) -> datetime:
        """保留期起点，带本地时区。"""
        return (now or datetime.now().astimezone()) - timedelta(days=RETENTION_DAYS)

    @staticmethod
    def _parse(line: str, cutoff: datetime) -> BagelRouteRecord | None:
        """解析一行；过期或无法读取时返回 None。"""
        try:
            record = BagelRouteRecord.from_json(json.loads(line))
            if datetime.fromisoformat(record.ended_at) < cutoff:
                return None
            return record
        except (TypeError, ValueError):
            return None


def _mean(values: list[float]) -> float:
    """平均值；调用方保证非空。"""
    return sum(values) / len(values)


def extra_hourly(income: float, seconds: float, restart_seconds: float | None) -> float | None:
    """额外每小时收益：跑路线比直接重开多花的时间里，每小时多拿多少调查收益。

    两种做法都要入场、识别出生点和退出，只差中间跑路线那段，
    所以用「路线每局收益 ÷（路线每局用时 − 直接重开每局用时）」，
    高于全局每小时收益就值得跑。

    Args:
        income: 路线每局平均调查收益。
        seconds: 路线每局平均用时。
        restart_seconds: 直接重开每局平均用时；没有样本时为 None。

    Returns:
        每小时收益；没有重开样本，或路线用时不比重开长时为 None。
    """
    if restart_seconds is None or seconds <= restart_seconds:
        return None
    return income / (seconds - restart_seconds) * 3600


def report_lines(records: list[BagelRouteRecord], catalog: BagelRouteCatalog) -> list[str]:
    """按地图、出生点生成汇总表，每行一条日志。

    Args:
        records: 保留期内的记录。
        catalog: 当前路线设置；只统计各出生点当前开启路线的当前版本。
    """
    lines: list[str] = []
    map_ids = sorted({record.map_id for record in records if record.map_id is not None})
    for map_id in map_ids:
        lines.extend(_map_lines(map_id, [record for record in records if record.map_id == map_id], catalog))
    return lines


def _map_lines(map_id: str, records: list[BagelRouteRecord], catalog: BagelRouteCatalog) -> list[str]:
    """一张地图的汇总行：第一行是全局数据，之后每个出生点一行。"""
    known = [record for record in records if record.income is not None]
    known_seconds = sum(record.seconds for record in known)
    global_hourly = (
        sum(record.income or 0 for record in known) / known_seconds * 3600 if known_seconds > 0 else None
    )
    restarts = [record for record in records if record.outcome == OUTCOME_UNSUPPORTED]
    restart_seconds = _mean([record.seconds for record in restarts]) if restarts else None
    restart_text = (
        f'直接重开平均 {format_duration(restart_seconds)}（{len(restarts)} 局）'
        if restart_seconds is not None else '直接重开暂无记录'
    )
    hourly_text = format_value(None if global_hourly is None else round(global_hourly))
    lines = [f'{map_id} · 近 {RETENTION_DAYS} 天 {len(records)} 局 · 全局每小时 {hourly_text} · {restart_text}']

    for spawn in catalog.spawns:
        if spawn.map_id != map_id:
            continue
        ref = catalog.active_ref(spawn.spawn_id)
        route = catalog.route(ref) if ref is not None else None
        if route is None:
            own = [record for record in restarts if record.spawn_id == spawn.spawn_id]
            lines.append(f'{spawn.name} · 直接重开 · {_restart_text(own)}')
            continue
        version = route_version(route)
        rows = [
            record for record in records
            if record.spawn_id == spawn.spawn_id and record.route_source == route.source
            and record.route_id == route.route_id and record.route_version == version
        ]
        head = f'{spawn.name} · {route.name}（{version}）'
        if not rows:
            lines.append(f'{head} · 暂无记录')
            continue
        lines.append(f'{head} · {_route_text(rows, restart_seconds, global_hourly)}')

    unregistered = [record for record in restarts if record.spawn_id is None]
    if unregistered:
        lines.append(f'未登记 · 直接重开 · {_restart_text(unregistered)}')
    return lines


def _restart_text(rows: list[BagelRouteRecord]) -> str:
    """直接重开的局数和平均用时。"""
    if not rows:
        return '暂无记录'
    return f'{len(rows)} 局 · 用时 {format_duration(_mean([record.seconds for record in rows]))}'


def _route_text(
    rows: list[BagelRouteRecord], restart_seconds: float | None, global_hourly: float | None,
) -> str:
    """一条路线的局数、成功率、每局收益、用时、额外每小时收益和结论。

    成功率按全部局算；收益和用时只用收益已读到的局，没读到的局另外标出。
    """
    known = [record for record in rows if record.income is not None]
    success = sum(1 for record in rows if record.outcome == OUTCOME_SUCCESS)
    parts = [f'{len(rows)} 局', f'成功率 {success / len(rows):.0%}']
    extra: float | None = None
    if known:
        income = _mean([float(record.income or 0) for record in known])
        seconds = _mean([record.seconds for record in known])
        extra = extra_hourly(income, seconds, restart_seconds)
        parts += [
            f'每局 {format_value(round(income))}',
            f'用时 {format_duration(seconds)}',
            f'额外每小时 {"无法计算" if extra is None else format_value(round(extra))}',
        ]
    if len(known) < MIN_ROUNDS:
        conclusion = CONCLUSION_FEW
    elif extra is None or global_hourly is None:
        conclusion = CONCLUSION_UNKNOWN
    else:
        conclusion = CONCLUSION_KEEP if extra > global_hourly else CONCLUSION_DISABLE
    unknown = len(rows) - len(known)
    note = f'（{unknown} 局未读到）' if unknown else ''
    return ' · '.join(parts) + f' · {conclusion}{note}'
