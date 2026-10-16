from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from one_dragon.base.config.yaml_operator import invalidate_cache
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_const import APP_ID


def _read_inventory(rows: object) -> dict[tuple[str, str], int]:
    """仅用于校验旧文件，拒绝空身份、重复身份及非法数量。"""
    if not isinstance(rows, list):
        raise ValueError('物品记录格式错误')
    result: dict[tuple[str, str], int] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('物品记录缺少完整身份')
        name, variant = row.get('name'), row.get('variant')
        if not all(isinstance(value, str) and value and value == value.strip() for value in (name, variant)):
            raise ValueError('物品名称与等级/变体不能为空或包含首尾空白')
        item = (name, variant)
        if item in result:
            raise ValueError('物品记录存在重复身份')
        quantity = row.get('quantity')
        if type(quantity) is not int or quantity <= 0:
            raise ValueError('物品数量必须为正整数')
        result[item] = quantity
    return result


class BagelRunRecord(AppRunRecord):
    """保存应用运行状态，校验并原样保留历史物资记录。"""

    def __init__(self, instance_idx: int, game_refresh_hour_offset: int = 0) -> None:
        """加载记录；损坏文件必须报错，不能按空记录重新刷局。"""
        super().__init__(APP_ID, instance_idx, game_refresh_hour_offset)
        if self.file_path is not None and Path(self.file_path).is_file():
            with Path(self.file_path).open(encoding='utf-8') as file:
                raw = yaml.safe_load(file)
            if not isinstance(raw, dict):
                raise ValueError('贝果运行记录损坏，请先核对待处理物资')
            self.data = raw
        collection = self.get('collection')
        if collection is not None:
            self._validate_collection(collection)

    @staticmethod
    def _validate_collection(collection: dict) -> None:
        """校验旧物资记录，避免截断或错误字段被当作初始状态。"""
        if (
            not isinstance(collection, dict)
            or type(collection.get('version')) is not int
            or collection['version'] != 1
        ):
            raise ValueError('不支持的贝果运行记录格式')
        for name in ('rounds', 'empty_rounds', 'failures'):
            value = collection.get(name)
            if type(value) is not int or value < 0:
                raise ValueError(f'贝果运行记录的 {name} 无效')
        targets = _read_inventory(collection.get('targets'))
        deposited = _read_inventory(collection.get('deposited'))
        if not targets or any(
            quantity > targets.get(item, 0) for item, quantity in deposited.items()
        ):
            raise ValueError('贝果运行记录的目标或实得数量无效')
        if 'last_round' not in collection:
            raise ValueError('贝果运行记录缺少上一局结果')
        last_round = collection['last_round']
        if last_round is not None:
            if not isinstance(last_round, dict) or not isinstance(last_round.get('id'), str):
                raise ValueError('贝果上一局标识无效')
            _read_inventory(last_round.get('deposited'))
        if 'pending' not in collection:
            raise ValueError('贝果运行记录缺少待处理状态')
        pending = collection['pending']
        if pending is not None:
            if not isinstance(pending, dict) or pending.get('phase') not in ('collecting', 'depositing'):
                raise ValueError('贝果待处理状态无效')
            if not isinstance(pending.get('id'), str) or not pending['id']:
                raise ValueError('贝果待处理记录缺少局次标识')
            secured = _read_inventory(pending.get('secured'))
            if any(
                quantity + deposited.get(item, 0) > targets.get(item, 0)
                for item, quantity in secured.items()
            ):
                raise ValueError('贝果待核对数量超出任务目标')
            if pending['phase'] == 'depositing':
                _read_inventory(pending.get('warehouse_before'))

    def save(self) -> None:
        """原子替换记录，写入失败时保留原文件并向调用者报错。"""
        if not self._ensure_write_path_ready():
            return
        write_path = self._get_write_path()
        if write_path is None:
            return
        target = Path(write_path)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                dir=target.parent,
                prefix=f'{target.name}.',
                suffix='.tmp',
                delete=False,
            ) as file:
                temporary = Path(file.name)
                yaml.safe_dump(self.data, file, allow_unicode=True, sort_keys=False)
            temporary.replace(target)
            invalidate_cache(str(target))
        except OSError:
            log.error('保存贝果运行记录失败', exc_info=True)
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
