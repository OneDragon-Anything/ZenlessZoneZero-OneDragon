from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfig,
)
from zzz_od.context.zzz_context import ZContext

DEFAULT_GROUP_ID = application_const.DEFAULT_GROUP_ID


class _OneDragonAppConfigCompat:
    def __init__(self, ctx: ZContext):
        self.ctx = ctx
        self._temp_app_run_list: Optional[list[str]] = None
        self.instance_idx = ctx.current_instance_idx

    def _group_config(self) -> ApplicationGroupConfig:
        return self.ctx.app_group_manager.get_one_dragon_group_config(
            instance_idx=self.ctx.current_instance_idx
        )

    @property
    def temp_app_run_list(self) -> Optional[list[str]]:
        return self._temp_app_run_list

    def set_temp_app_run_list(self, app_run_list: Optional[list[str]]) -> None:
        self._temp_app_run_list = app_run_list

    def clear_temp_app_run_list(self) -> None:
        self._temp_app_run_list = None

    def get(self, key: str, default=None):
        if key == "app_run_list":
            return self.app_run_list
        if key == "app_order":
            return self.app_order
        return default

    @property
    def app_order(self) -> list[str]:
        return [item.app_id for item in self._group_config().app_list]

    @app_order.setter
    def app_order(self, new_list: list[str]) -> None:
        self._group_config().set_app_order(new_list)

    def move_up_app(self, app_id: str) -> None:
        self._group_config().move_up_app(app_id)

    @property
    def app_run_list(self) -> list[str]:
        if self._temp_app_run_list is not None:
            return self._temp_app_run_list
        return [item.app_id for item in self._group_config().app_list if item.enabled]

    @app_run_list.setter
    def app_run_list(self, new_list: list[str]) -> None:
        selected = set(new_list)
        group_config = self._group_config()
        changed = False
        for item in group_config.app_list:
            enable = item.app_id in selected
            if item.enabled != enable:
                item.enabled = enable
                changed = True
        if changed:
            group_config.save_app_list()

    def set_app_run(self, app_id: str, to_run: bool) -> None:
        self._group_config().set_app_enable(app_id, to_run)


def get_one_dragon_app_config(ctx: ZContext) -> _OneDragonAppConfigCompat:
    compat = getattr(ctx, "_api_one_dragon_app_config", None)
    if compat is None or getattr(compat, "instance_idx", None) != ctx.current_instance_idx:
        compat = _OneDragonAppConfigCompat(ctx)
        setattr(ctx, "_api_one_dragon_app_config", compat)
    return compat


def get_app_config(
    ctx: ZContext,
    *,
    app_id: str,
    group_id: Optional[str] = None,
    instance_idx: Optional[int] = None,
):
    """Fetch application config through run_context with sensible defaults."""
    if instance_idx is None:
        instance_idx = ctx.current_instance_idx
    if group_id is None:
        group_id = DEFAULT_GROUP_ID

    config = ctx.run_context.get_config(
        app_id=app_id,
        instance_idx=instance_idx,
        group_id=group_id,
    )
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CONFIG_NOT_FOUND",
                    "message": f"Config for app '{app_id}' not found",
                }
            },
        )
    return config


def get_app_run_record(
    ctx: ZContext,
    *,
    app_id: str,
    instance_idx: Optional[int] = None,
):
    """Fetch application run record via run_context."""
    if instance_idx is None:
        instance_idx = ctx.current_instance_idx

    record = ctx.run_context.get_run_record(app_id=app_id, instance_idx=instance_idx)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "RUN_RECORD_NOT_FOUND",
                    "message": f"Run record for app '{app_id}' not found",
                }
            },
        )
    return record
