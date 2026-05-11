from __future__ import annotations

import json
import time
from typing import Any

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.screen_utils import FindAreaResultEnum, find_area_in_screen
from one_dragon.utils import cv2_utils, os_utils
from one_dragon.utils.log_utils import log
from one_dragon.utils.str_utils import find_best_match_by_similarity

from zzz_od.application.inventory_scan.InventoryDataProcessor import InventoryDataProcessor
from zzz_od.application.inventory_scan.parser.agent_parser import AgentParser
from zzz_od.application.inventory_scan.parser.drive_disk_parser import DriveDiskParser
from zzz_od.application.one_click_drive_tune import one_click_drive_tune_const
from zzz_od.application.one_click_drive_tune.drive_tune_cv import contours_to_grid_centers
from zzz_od.application.one_click_drive_tune.drive_tune_scoring import (
    disc_fingerprint,
    disc_relative_score,
)
from zzz_od.application.one_click_drive_tune.one_click_drive_tune_config import (
    OneClickDriveTuneConfig,
)
from zzz_od.application.one_click_drive_tune.one_click_drive_tune_run_record import (
    OneClickDriveTuneRunRecord,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class OneClickDriveTuneApp(ZApplication):
    """遍历代理人驱动盘槽位，在替换列表中以网格+滚动扫描仓库可见驱动盘并择优换装（不强化）。"""

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=one_click_drive_tune_const.APP_ID,
            op_name=one_click_drive_tune_const.APP_NAME,
        )
        self.config: OneClickDriveTuneConfig = self.ctx.run_context.get_config(
            app_id=one_click_drive_tune_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: OneClickDriveTuneRunRecord = (
            self.ctx.run_context.get_run_record(
                instance_idx=self.ctx.current_instance_idx,
                app_id=one_click_drive_tune_const.APP_ID,
            )
        )

        self._processor = InventoryDataProcessor()
        self._slot_mapping: dict[str, str] = {}
        self._slot_mapping_path = os_utils.get_path_under_work_dir(
            "src", "zzz_od", "game_data", "slot_Mapping.json"
        )

        self.agent_unlocked_area = self.ctx.screen_loader.get_area(
            "代理人-信息", "代理人-是否为已解锁"
        )
        self.agent_name_area = self.ctx.screen_loader.get_area(
            "代理人-信息", "代理人-名称"
        )
        self.switch_next_agent_area = self.ctx.screen_loader.get_area(
            "代理人-信息", "按钮-下一位代理人"
        )
        self.replace_btn_area = self.ctx.screen_loader.get_area(
            "代理人-装备详细", "替换"
        )
        self.drive_disk_detail_area = self.ctx.screen_loader.get_area(
            "代理人-装备详细", "驱动盘详细信息"
        )
        self.drive_list_area = self.ctx.screen_loader.get_area(
            "代理人-装备详细", "驱动盘列表"
        )
        self.detail_back_area = self.ctx.screen_loader.get_area(
            "代理人-装备详细", "返回"
        )
        self.equipment_back_area = self.ctx.screen_loader.get_area(
            "代理人-装备", "返回"
        )
        self.agent_list_basic_area = self.ctx.screen_loader.get_area(
            "代理人-列表", "基础"
        )
        self.material_confirm_area = self.ctx.screen_loader.get_area(
            "代理人-装备详细", "材料返还-确认"
        )
        self.filter_btn_area = self.ctx.screen_loader.get_area(
            "代理人-装备详细", "筛选"
        )
        self.filter_reset_area = self.ctx.screen_loader.get_area("筛选", "重置")
        self.filter_s_area = self.ctx.screen_loader.get_area("筛选", "S")
        self.filter_suit_entry_area = self.ctx.screen_loader.get_area(
            "筛选", "套装选择"
        )
        self.suit_confirm_area = self.ctx.screen_loader.get_area(
            "套装筛选", "确认筛选"
        )
        self.suit_list_area = self.ctx.screen_loader.get_area("套装筛选", "套装列表")

        self._drive_parser = DriveDiskParser(ctx)

    def _load_slot_mapping(self) -> None:
        if self._slot_mapping:
            return
        try:
            with open(self._slot_mapping_path, encoding="utf-8") as f:
                self._slot_mapping = json.load(f)
        except Exception as e:
            log.error(f"加载 slot 映射失败: {e}", exc_info=True)
            self._slot_mapping = {}

    def _ocr_items_from_image(self, image: Any) -> list[dict[str, Any]]:
        ocr_result = self.ctx.ocr.run_ocr(image)
        if not ocr_result:
            return []
        ocr_items: list[dict[str, Any]] = []
        for text, match_list in ocr_result.items():
            for match in match_list:
                pos = None
                if hasattr(match, "x"):
                    pos = (match.x, match.y, match.x + match.w, match.y + match.h)
                ocr_items.append(
                    {
                        "text": text,
                        "confidence": match.confidence
                        if hasattr(match, "confidence")
                        else 1.0,
                        "position": pos,
                    }
                )
        return ocr_items

    def _read_agent_key(self, screen: Any) -> str | None:
        crop = cv2_utils.crop_image_only(screen, self.agent_name_area.rect)
        items = self._ocr_items_from_image(crop)
        if not items:
            return None
        parser = AgentParser(self.ctx)
        data = parser.parse_ocr_result(items, crop)
        return data.get("key") if data else None

    def _parse_drive_disc_detail(self, screen: Any) -> dict[str, Any] | None:
        crop = cv2_utils.crop_image_only(screen, self.drive_disk_detail_area.rect)
        items = self._ocr_items_from_image(crop)
        if not items:
            return None
        return self._drive_parser.parse_ocr_result(items, crop)

    def _grid_click_point(self, rect: Rect, row: int, col: int, rows: int, cols: int) -> Point:
        cell_w = rect.width / cols
        cell_h = rect.height / rows
        x = int(rect.x1 + (col + 0.5) * cell_w)
        y = int(rect.y1 + (row + 0.5) * cell_h)
        return Point(x, y)

    def _scroll_drive_list_down(self, rect: Rect) -> None:
        c = rect.center
        start = Point(c.x, c.y + 160)
        end = Point(c.x, c.y - 160)
        self.ctx.controller.drag_to(start=start, end=end, duration=0.35)

    def _replace_button_text(self, screen: Any) -> str:
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            image=screen,
            rect=self.replace_btn_area.rect,
            color_range=self.replace_btn_area.color_range,
            crop_first=True,
        )
        if not ocr_result_list:
            return ""
        return str(ocr_result_list[0].data)

    def _maybe_click_material_confirm(self, screen: Any) -> None:
        if (
            find_area_in_screen(self.ctx, screen, self.material_confirm_area)
            != FindAreaResultEnum.TRUE
        ):
            return
        self.ctx.controller.click(self.material_confirm_area.rect.center)
        time.sleep(0.35)

    def _ensure_equipment_page(self) -> OperationRoundResult:
        screen = self.screenshot()
        if screen is None:
            return self.round_fail("截图失败")
        name = screen_utils.get_match_screen_name(self.ctx, screen)
        if name == "代理人-装备":
            return self.round_success("已在装备页")
        return self.round_by_goto_screen(screen_name="代理人-装备")

    def _return_to_agent_equipment_page(self) -> OperationRoundResult:
        """从代理人-装备详细回到代理人-装备。"""
        screen = self.screenshot()
        if screen is None:
            return self.round_fail("截图失败")
        name = screen_utils.get_match_screen_name(self.ctx, screen)
        if name == "代理人-装备":
            return self.round_success("已在装备页")
        if name == "代理人-装备详细":
            self.ctx.controller.click(self.detail_back_area.rect.center)
            time.sleep(0.45)
            return self.round_success("已返回装备页")
        return self.round_retry("等待返回装备页", wait=0.5)

    def _return_to_agent_info(self) -> OperationRoundResult:
        """代理人-装备 -> 代理人-列表 -> 代理人-信息。"""
        r = self._ensure_equipment_page()
        if not r.is_success:
            return r
        screen = self.screenshot()
        if screen is None:
            return self.round_fail("截图失败")
        self.ctx.controller.click(self.equipment_back_area.rect.center)
        time.sleep(0.45)
        screen = self.screenshot()
        if screen is None:
            return self.round_fail("截图失败")
        self.ctx.controller.click(self.agent_list_basic_area.rect.center)
        time.sleep(0.45)
        return self.round_success("已回到代理人信息")

    def _grid_rows_from_pipeline(self, screen: Any) -> list[list[Point]] | None:
        """drive_disk_enhance_bundle：HSV+轮廓流水线定位左侧驱动盘方格中心。"""
        pl = self.ctx.cv_service.load_pipeline(
            one_click_drive_tune_const.CV_PIPELINE_GRID
        )
        if pl is None:
            log.warning("驱动盘方格流水线加载失败")
            return None
        ctx_out = pl.execute(screen, service=self.ctx.cv_service, debug_mode=False)
        if not getattr(ctx_out, "contours", None):
            return None
        rows = contours_to_grid_centers(ctx_out.contours, self.drive_list_area.rect)
        return rows if rows else None

    def _pick_suit_from_list(self, suit_cn: str) -> OperationRoundResult:
        """套装筛选流水线 OCR + 模糊匹配 + 滚动（与 bundle 一致）。"""
        pl = self.ctx.cv_service.load_pipeline(
            one_click_drive_tune_const.CV_PIPELINE_SUIT
        )
        if pl is None:
            return self.round_fail("套装筛选流水线加载失败")
        target = [suit_cn]
        th = self.config.suit_similarity_threshold
        oy = self.config.suit_pick_offset_y
        scroll_center = self.suit_list_area.rect.center
        max_rounds = max(1, self.config.suit_pick_max_scroll_rounds)

        for _ in range(max_rounds):
            screen = self.screenshot()
            if screen is None:
                return self.round_fail("截图失败")
            ctx_out = pl.execute(screen, service=self.ctx.cv_service, debug_mode=False)
            if not ctx_out.ocr_result:
                pass
            else:
                offset_x, offset_y = ctx_out.crop_offset
                for ocr_text, match_list in ctx_out.ocr_result.items():
                    matched, _score = find_best_match_by_similarity(
                        ocr_text, target, threshold=th
                    )
                    if matched and match_list:
                        match = match_list[0]
                        rect = Rect(
                            match.rect.x1 + offset_x,
                            match.rect.y1 + offset_y,
                            match.rect.x2 + offset_x,
                            match.rect.y2 + offset_y,
                        )
                        click_pt = rect.center + Point(0, oy)
                        self.ctx.controller.click(click_pt)
                        time.sleep(0.3)
                        self.ctx.controller.click(self.suit_confirm_area.rect.center)
                        time.sleep(0.3)
                        self.ctx.controller.click(self.suit_confirm_area.rect.center)
                        time.sleep(0.45)
                        return self.round_success("已确认套装筛选")
            for _ in range(max(1, self.config.suit_scroll_repeat)):
                self.ctx.controller.scroll(1, scroll_center)
                time.sleep(0.12)

        return self.round_fail(f"未在套装列表中找到: {suit_cn}")

    def _apply_suit_filter(self, suit_cn: str) -> OperationRoundResult:
        """筛选面板：重置 → 可选 S → 套装选择 → OCR 选套装 → 双击确认。"""
        if not suit_cn:
            return self.round_success("跳过套装筛选")
        self.ctx.controller.click(self.filter_btn_area.rect.center)
        time.sleep(0.35)
        self.ctx.controller.click(self.filter_reset_area.rect.center)
        time.sleep(0.3)
        if self.config.filter_s_grade:
            self.ctx.controller.click(self.filter_s_area.rect.center)
            time.sleep(0.3)
        self.ctx.controller.click(self.filter_suit_entry_area.rect.center)
        time.sleep(0.35)
        return self._pick_suit_from_list(suit_cn)

    def _tune_one_slot(self, slot: int, agent_key: str, weight: dict[str, float]) -> OperationRoundResult:
        """
        与 drive_disk_enhance_bundle 对齐：先进入槽位详细页 → 可选套装筛选 →
        CV 轮廓网格遍历左侧列表（失败则回退固定网格）→ 评分择优 → 装备确认（不强化）。
        """
        self._load_slot_mapping()
        partition_area = self.ctx.screen_loader.get_area(
            "代理人-装备", f"分区{slot}"
        )
        self.ctx.controller.click(partition_area.rect.center)
        time.sleep(0.4)
        screen = self.screenshot()
        if screen is None:
            return self.round_fail("截图失败")

        btn_text = self._replace_button_text(screen)
        equipped = "卸下" in btn_text
        current_score = 0.0
        current_fp: tuple[Any, ...] | None = None
        if equipped:
            cur_disc = self._parse_drive_disc_detail(screen)
            if cur_disc is not None:
                current_fp = disc_fingerprint(cur_disc)
                sc = disc_relative_score(
                    self._processor, cur_disc, slot, weight, self._slot_mapping
                )
                if sc is not None:
                    current_score = sc

        suit_cn = self.config.suit_name_for_slot(slot)
        if suit_cn:
            fr = self._apply_suit_filter(suit_cn)
            if not fr.is_success:
                log.warning(
                    f"{agent_key} {slot}号位 套装筛选失败: {fr.status}，继续未筛选列表"
                )

        list_rect = self.drive_list_area.rect
        fixed_rows = max(1, self.config.grid_rows)
        fixed_cols = max(1, self.config.grid_cols)
        pages = max(1, self.config.list_max_scroll_pages)

        best_point: Point | None = None
        best_score = -1.0
        best_fp: tuple[Any, ...] | None = None

        for page in range(pages):
            screen = self.screenshot()
            if screen is None:
                return self.round_fail("截图失败")

            grid_rows: list[list[Point]] | None = None
            if self.config.use_cv_grid:
                grid_rows = self._grid_rows_from_pipeline(screen)

            if grid_rows:
                for row in grid_rows:
                    for pt in row:
                        self.ctx.controller.click(pt)
                        time.sleep(0.22)
                        screen = self.screenshot()
                        if screen is None:
                            continue
                        disc = self._parse_drive_disc_detail(screen)
                        if disc is None:
                            continue
                        if str(disc.get("slotKey", "")).strip() != str(slot):
                            continue
                        sc = disc_relative_score(
                            self._processor, disc, slot, weight, self._slot_mapping
                        )
                        if sc is None:
                            continue
                        fp = disc_fingerprint(disc)
                        if sc > best_score:
                            best_score = sc
                            best_point = pt
                            best_fp = fp
            else:
                for r in range(fixed_rows):
                    for c in range(fixed_cols):
                        pt = self._grid_click_point(
                            list_rect, r, c, fixed_rows, fixed_cols
                        )
                        self.ctx.controller.click(pt)
                        time.sleep(0.22)
                        screen = self.screenshot()
                        if screen is None:
                            continue
                        disc = self._parse_drive_disc_detail(screen)
                        if disc is None:
                            continue
                        if str(disc.get("slotKey", "")).strip() != str(slot):
                            continue
                        sc = disc_relative_score(
                            self._processor, disc, slot, weight, self._slot_mapping
                        )
                        if sc is None:
                            continue
                        fp = disc_fingerprint(disc)
                        if sc > best_score:
                            best_score = sc
                            best_point = pt
                            best_fp = fp

            if page + 1 < pages:
                self._scroll_drive_list_down(list_rect)
                time.sleep(0.32)

        gain = self.config.min_score_gain
        should_swap = (
            best_point is not None
            and best_score >= current_score + gain
            and (best_fp is None or best_fp != current_fp)
        )

        if should_swap:
            self.ctx.controller.click(best_point)
            time.sleep(0.28)
            screen = self.screenshot()
            if screen is None:
                return self.round_fail("截图失败")
            self.round_by_find_and_click_area(
                screen,
                "代理人-装备详细",
                "替换",
                success_wait=0.35,
                retry_wait=0.35,
            )
            time.sleep(0.25)
            screen = self.screenshot()
            if screen is None:
                return self.round_fail("截图失败")
            cr = self.round_by_find_and_click_area(
                screen,
                "代理人-装备详细",
                "替换-确认",
                success_wait=0.5,
                retry_wait=0.5,
            )
            if not cr.is_success:
                log.warning(f"{agent_key} {slot}号位 确认换装失败")
            time.sleep(0.35)
            screen = self.screenshot()
            if screen is not None:
                self._maybe_click_material_confirm(screen)
        else:
            self.ctx.controller.click(self.detail_back_area.rect.center)
            time.sleep(0.4)

        rr = self._return_to_agent_equipment_page()
        if not rr.is_success:
            return rr
        log.info(
            f"{agent_key} {slot}号位 调优完成 "
            f"(当前≈{current_score:.1f}, 最优≈{best_score:.1f}, 已换装={'是' if should_swap else '否'})"
        )
        return self.round_success(f"{slot}号位完成")

    def _tune_agent(self, agent_key: str) -> OperationRoundResult:
        weight = self._processor.load_character_weight(agent_key)
        if weight is None:
            log.info(f"跳过代理人 {agent_key}：无权重配置")
            return self.round_success("无权重跳过")

        r = self.round_by_goto_screen(screen_name="代理人-装备")
        if not r.is_success:
            return r
        r = self._ensure_equipment_page()
        if not r.is_success:
            return r

        for slot in range(1, 7):
            tr = self._tune_one_slot(slot, agent_key, weight)
            if not tr.is_success:
                return tr
        return self.round_success(f"代理人 {agent_key} 调优完成")

    @operation_node(name="开始前返回", is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name="开始前返回")
    @operation_node(name="前往代理人信息并开始调优")
    def tune_all_agents(self) -> OperationRoundResult:
        self._load_slot_mapping()
        self._drive_parser.disc_counter = 0

        gi = self.round_by_goto_screen(screen_name="代理人-信息")
        if not gi.is_success:
            return gi

        seen_signatures: set[bytes] = set()
        max_iterations = 120
        for iteration in range(max_iterations):
            screen = self.screenshot()
            if screen is None:
                return self.round_fail("截图失败")

            unlocked = (
                find_area_in_screen(self.ctx, screen, self.agent_unlocked_area)
                == FindAreaResultEnum.TRUE
            )
            if not unlocked:
                log.info("当前代理人未解锁，结束调优")
                break

            sig = cv2_utils.crop_image_only(
                screen, self.agent_name_area.rect
            ).tobytes()
            if sig in seen_signatures:
                log.info("代理人列表已遍历一圈，结束调优")
                break
            seen_signatures.add(sig)

            agent_key = self._read_agent_key(screen)
            if not agent_key:
                log.warning("未能识别代理人名称，跳过")
            else:
                ur = self._tune_agent(agent_key)
                if not ur.is_success:
                    return ur

            ri = self._return_to_agent_info()
            if not ri.is_success:
                return ri

            self.ctx.controller.click(self.switch_next_agent_area.rect.center)
            time.sleep(0.35)

        return self.round_success("一键调优完成")


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.init_ocr()
    ctx.run_context.start_running()
    OneClickDriveTuneApp(ctx).execute()


if __name__ == "__main__":
    __debug()
