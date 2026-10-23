from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.application.bagel.bagel_const import (
    APP_ID,
    CLEAN_MODE_CUSTOM,
    CLEAN_MODE_DEFAULT,
    CLEAN_QUALITIES,
    CLEAN_TYPES,
    DEFAULT_CLEAN_QUALITIES,
    DEFAULT_CLEAN_TYPES,
)


@dataclass(frozen=True)
class BagelCleanStep:
    """一次出售：类型和品质同时命中才卖。"""

    types: tuple[str, ...]
    qualities: tuple[str, ...]


class BagelConfig(ApplicationConfig):
    """贝果运行上限、入箱和仓库清理设置；按账号、应用组隔离。"""

    def __init__(self, instance_idx: int, group_id: str) -> None:
        """加载当前账号和应用组的配置。"""
        super().__init__(APP_ID, instance_idx, group_id)

    @property
    def max_success_rounds(self) -> int:
        """成功入仓多少局后结束；0 不限制成功次数。"""
        return self.get('max_success_rounds', 1)

    @max_success_rounds.setter
    def max_success_rounds(self, value: int) -> None:
        """保存成功局数上限。"""
        if type(value) is not int or not 0 <= value <= 1000:
            raise ValueError('max_success_rounds 必须是 0 至 1000 的整数')
        self.update('max_success_rounds', value)

    @property
    def max_failure_retries(self) -> int:
        """本次任务因失败最多额外入场多少次；成功不清零。"""
        return self.get('max_failure_retries', 5)

    @max_failure_retries.setter
    def max_failure_retries(self, value: int) -> None:
        """保存累计失败重试上限，0 表示失败后只结算。"""
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError('max_failure_retries 必须是 0 至 100 的整数')
        self.update('max_failure_retries', value)

    @property
    def blueprint_priority(self) -> bool:
        """蓝图是否优先于全部非蓝图入箱；旧配置缺项也开启。"""
        return self.get('blueprint_priority', True)

    @blueprint_priority.setter
    def blueprint_priority(self, value: bool) -> None:
        """保存蓝图优先开关，不影响仓库出售。"""
        if type(value) is not bool:
            raise ValueError('blueprint_priority 必须是布尔值')
        self.update('blueprint_priority', value)

    @property
    def auto_clean_warehouse(self) -> bool:
        """入仓后是否用快速选择卖掉 C–S 的贵重物品、战术棱镜和其他。"""
        return self.get('auto_clean_warehouse', True)

    @auto_clean_warehouse.setter
    def auto_clean_warehouse(self, value: bool) -> None:
        """保存仓库清理开关。"""
        if type(value) is not bool:
            raise ValueError('auto_clean_warehouse 必须是布尔值')
        self.update('auto_clean_warehouse', value)

    @property
    def sell_interval(self) -> int:
        """本任务多少次非空入仓后出售；失败局带回物资也计入。"""
        return self.get('sell_interval', 1)

    @sell_interval.setter
    def sell_interval(self, value: int) -> None:
        """保存出售间隔，至少 1 局。"""
        if type(value) is not int or value < 1 or value > 999:
            raise ValueError('sell_interval 必须是 1 至 999 的整数')
        self.update('sell_interval', value)

    @property
    def clean_mode(self) -> str:
        """default 用固定类型和品质；custom 按 clean_steps 顺序多次出售。"""
        return self._text_mode('clean_mode', CLEAN_MODE_DEFAULT)

    @clean_mode.setter
    def clean_mode(self, value: str) -> None:
        """只接受默认或自定义。"""
        if value not in (CLEAN_MODE_DEFAULT, CLEAN_MODE_CUSTOM):
            raise ValueError('clean_mode 只能是 default 或 custom')
        self.update('clean_mode', value)

    @property
    def clean_steps(self) -> list[BagelCleanStep]:
        """自定义时按列表顺序各出售一次。没有配置就是还没有步骤。"""
        raw = self.get('clean_steps', [])
        if type(raw) is not list:
            raise ValueError('clean_steps 必须是列表')
        return [self._parse_step(item) for item in raw]

    @clean_steps.setter
    def clean_steps(self, value: list[BagelCleanStep]) -> None:
        """保存出售步骤。"""
        if type(value) is not list:
            raise ValueError('clean_steps 必须是列表')
        self.update('clean_steps', [self._step_dict(step) for step in value])

    def add_clean_step(self, step: BagelCleanStep | None = None) -> None:
        """在末尾追加一步。"""
        steps = list(self.clean_steps)
        steps.append(step or BagelCleanStep((), ()))
        self.clean_steps = steps

    def update_clean_step(self, index: int, step: BagelCleanStep) -> None:
        """替换指定步骤。"""
        steps = list(self.clean_steps)
        if not 0 <= index < len(steps):
            raise ValueError('清理步骤序号超出范围')
        steps[index] = step
        self.clean_steps = steps

    def delete_clean_step(self, index: int) -> None:
        """删除指定步骤。"""
        steps = list(self.clean_steps)
        if not 0 <= index < len(steps):
            raise ValueError('清理步骤序号超出范围')
        del steps[index]
        self.clean_steps = steps

    def move_clean_step(self, index: int, target: int) -> None:
        """把一步挪到目标位置。"""
        steps = list(self.clean_steps)
        if not 0 <= index < len(steps) or not 0 <= target < len(steps):
            raise ValueError('清理步骤序号超出范围')
        step = steps.pop(index)
        steps.insert(target, step)
        self.clean_steps = steps

    def clean_filter_groups(self) -> tuple[tuple[str, ...], ...]:
        """每步快速选择要点中的区域名。默认只有固定的一步。"""
        if self.clean_mode != CLEAN_MODE_CUSTOM:
            names = (*DEFAULT_CLEAN_TYPES, *DEFAULT_CLEAN_QUALITIES)
            return (tuple(f'筛选-{name}' for name in names),)
        return tuple(
            tuple(f'筛选-{name}' for name in (*step.types, *step.qualities))
            for step in self.clean_steps
        )

    def _parse_step(self, value: object) -> BagelCleanStep:
        """读取一步；名单外或重复的名字留给启动校验拒绝。"""
        if type(value) is not dict:
            raise ValueError('清理步骤必须是对象')
        return BagelCleanStep(tuple(self._stored_names(value.get('types'))), tuple(self._stored_names(value.get('qualities'))))

    def _step_dict(self, step: BagelCleanStep) -> dict[str, list[str]]:
        """写入前校验类型和品质。"""
        types = list(step.types)
        qualities = list(step.qualities)
        self._set_names_checked(types, CLEAN_TYPES, '清理类型')
        self._set_names_checked(qualities, CLEAN_QUALITIES, '清理品质')
        return {'types': types, 'qualities': qualities}

    def _stored_names(self, value: object) -> list[str]:
        """读取一步里的名字列表。"""
        if type(value) is not list or any(type(item) is not str for item in value):
            raise ValueError('清理步骤的类型和品质必须是字符串列表')
        return list(value)

    def _text_mode(self, name: str, default: str) -> str:
        """读取文本配置；手改成非文本时交给启动校验拒绝。"""
        value = self.get(name, default)
        if type(value) is not str:
            raise ValueError(f'{name} 必须是文本')
        return value

    def _set_names_checked(self, value: list[str], allowed: tuple[str, ...], label: str) -> None:
        """拒绝非列表、重复和名单外的名字。"""
        if any(item not in allowed for item in value):
            raise ValueError(f'{label}只能从规定名单里选择')
        if len(set(value)) != len(value):
            raise ValueError(f'{label}不能重复')

    def validate(self) -> None:
        """启动前校验配置。"""
        interval = self.sell_interval
        if type(interval) is not int or not 1 <= interval <= 999:
            raise ValueError('sell_interval 必须是 1 至 999 的整数')
        value = self.max_success_rounds
        if type(value) is not int or not 0 <= value <= 1000:
            raise ValueError('max_success_rounds 必须是 0 至 1000 的整数')
        retries = self.max_failure_retries
        if type(retries) is not int or not 0 <= retries <= 100:
            raise ValueError('max_failure_retries 必须是 0 至 100 的整数')
        if type(self.blueprint_priority) is not bool:
            raise ValueError('blueprint_priority 必须是布尔值')
        if type(self.auto_clean_warehouse) is not bool:
            raise ValueError('auto_clean_warehouse 必须是布尔值')
        if self.clean_mode not in (CLEAN_MODE_DEFAULT, CLEAN_MODE_CUSTOM):
            raise ValueError('clean_mode 只能是 default 或 custom')
        steps = self.clean_steps
        for step in steps:
            if any(name not in CLEAN_TYPES for name in step.types):
                raise ValueError('清理类型不在快速选择里')
            if any(name not in CLEAN_QUALITIES for name in step.qualities):
                raise ValueError('清理品质不在快速选择里')
            if len(set(step.types)) != len(step.types) or len(set(step.qualities)) != len(step.qualities):
                raise ValueError('清理筛选不能重复')
        if (
            self.auto_clean_warehouse
            and self.clean_mode == CLEAN_MODE_CUSTOM
            and (not steps or any(not step.types or not step.qualities for step in steps))
        ):
            raise ValueError('自定义清理每一步都要同时选择类型和品质')


class BagelCleanMode(Enum):
    """清理方案。默认用固定组合，自定义用勾选。"""

    DEFAULT = ConfigItem('默认', CLEAN_MODE_DEFAULT, '默认出售贵重物品、战术棱镜和其他物品的 C–S 品质')
    CUSTOM = ConfigItem('自定义', CLEAN_MODE_CUSTOM, '按勾选的类型和品质出售')


class BagelCleanType(Enum):
    """仓库快速选择里可卖的类型。不含「全部」。"""

    VALUABLE = ConfigItem('贵重物品', '贵重物品')
    PRISM = ConfigItem('战术棱镜', '战术棱镜')
    OTHER = ConfigItem('其他', '其他')
    EQUIP = ConfigItem('装备', '装备')
    TACTIC = ConfigItem('战术道具', '战术道具')
    KEYCARD = ConfigItem('门禁卡', '门禁卡')


class BagelCleanQuality(Enum):
    """仓库快速选择里可卖的品质。"""

    C = ConfigItem('C', 'C')
    B = ConfigItem('B', 'B')
    A = ConfigItem('A', 'A')
    S = ConfigItem('S', 'S')
    Z = ConfigItem('Z', 'Z')
