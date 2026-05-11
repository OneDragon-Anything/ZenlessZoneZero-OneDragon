from __future__ import annotations

from typing import Any

from zzz_od.application.inventory_scan.InventoryDataProcessor import InventoryDataProcessor


def disc_relative_score(
    processor: InventoryDataProcessor,
    disc: dict[str, Any],
    position: int,
    character_weight: dict[str, float],
    slot_mapping: dict[str, str],
) -> float | None:
    """使用 InventoryDataProcessor.calculate_actual_disc_score 的 relativeScore。"""
    disc_copy = disc.copy()
    disc_copy["position"] = position
    try:
        result = processor.calculate_actual_disc_score(
            disc_copy, character_weight, slot_mapping
        )
        return float(result.get("relativeScore", 0.0))
    except Exception:
        return None


def disc_fingerprint(disc: dict[str, Any]) -> tuple[Any, ...]:
    """用于粗略判断是否同一驱动盘实例（无游戏内 UID 时的占位）。"""
    subs = disc.get("substats") or []
    sub_tuples = tuple(
        sorted(
            (s.get("key"), s.get("upgrades", 0)) for s in subs if isinstance(s, dict)
        )
    )
    return (
        disc.get("setKey"),
        disc.get("slotKey"),
        disc.get("level"),
        disc.get("mainStatKey"),
        sub_tuples,
    )
