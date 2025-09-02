from __future__ import annotations

from typing import Any, Dict, List

from one_dragon.base.operation.application_run_record import AppRunRecord


STATUS_CODE_TO_NAME = {
    AppRunRecord.STATUS_WAIT: "WAIT",
    AppRunRecord.STATUS_SUCCESS: "SUCCESS",
    AppRunRecord.STATUS_FAIL: "FAIL",
    AppRunRecord.STATUS_RUNNING: "RUNNING",
}


def iter_app_run_records(ctx) -> List[AppRunRecord]:
    results: List[AppRunRecord] = []
    for attr_name in dir(ctx):
        try:
            value = getattr(ctx, attr_name)
        except Exception:
            continue
        if isinstance(value, AppRunRecord):
            results.append(value)
    return results


def build_onedragon_aggregate(ctx) -> Dict[str, Any]:
    records = iter_app_run_records(ctx)
    items: List[Dict[str, Any]] = []
    counts = {"WAIT": 0, "SUCCESS": 0, "FAIL": 0, "RUNNING": 0}
    for r in records:
        status_name = STATUS_CODE_TO_NAME.get(r.run_status, "UNKNOWN")
        if status_name in counts:
            counts[status_name] += 1
        items.append(
            {
                "appId": getattr(r, "app_id", ""),
                "status": status_name,
                "dt": getattr(r, "dt", None),
                "runTime": getattr(r, "run_time", None),
                "runTimeFloat": getattr(r, "run_time_float", None),
            }
        )
    total = len(items)
    progress = (counts["SUCCESS"] / total) if total > 0 else 0.0
    return {
        "total": total,
        "counts": counts,
        "items": items,
        "progress": progress,
    }






