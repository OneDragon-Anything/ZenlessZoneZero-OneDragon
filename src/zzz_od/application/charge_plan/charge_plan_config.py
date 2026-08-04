import uuid
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.utils.log_utils import log
from zzz_od.application.charge_plan import charge_plan_const


class CardNumEnum(Enum):
    DEFAULT = ConfigItem('默认数量')
    NUM_1 = ConfigItem('1张卡片', '1')
    NUM_2 = ConfigItem('2张卡片', '2')
    NUM_3 = ConfigItem('3张卡片', '3')
    NUM_4 = ConfigItem('4张卡片', '4')
    NUM_5 = ConfigItem('5张卡片', '5')


class RestoreChargeEnum(Enum):
    NONE = ConfigItem('不使用')
    BACKUP_ONLY = ConfigItem('使用储蓄电量')
    ETHER_ONLY = ConfigItem('使用以太电池')
    BOTH = ConfigItem('同时使用储蓄电量和以太电池')


class ChargePlanRunModeEnum(Enum):
    RUN_TIMES = ConfigItem('按次数运行', 'run_times')
    MATERIAL_COUNT = ConfigItem('按材料数量运行', 'material_count')


_FIXED_MATERIAL_TIER_CHAINS: tuple[tuple[str, ...], ...] = (
    ('资深调查员记录', '正式调查员记录', '见习调查员记录'),
    ('音擎能源模块', '变频音擎电源', '音擎蓄电池'),
    ('以太镀剂', '晶质镀剂', '塑化镀剂'),
    ('先行者认证章', '高阶强攻认证章', '初阶强攻认证章'),
    ('破阵者认证章', '高阶击破认证章', '初阶击破认证章'),
    ('掌控者认证章', '高阶异常认证章', '初阶异常认证章'),
    ('统御者认证章', '高阶支援认证章', '初阶支援认证章'),
    ('捍卫者认证章', '高阶防护认证章', '初阶防护认证章'),
    ('裁决者认证章', '高阶命破认证章', '初阶命破认证章'),
)

_MATERIAL_COUNT_MISSION_TYPES: frozenset[str] = frozenset({
    '基础材料',
    '代理人晋升',
    '音擎改装',
    '代理人技能',
})

_MATERIAL_SYNTHESIS_MISSION_TYPES: frozenset[str] = frozenset({
    '代理人晋升',
    '音擎改装',
    '代理人技能',
})


def _normalize_material_count_value(value: object) -> int | None:
    """把配置中的材料数量转为整数，并拒绝布尔值和非整数小数。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ChargePlanItem:
    tab_name: str = '训练'
    category_name: str = '实战模拟室'
    mission_type_name: str = '基础材料'
    mission_name: str | None = '调查专项'
    level: str = '默认等级'
    auto_battle_config: str = '全配队通用'
    run_times: int = 0
    plan_times: int = 1
    run_mode: str = ChargePlanRunModeEnum.RUN_TIMES.value.value
    target_material_name: str = ''
    target_material_count: int = 1
    material_counts: dict[str, int] = field(default_factory=dict)
    include_synthesis: bool = False
    card_num: str = CardNumEnum.DEFAULT.value.value  # 实战模拟室的卡片数量
    predefined_team_idx: int = -1  # 预备配队下标 -1为使用当前配队
    notorious_hunt_buff_num: int = 1  # 恶名狩猎 选择的buff
    plan_id: str | None = None  # 计划的唯一标识符
    skipped: bool = field(default=False, repr=False, metadata={'persist': False})  # 单次运行中是否跳过

    def __post_init__(self) -> None:
        if self.plan_id is None:
            self.plan_id = str(uuid.uuid4())

        self.target_material_name = str(self.target_material_name or '').strip()
        normalized_target_count = _normalize_material_count_value(self.target_material_count)
        self.target_material_count = max(0, normalized_target_count or 0)

        normalized_counts: dict[str, int] = {}
        for material_name, count in (self.material_counts or {}).items():
            normalized_count = _normalize_material_count_value(count)
            if normalized_count is None:
                continue
            if normalized_count > 0:
                normalized_counts[str(material_name)] = normalized_count
        self.material_counts = normalized_counts

    @property
    def is_agent_plan(self) -> bool:
        return self.mission_type_name == '代理人方案培养'

    @property
    def supports_material_count(self) -> bool:
        """当前副本是否只产出一个可按品质识别的材料系列。"""
        return (
            self.category_name == '实战模拟室'
            and self.mission_type_name in _MATERIAL_COUNT_MISSION_TYPES
            and self.mission_name is not None
        )

    @property
    def supports_material_synthesis(self) -> bool:
        """当前材料系列是否支持按 3:1 向上合成。"""
        return self.mission_type_name in _MATERIAL_SYNTHESIS_MISSION_TYPES

    @property
    def is_material_count_plan(self) -> bool:
        """是否选择了按材料数量运行。"""
        return self.run_mode == ChargePlanRunModeEnum.MATERIAL_COUNT.value.value

    @property
    def material_tier_names(self) -> tuple[str, ...]:
        """目标材料及可按 3:1 合成到目标的低级材料名称。"""
        target = self.target_material_name.strip()
        if not target:
            return ()

        for tier_chain in _FIXED_MATERIAL_TIER_CHAINS:
            if target in tier_chain:
                return tier_chain[tier_chain.index(target):]

        if target.startswith('特化型') and len(target) > len('特化型'):
            suffix = target[len('特化型'):]
            return target, f'增强型{suffix}', suffix
        if target.startswith('增强型') and len(target) > len('增强型'):
            suffix = target[len('增强型'):]
            return target, suffix
        if target.startswith('特化') and len(target) > len('特化'):
            suffix = target[len('特化'):]
            return target, f'进阶{suffix}', f'基础{suffix}'
        if target.startswith('进阶') and len(target) > len('进阶'):
            suffix = target[len('进阶'):]
            return target, f'基础{suffix}'
        if target.startswith('高阶') and target.endswith('认证章'):
            suffix = target[len('高阶'):]
            return target, f'初阶{suffix}'
        return (target,)

    @property
    def current_material_count(self) -> int:
        """当前目标材料数量，可按开关计入低级材料的合成结果。"""
        tier_names = self.material_tier_names
        if not tier_names:
            return 0
        if not self.include_synthesis or not self.supports_material_synthesis:
            return self.material_counts.get(tier_names[0], 0)

        lowest_tier_units = 0
        tier_count = len(tier_names)
        for idx, material_name in enumerate(tier_names):
            multiplier = 3 ** (tier_count - idx - 1)
            lowest_tier_units += self.material_counts.get(material_name, 0) * multiplier
        return lowest_tier_units // (3 ** (tier_count - 1))

    def _material_count_invalid_reason(self) -> str | None:
        """返回材料数量计划不能运行的原因。"""
        if not self.supports_material_count:
            return '当前副本不支持按材料数量运行'
        if not self.target_material_name:
            return '目标材料为空'
        if self.target_material_count <= 0:
            return '目标材料数必须大于 0'
        return None

    @property
    def is_finished(self) -> bool:
        """计划是否已达到所选运行方式的目标。"""
        if self.is_material_count_plan:
            invalid_reason = self._material_count_invalid_reason()
            if invalid_reason is not None:
                log.warning(
                    f'材料数量计划配置非法，按已完成处理 '
                    f'plan_id={self.plan_id} category={self.category_name} '
                    f'mission_type={self.mission_type_name} '
                    f'mission={self.mission_name} reason={invalid_reason}'
                )
                return True
            return self.current_material_count >= self.target_material_count
        return self.run_times >= self.plan_times

    @property
    def uid(self) -> str:
        tab_name = self.tab_name or ''
        category_name = self.category_name or ''
        mission_type_name = self.mission_type_name or ''
        mission_name = self.mission_name or ''
        return f'{tab_name}_{category_name}_{mission_type_name}_{mission_name}'

    @property
    def estimated_charge_power(self) -> int:
        # 进本前只做体力预估；未知类型交给副本内流程再检查真实消耗
        if self.category_name == '实战模拟室':
            if self.card_num == CardNumEnum.DEFAULT.value.value:
                return 20
            return int(self.card_num) * 20
        if self.category_name == '区域巡防':
            return 60
        if self.category_name == '专业挑战室':
            return 40
        if self.category_name == '恶名狩猎':
            return 60
        if self.category_name == '合成电池':
            return 60
        return 0  # 未知类型，在副本内检查

    def to_dict(self) -> dict[str, object]:
        return {
            item.name: getattr(self, item.name)
            for item in fields(self)
            if item.metadata.get('persist', True)
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ChargePlanItem':
        return cls(**data)


class ChargePlanConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            instance_idx=instance_idx,
            group_id=group_id,
            app_id=charge_plan_const.APP_ID,
        )

        self.plan_list: list[ChargePlanItem] = []

        for plan_item in self.data.get('plan_list', []):
            self.plan_list.append(ChargePlanItem(**plan_item))

    def save(self):
        plan_list = []

        for plan_item in self.plan_list:
            plan_data = plan_item.to_dict()
            plan_list.append(plan_data)

        self.data['plan_list'] = plan_list

        YamlConfig.save(self)

    def add_plan(self, plan: ChargePlanItem) -> None:
        self.plan_list.append(plan)
        self.save()

    def delete_plan(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.plan_list):
            return
        self.plan_list.pop(idx)
        self.save()

    def update_plan(self, idx: int, plan: ChargePlanItem) -> None:
        if idx < 0 or idx >= len(self.plan_list):
            return
        self.plan_list[idx] = plan
        self.save()

    def move_up(self, idx: int) -> None:
        if idx <= 0 or idx >= len(self.plan_list):
            return

        tmp = self.plan_list[idx - 1]
        self.plan_list[idx - 1] = self.plan_list[idx]
        self.plan_list[idx] = tmp

        self.save()

    def move_top(self, idx: int) -> None:
        if idx <= 0 or idx >= len(self.plan_list):
            return

        tmp = self.plan_list[idx]
        self.plan_list.pop(idx)
        self.plan_list.insert(0, tmp)

        self.save()

    def reset_plans(self) -> None:
        """
        根据运行次数重置运行计划。
        未跳过的按次数计划按整轮扣减，材料计划保持已经累计的数量。
        """
        if len(self.plan_list) == 0:
            return

        eligible = [
            plan
            for plan in self.plan_list
            if (
                not plan.skipped
                and not plan.is_material_count_plan
                and plan.plan_times > 0
            )
        ]
        skipped_agent_plans = [p for p in self.plan_list if p.skipped and p.is_agent_plan]
        modified = False

        if eligible:
            while True:
                if any(not plan.is_finished for plan in eligible):
                    break

                for plan in eligible:
                    plan.run_times -= plan.plan_times
                modified = True

            if not modified:
                return

        for plan in skipped_agent_plans:
            if plan.run_times == 0:
                continue
            plan.run_times = 0
            modified = True

        if modified:
            self.save()

    def try_reset_plan_times_by_dt(self, current_dt: str) -> bool:
        """
        按游戏刷新日清零已运行次数

        Args:
            current_dt: 当前游戏刷新日

        Returns:
            是否执行了清零
        """
        if not self.daily_reset_plan_times:
            return False
        if self.last_daily_reset_dt == current_dt:
            return False

        for plan in self.plan_list:
            plan.run_times = 0
        self.update('last_daily_reset_dt', current_dt, save=False)
        self.save()
        return True

    def get_next_plan(
        self, last_tried_plan: ChargePlanItem | None = None
    ) -> ChargePlanItem | None:
        """
        获取下一个未完成的计划任务（跳过 skipped 的计划）。
        如果提供了 last_tried_plan，则从该任务之后开始查找。
        如果未提供，则从列表的开头查找第一个未完成任务。
        Args:
            last_tried_plan: 上次尝试的计划
        """
        if len(self.plan_list) == 0:
            return None

        start_index = 0
        if last_tried_plan is not None:
            # 1. 从上次尝试的计划之后开始查找
            last_tried_index = -1
            for i, plan in enumerate(self.plan_list):
                if self._is_same_plan(plan, last_tried_plan):
                    last_tried_index = i
                    break

            if last_tried_index != -1:
                start_index = last_tried_index + 1
                # 如果已到达列表末尾，返回 None
                if start_index >= len(self.plan_list):
                    return None
            else:
                # 2. 找不到上次计划则从头开始
                start_index = 0

        # 3. 从指定位置开始遍历查找符合条件的计划
        for i in range(start_index, len(self.plan_list)):
            plan = self.plan_list[i]
            if plan.skipped:
                continue
            if not plan.is_finished:
                return plan

        # 4. 检查完一轮都没找到合适的计划
        return None

    def all_plan_finished(self) -> bool:
        """
        是否全部计划已完成（忽略本次运行中已标记跳过的计划）
        """
        if self.plan_list is None:
            return True

        for plan in self.plan_list:
            if plan.skipped:
                continue
            if not plan.is_finished:
                return False
        return True

    def add_plan_run_times(self, to_add: ChargePlanItem) -> None:
        """
        找到一个合适的计划 增加有一次运行次数
        """
        # 第一次 先找还没有完成的
        for plan in self.plan_list:
            if not self._is_same_plan(plan, to_add):
                continue
            if plan.is_finished:
                continue
            plan.run_times += 1
            self.save()
            return

        # 第二次 就随便加一个
        for plan in self.plan_list:
            if not self._is_same_plan(plan, to_add):
                continue
            plan.run_times += 1
            self.save()
            return

    def add_plan_material_counts(
        self,
        to_add: ChargePlanItem,
        material_counts: dict[str, int],
    ) -> bool:
        """把一场战斗识别到的材料数量合并到对应计划。"""
        for plan in self.plan_list:
            if not self._is_same_plan(plan, to_add):
                continue

            modified = False
            for material_name, count in material_counts.items():
                if count <= 0:
                    continue
                plan.material_counts[material_name] = (
                    plan.material_counts.get(material_name, 0) + count
                )
                modified = True
            if modified:
                self.save()
            return True
        return False

    def _is_same_plan(
        self, x: ChargePlanItem, y: ChargePlanItem, compare_plan_id: bool = True
    ) -> bool:
        if x is None or y is None:
            return False

        # 如果两个计划都有ID，直接比较ID
        if compare_plan_id and x.plan_id and y.plan_id:
            return x.plan_id == y.plan_id

        return x == y

    @property
    def loop(self) -> bool:
        return self.get('loop', True)

    @loop.setter
    def loop(self, new_value: bool) -> None:
        self.update('loop', new_value)

    @property
    def daily_reset_plan_times(self) -> bool:
        return self.get('daily_reset_plan_times', False)

    @daily_reset_plan_times.setter
    def daily_reset_plan_times(self, new_value: bool) -> None:
        self.update('daily_reset_plan_times', new_value)

    @property
    def last_daily_reset_dt(self) -> str:
        return self.get('last_daily_reset_dt', '')

    @last_daily_reset_dt.setter
    def last_daily_reset_dt(self, new_value: str) -> None:
        self.update('last_daily_reset_dt', new_value)

    @property
    def skip_plan(self) -> bool:
        return self.get('skip_plan', False)

    @skip_plan.setter
    def skip_plan(self, new_value: bool) -> None:
        self.update('skip_plan', new_value)

    @property
    def double_reward(self) -> bool:
        return self.get('double_reward', False)

    @double_reward.setter
    def double_reward(self, new_value: bool) -> None:
        self.update('double_reward', new_value)

    @property
    def combat_simulation_double_reward_config(self) -> ChargePlanItem:
        data = self.get('combat_simulation_double_reward_config', {})
        return ChargePlanItem.from_dict(data)

    @combat_simulation_double_reward_config.setter
    def combat_simulation_double_reward_config(self, new_value: ChargePlanItem) -> None:
        self.update('combat_simulation_double_reward_config', new_value.to_dict())

    @property
    def restore_charge(self) -> str:
        return self.get('restore_charge', RestoreChargeEnum.NONE.value.value)

    @restore_charge.setter
    def restore_charge(self, new_value: str) -> None:
        self.update('restore_charge', new_value)

    @property
    def is_restore_charge_enabled(self) -> bool:
        return self.restore_charge != RestoreChargeEnum.NONE.value.value

    # 运行态/身份字段(set_config 拒绝;详见 spec v5 _RO_FIELDS)
    _RO_FIELDS: ClassVar[set[str]] = {
        'plan_id',
        'last_daily_reset_dt',
        'skip_plan',
        'material_counts',
    }

    @classmethod
    def validate_item(cls, ctx: 'ZContext', item: 'ChargePlanItem') -> str | None:
        """校验 plan item 业务合法性:category / mission_type / mission_name 在 compendium 合法。

        合法返 None,非法返原因(含合法值)。供 MCP config 工具写入前校验。
        """
        categories = [c.value for c in ctx.compendium_service.get_charge_plan_category_list()]
        if item.category_name not in categories:
            return f'category {item.category_name} 不合法(合法: {categories})'
        mission_types = [m.value for m in ctx.compendium_service.get_charge_plan_mission_type_list(item.category_name)]
        if mission_types:
            # category 有 mission_type(常规副本):必须合法
            if item.mission_type_name not in mission_types:
                return f'mission_type {item.mission_type_name} 不合法(合法: {mission_types})'
        elif item.mission_type_name:
            # category 无 mission_type(合成电池等):必须为空
            return f'{item.category_name} 无 mission_type,mission_type_name 应为空(当前: {item.mission_type_name})'
        missions = [m.value for m in ctx.compendium_service.get_charge_plan_mission_list(item.category_name, item.mission_type_name)] if mission_types else []
        if missions and item.mission_name is None:
            return f'mission_name 必填(合法: {missions})'
        if item.mission_name is not None and item.mission_name not in missions:
            return f'mission {item.mission_name} 不合法(合法: {missions})'
        if item.is_material_count_plan:
            if not item.supports_material_count:
                return '按材料数量运行仅支持实战模拟室的单一材料系列计划'
            if not item.target_material_name:
                return '按材料数量运行时 target_material_name 必填'
            material_names = [
                option.value
                for option in ctx.compendium_service.get_charge_plan_material_list(
                    item.category_name,
                    item.mission_type_name,
                    item.mission_name,
                )
            ]
            if item.target_material_name not in material_names:
                return (
                    f'target_material_name {item.target_material_name} 不合法'
                    f'(合法: {material_names})'
                )
            if item.target_material_count <= 0:
                return '按材料数量运行时 target_material_count 必须大于 0'
            if item.include_synthesis and not item.supports_material_synthesis:
                return '当前材料不支持 3:1 合成折算'
        return None
