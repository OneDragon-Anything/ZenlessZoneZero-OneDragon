from __future__ import annotations

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


class BagelConfig(ApplicationConfig):
    """贝果运行上限和仓库清理设置；按账号、应用组隔离。"""

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
        """多少个成功入仓局出售一次；1 表示每局都卖。"""
        return self.get('sell_interval', 1)

    @sell_interval.setter
    def sell_interval(self, value: int) -> None:
        """保存出售间隔，至少 1 局。"""
        if type(value) is not int or value < 1 or value > 999:
            raise ValueError('sell_interval 必须是 1 至 999 的整数')
        self.update('sell_interval', value)

    @property
    def clean_mode(self) -> str:
        """default 用固定类型和品质；custom 用下面两项勾选。"""
        return self._text_mode('clean_mode', CLEAN_MODE_DEFAULT)

    @clean_mode.setter
    def clean_mode(self, value: str) -> None:
        """只接受默认或自定义。"""
        if value not in (CLEAN_MODE_DEFAULT, CLEAN_MODE_CUSTOM):
            raise ValueError('clean_mode 只能是 default 或 custom')
        self.update('clean_mode', value)

    @property
    def clean_types(self) -> list[str]:
        """自定义时要卖的仓库类型。"""
        return self._name_list('clean_types')

    @clean_types.setter
    def clean_types(self, value: list[str]) -> None:
        """保存类型勾选，不接受名单以外的名字。"""
        self._set_names('clean_types', value, CLEAN_TYPES)

    @property
    def clean_qualities(self) -> list[str]:
        """自定义时要卖的品质。"""
        return self._name_list('clean_qualities')

    @clean_qualities.setter
    def clean_qualities(self, value: list[str]) -> None:
        """保存品质勾选，不接受名单以外的名字。"""
        self._set_names('clean_qualities', value, CLEAN_QUALITIES)

    def clean_filter_areas(self) -> tuple[str, ...]:
        """快速选择里要点中的区域名。默认忽略自定义勾选。"""
        if self.clean_mode == CLEAN_MODE_CUSTOM:
            names = (*self.clean_types, *self.clean_qualities)
        else:
            names = (*DEFAULT_CLEAN_TYPES, *DEFAULT_CLEAN_QUALITIES)
        return tuple(f'筛选-{name}' for name in names)

    def _text_mode(self, name: str, default: str) -> str:
        """读取文本配置；手改成非文本时交给启动校验拒绝。"""
        value = self.get(name, default)
        if type(value) is not str:
            raise ValueError(f'{name} 必须是文本')
        return value

    def _name_list(self, name: str) -> list[str]:
        """读取字符串列表；缺省为空。"""
        value = self.get(name, [])
        if type(value) is not list or any(type(item) is not str for item in value):
            raise ValueError(f'{name} 必须是字符串列表')
        return list(value)

    def _set_names(self, name: str, value: list[str], allowed: tuple[str, ...]) -> None:
        """拒绝非列表、重复和名单外的名字。"""
        if type(value) is not list or any(type(item) is not str or item not in allowed for item in value):
            raise ValueError(f'{name} 只能从规定名单里选择')
        if len(set(value)) != len(value):
            raise ValueError(f'{name} 不能重复')
        self.update(name, value)

    def validate(self) -> None:
        """启动前校验手工修改的 YAML；旧名单字段不再读取。"""
        value = self.max_success_rounds
        if type(value) is not int or not 0 <= value <= 1000:
            raise ValueError('max_success_rounds 必须是 0 至 1000 的整数')
        retries = self.max_failure_retries
        if type(retries) is not int or not 0 <= retries <= 100:
            raise ValueError('max_failure_retries 必须是 0 至 100 的整数')
        if type(self.auto_clean_warehouse) is not bool:
            raise ValueError('auto_clean_warehouse 必须是布尔值')
        if self.clean_mode not in (CLEAN_MODE_DEFAULT, CLEAN_MODE_CUSTOM):
            raise ValueError('clean_mode 只能是 default 或 custom')
        types = self.clean_types
        qualities = self.clean_qualities
        if any(name not in CLEAN_TYPES for name in types):
            raise ValueError('清理类型不在快速选择里')
        if any(name not in CLEAN_QUALITIES for name in qualities):
            raise ValueError('清理品质不在快速选择里')
        if len(set(types)) != len(types) or len(set(qualities)) != len(qualities):
            raise ValueError('清理筛选不能重复')
        if (
            self.auto_clean_warehouse
            and self.clean_mode == CLEAN_MODE_CUSTOM
            and (not types or not qualities)
        ):
            raise ValueError('自定义清理要同时选择类型和品质')


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
