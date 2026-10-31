"""贝果出生点匹配：用一次定位结果在出生点清单中找唯一命中。

只做纯计算，不截图、不读写配置。连续几帧才算确认、最多观察多久，由调用方决定。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zzz_od.application.bagel.bagel_route_model import BagelSpawnPoint

SPAWN_HIT: str = 'hit'
"""定位落在唯一一个出生点的识别半径内。"""

SPAWN_MISS: str = 'miss'
"""定位不在任何出生点的识别半径内。"""

SPAWN_AMBIGUOUS: str = 'ambiguous'
"""定位同时落在多个出生点的识别半径内，不能任取一个。"""


@dataclass(frozen=True)
class BagelSpawnMatch:
    """一次匹配的结果。"""

    kind: str
    """``SPAWN_HIT`` / ``SPAWN_MISS`` / ``SPAWN_AMBIGUOUS``。"""
    spawn: BagelSpawnPoint | None = None
    """唯一命中的出生点；其余情况为 None。"""
    candidates: tuple[str, ...] = ()
    """半径内全部出生点的标识，歧义时用于日志。"""

    def same_as(self, other: BagelSpawnMatch | None) -> bool:
        """两次匹配结论是否相同：类型相同，命中时出生点也相同。"""
        if other is None or other.kind != self.kind:
            return False
        if self.kind == SPAWN_HIT:
            return self.spawn is not None and other.spawn is not None \
                and self.spawn.spawn_id == other.spawn.spawn_id
        return True

    def describe(self) -> str:
        """日志用的结论文字。"""
        if self.kind == SPAWN_HIT and self.spawn is not None:
            return f'出生点 {self.spawn.name}'
        if self.kind == SPAWN_AMBIGUOUS:
            return f'多个出生点同时命中：{"、".join(self.candidates)}'
        return '不在任何已登记出生点范围内'


def match_spawn(
    spawns: list[BagelSpawnPoint], map_id: str, position: tuple[float, float],
) -> BagelSpawnMatch:
    """在全部已登记出生点中匹配当前位置。

    必须对全部出生点匹配，不能先排除没有开启路线的出生点：否则角色站在
    无路线的出生点时，可能被错判成附近另一个有路线的出生点。

    Args:
        spawns: 全部已登记出生点。
        map_id: 当前定位所在地图。
        position: 当前全局坐标。

    Returns:
        匹配结论。
    """
    hits = [
        spawn for spawn in spawns
        if spawn.map_id == map_id and spawn.distance_to(*position) <= spawn.radius
    ]
    if not hits:
        return BagelSpawnMatch(SPAWN_MISS)
    if len(hits) > 1:
        return BagelSpawnMatch(
            SPAWN_AMBIGUOUS, candidates=tuple(spawn.name for spawn in hits),
        )
    return BagelSpawnMatch(SPAWN_HIT, spawn=hits[0], candidates=(hits[0].name,))
