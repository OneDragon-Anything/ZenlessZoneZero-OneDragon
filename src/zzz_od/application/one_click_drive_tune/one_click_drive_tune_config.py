from __future__ import annotations

import json

from one_dragon.base.operation.application.application_config import ApplicationConfig

from zzz_od.application.one_click_drive_tune import one_click_drive_tune_const


class OneClickDriveTuneConfig(ApplicationConfig):
    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id=one_click_drive_tune_const.APP_ID,
            instance_idx=instance_idx,
            group_id=group_id,
        )

    @property
    def list_max_scroll_pages(self) -> int:
        return int(self.get("list_max_scroll_pages", 28))

    @list_max_scroll_pages.setter
    def list_max_scroll_pages(self, new_value: int) -> None:
        self.update("list_max_scroll_pages", new_value)

    @property
    def grid_rows(self) -> int:
        return int(self.get("grid_rows", 4))

    @grid_rows.setter
    def grid_rows(self, new_value: int) -> None:
        self.update("grid_rows", new_value)

    @property
    def grid_cols(self) -> int:
        return int(self.get("grid_cols", 5))

    @grid_cols.setter
    def grid_cols(self, new_value: int) -> None:
        self.update("grid_cols", new_value)

    @property
    def min_score_gain(self) -> float:
        return float(self.get("min_score_gain", 0.5))

    @min_score_gain.setter
    def min_score_gain(self, new_value: float) -> None:
        self.update("min_score_gain", new_value)

    @property
    def use_cv_grid(self) -> bool:
        return bool(self.get("use_cv_grid", True))

    @use_cv_grid.setter
    def use_cv_grid(self, new_value: bool) -> None:
        self.update("use_cv_grid", new_value)

    @property
    def filter_s_grade(self) -> bool:
        return bool(self.get("filter_s_grade", True))

    @filter_s_grade.setter
    def filter_s_grade(self, new_value: bool) -> None:
        self.update("filter_s_grade", new_value)

    @property
    def suit_similarity_threshold(self) -> float:
        return float(self.get("suit_similarity_threshold", 0.69))

    @suit_similarity_threshold.setter
    def suit_similarity_threshold(self, new_value: float) -> None:
        self.update("suit_similarity_threshold", new_value)

    @property
    def suit_pick_offset_y(self) -> int:
        return int(self.get("suit_pick_offset_y", -60))

    @suit_pick_offset_y.setter
    def suit_pick_offset_y(self, new_value: int) -> None:
        self.update("suit_pick_offset_y", new_value)

    @property
    def suit_pick_max_scroll_rounds(self) -> int:
        return int(self.get("suit_pick_max_scroll_rounds", 10))

    @suit_pick_max_scroll_rounds.setter
    def suit_pick_max_scroll_rounds(self, new_value: int) -> None:
        self.update("suit_pick_max_scroll_rounds", new_value)

    @property
    def suit_scroll_repeat(self) -> int:
        return int(self.get("suit_scroll_repeat", 3))

    @suit_scroll_repeat.setter
    def suit_scroll_repeat(self, new_value: int) -> None:
        self.update("suit_scroll_repeat", new_value)

    def suit_name_for_slot(self, slot: int) -> str:
        """1–6 号位套装中文名；空字符串表示该槽位不做套装筛选。"""
        default_list = ["", "", "", "", "", ""]
        raw = self.get("suit_slot_names_json", "")
        try:
            arr = json.loads(raw) if raw else default_list
            if not isinstance(arr, list):
                return ""
            idx = slot - 1
            if 0 <= idx < len(arr) and arr[idx]:
                return str(arr[idx]).strip()
        except (json.JSONDecodeError, TypeError):
            pass
        return ""
