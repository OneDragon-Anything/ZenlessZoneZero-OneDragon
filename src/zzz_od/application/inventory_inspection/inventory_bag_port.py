"""Native OneDragon inventory port; production calibration is separately gated.

Reuse existing screenshot/OCR/controller/screen route primitives, but do not
execute GotoMenu/BackToNormalWorld/OpenAndEnterGame or initialise/download OCR.
Only the verified ordinary-world -> menu -> warehouse route is allowed.
"""

import hashlib
import time
import unicodedata
from math import isfinite
from typing import Any

from zzz_od.application.inventory_support import inventory_scrollbar as scrollbar

WORLD, MENU, WENGINE, MATERIAL = (
    '大世界-普通',
    '菜单',
    '仓库-音擎仓库',
    '仓库-材料道具',
)
SCREENS = [WORLD, MENU, WENGINE, MATERIAL]
SAFE_EDGES = {(WORLD, '按钮-菜单', MENU), (MENU, '底部-仓库', WENGINE)}


def safe_route(route: Any, current: Any, target: Any = WENGINE) -> Any:
    nodes = getattr(route, 'node_list', None)
    if (
        not getattr(route, 'can_go', False)
        or not isinstance(nodes, list)
        or (not 1 <= len(nodes) <= 4)
    ):
        return False
    previous = current
    for node in nodes:
        edge = (
            getattr(node, 'from_screen', None),
            getattr(node, 'from_area', None),
            getattr(node, 'to_screen', None),
        )
        if edge not in SAFE_EDGES or edge[0] != previous:
            return False
        previous = edge[2]
    return previous == target


def exact_token(matches: Any) -> Any:
    if not isinstance(matches, list) or len(matches) != 1:
        return None
    match = matches[0]
    text, confidence = (
        getattr(match, 'data', None),
        getattr(match, 'confidence', None),
    )
    if (
        not isinstance(text, str)
        or not text.strip()
        or isinstance(confidence, bool)
        or (not isinstance(confidence, (float, int)))
        or (not isfinite(confidence))
        or (not 0.9 <= confidence <= 1)
    ):
        return None
    return {'text': text, 'confidence': confidence}


def compact(value: Any) -> Any:
    return ''.join(unicodedata.normalize('NFKC', value).split())


def same_viewport(left: Any, right: Any) -> Any:
    return all((abs(a - b) <= 1 for a, b in zip(left, right, strict=True)))


def point(x: Any, y: Any) -> Any:
    from one_dragon.base.geometry.point import Point

    return Point(x, y)


class NativeBagPort:
    def __init__(
        self,
        operation: Any,
        guard: Any,
        *,
        pause: Any = time.sleep,
        point_factory: Any = point,
        event: Any = lambda *args: None,
    ) -> None:
        if not callable(event):
            raise ValueError('Native inventory diagnostic sink must be callable')
        self.op, self.guard = (operation, guard)
        self.pause, self.point = (pause, point_factory)
        self.event = event
        self.scrollbar = None
        self.selected_thumb = None
        self.selection_policy = None

    def configure_scrollbar(self, value: Any) -> Any:
        self.scrollbar = scrollbar.validate(value)

    def configure_scroll_mode(self, value: Any) -> Any:
        if value != 'native_grid_wheel':
            raise ValueError('Only natively calibrated grid wheel is supported')

    def configure_selection_policy(self, value: Any) -> Any:
        if value != 'interior_rows_with_endpoint_edges' or self.scrollbar is None:
            raise ValueError(
                'Native endpoint-aware grid policy requires a calibrated scrollbar'
            )
        self.selection_policy = value

    def viewport_cells(self, cells: Any) -> Any:
        if self.selection_policy != 'interior_rows_with_endpoint_edges':
            raise ValueError('Native viewport selection policy not configured')
        rows = sorted({cell[1] for cell in cells})
        if len(rows) != 4:
            raise ValueError('Endpoint-aware grid requires four calibrated rows')
        thumb = self._thumb()
        top = scrollbar.at_top(thumb, self.scrollbar)
        bottom = thumb[1] >= self.scrollbar['roi'][3] - 5
        selected = [
            cell
            for cell in cells
            if cell[1] in rows[1:-1]
            or (top and cell[1] == rows[0])
            or (bottom and cell[1] == rows[-1])
        ]
        self.event(
            'native_viewport_cells',
            {
                'thumb': list(thumb),
                'top': top,
                'bottom': bottom,
                'rows': sorted({cell[1] for cell in selected}),
            },
        )
        return selected

    def _thumb(self) -> Any:
        if self.scrollbar is None:
            raise ValueError('Native scrollbar not configured')
        frame = self._frame()
        x, y, w, h = self.scrollbar['roi']
        import cv2

        image = cv2.resize(frame, (1920, 1080))
        return scrollbar.thumb(image[y : y + h, x : x + w], self.scrollbar)

    def at_top(self) -> Any:
        return scrollbar.at_top(self._thumb(), self.scrollbar)

    def _settle_scroll(self, before: Any, direction: Any) -> Any:
        previous, stable = (None, 0)
        endpoint = (
            scrollbar.at_top(before, self.scrollbar)
            if direction < 0
            else before[1] >= self.scrollbar['roi'][3] - 5
        )
        for _ in range(12):
            current = self._thumb()
            if abs(current[1] - current[0] - (before[1] - before[0])) > 2:
                raise RuntimeError('Native scrollbar span changed during scroll')
            stable = stable + 1 if current == previous else 0
            progressed = (
                current[0] < before[0] if direction < 0 else current[0] > before[0]
            )
            same_endpoint = endpoint and current == before
            if stable >= 2 and (progressed or same_endpoint):
                return current
            previous = current
            self.pause(0.15)
        raise RuntimeError(
            'Native scrollbar did not settle within bounded observations'
        )

    def _frame(self) -> Any:
        self.guard()
        frame = self.op.screenshot()
        if (
            frame is None
            or len(frame.shape) != 3
            or frame.shape[2] != 3
            or (frame.shape[0] <= 0)
            or (abs(frame.shape[1] / frame.shape[0] - 16 / 9) > 0.01)
        ):
            raise RuntimeError(
                'Native OneDragon bag frame missing or changed aspect ratio'
            )
        self.guard()
        return frame

    def _screen(self, frame: Any) -> Any:
        self.guard()
        name = self.op.check_and_update_current_screen(
            screen=frame, screen_name_list=SCREENS
        )
        self.guard()
        return name if name in SCREENS else None

    def _matches(self, roi: Any, frame: Any) -> Any:
        if (
            not isinstance(roi, list)
            or len(roi) != 4
            or any(type(n) is not int for n in roi)
        ):
            raise ValueError('Expected calibrated native ROI')
        x, y, w, h = roi
        if x < 0 or y < 0 or w <= 0 or (h <= 0) or (x + w > 1920) or (y + h > 1080):
            raise ValueError('OCR crop outside calibrated frame')
        height, width = frame.shape[:2]
        crop = frame[
            round(y * height / 1080) : round((y + h) * height / 1080),
            round(x * width / 1920) : round((x + w) * width / 1920),
        ]
        self.guard()
        value = self.op.ctx.ocr.ocr(crop, threshold=0.9)
        self.guard()
        return (value, crop.shape[1], crop.shape[0])

    def _read(self, roi: Any, frame: Any) -> Any:
        return exact_token(self._matches(roi, frame)[0])

    def _warehouse_cell(self, roi: Any, frame: Any) -> Any:
        matches, width, height = self._matches(roi, frame)
        if not isinstance(matches, list):
            return None
        selected = [
            row
            for row in matches
            if isinstance(getattr(row, 'data', None), str)
            and compact(row.data) == '仓库'
        ]
        if exact_token(selected) is None:
            return None
        center = getattr(selected[0], 'center', None)
        if center is None:
            return None
        cx, cy = (getattr(center, 'x', None), getattr(center, 'y', None))
        if any(
            isinstance(n, bool) or not isinstance(n, (float, int)) or (not isfinite(n))
            for n in (cx, cy)
        ):
            return None
        if not 0 <= cx < width or not 0 <= cy < height:
            return None
        x, y, w, h = roi
        return [
            min(x + w - 1, round(x + cx * w / width)),
            min(y + h - 1, round(y + cy * h / height)),
        ]

    def bag_open(self) -> Any:
        return self._screen(self._frame()) in (WENGINE, MATERIAL)

    def _wait_after_route_action(self, previous: Any, target: Any) -> Any:
        for attempt in range(12):
            current = self._screen(self._frame())
            if current == target or (target == WENGINE and current == MATERIAL):
                return True
            if current is not None and current != previous:
                return False
            if attempt != 11:
                self.pause(0.2)
        return False

    def open_bag(self) -> Any:
        for _ in range(6):
            frame = self._frame()
            current = self._screen(frame)
            if current in (WENGINE, MATERIAL):
                return True
            if current not in (WORLD, MENU):
                return False
            route = self.op.ctx.screen_loader.get_screen_route(current, WENGINE)
            if not safe_route(route, current):
                return False
            first = route.node_list[0]
            if current == MENU:
                area = self.op.ctx.screen_loader.get_area(MENU, first.from_area)
                rect = getattr(area, 'rect', None)
                if rect is None:
                    return False
                cell = self._warehouse_cell(
                    [rect.x1, rect.y1, rect.x2 - rect.x1, rect.y2 - rect.y1], frame
                )
                if cell is None:
                    return False
                self.click_cell(cell)
            else:
                self.guard()
                result = self.op.round_by_find_and_click_area(
                    frame, current, first.from_area
                )
                self.guard()
                if not getattr(result, 'is_success', False):
                    return False
            if not self._wait_after_route_action(current, first.to_screen):
                return False
        return False

    def page_verified(self, page: Any) -> Any:
        for index in range(2):
            frame = self._frame()
            current = self._screen(frame)
            if current != MATERIAL and (
                not (current is None and self._currency_overlay(page, frame))
            ):
                if self._is_denny_candidate(page):
                    self._currency_rejection('page_screen', current, page, frame, index)
                return False
            anchor = page['page_anchor']
            value = self._read(anchor['roi'], frame)
            if value is None or compact(value['text']) != compact(anchor['text']):
                if self._is_denny_candidate(page):
                    self.event(
                        'currency_verification_rejected',
                        {
                            'stage': 'page_anchor',
                            'screen': current,
                            'frame_index': index,
                            'anchor_exact': False,
                            'quantity_accepted': False,
                        },
                    )
                return False
            if index == 0:
                self.pause(0.15)
        return True

    def _currency_overlay(self, page: Any, frame: Any) -> Any:
        """Positive candidate-only popup identity, not an unknown-screen bypass.

        Native warehouse templates are obscured by the tooltip. Require its
        title plus two independent exact labels in separate calibrated crops.
        Quantity acceptance still belongs to the two-frame passive collector.
        """
        identity = page.get('currency_overlay_identity')
        if not self._is_denny_candidate(page) or not isinstance(identity, dict):
            return False
        if (
            identity.get('schema') != 'zzz-denny-overlay/v1'
            or set(identity) != {'schema', 'native_evidence', 'anchors'}
            or (not isinstance(identity.get('native_evidence'), str))
            or (not identity['native_evidence'])
        ):
            return False
        anchors = identity.get('anchors')
        if (
            not isinstance(anchors, list)
            or len(anchors) != 2
            or [a.get('text') for a in anchors if isinstance(a, dict)]
            != ['当前拥有', 'CURRENCY']
        ):
            return False
        regions = [page['page_anchor']['roi']]
        for anchor in anchors:
            if set(anchor) != {'text', 'roi'}:
                return False
            roi = anchor['roi']
            if (
                not isinstance(roi, list)
                or len(roi) != 4
                or any(type(n) is not int for n in roi)
            ):
                return False
            x, y, w, h = roi
            if x < 0 or y < 0 or w <= 0 or (h <= 0) or (x + w > 1920) or (y + h > 1080):
                return False
            for px, py, pw, ph in regions:
                if x < px + pw and px < x + w and (y < py + ph) and (py < y + h):
                    return False
            regions.append(roi)
        for anchor in [page['page_anchor']] + anchors:
            token = self._read(anchor['roi'], frame)
            if token is None or compact(token['text']) != anchor['text']:
                return False
        return True

    @staticmethod
    def _is_denny_candidate(page: Any) -> Any:
        return (
            page.get('game') == 'zzz'
            and page.get('candidate_only') is True
            and (page.get('page_anchor', {}).get('text') == '丁尼')
            and (len(page.get('materials', [])) == 1)
            and (page['materials'][0].get('id') == 'denny')
            and (page['materials'][0].get('category') == 'currency')
        )

    def _currency_rejection(
        self, stage: Any, current: Any, page: Any, frame: Any, frame_index: Any = None
    ) -> Any:
        token = self._read(page['page_anchor']['roi'], frame)
        self.event(
            'currency_verification_rejected',
            {
                'stage': stage,
                'screen': current if current in SCREENS else None,
                'frame_index': frame_index,
                'anchor_exact': token is not None and compact(token['text']) == '丁尼',
                'quantity_accepted': False,
            },
        )

    def select_tab(self, page: Any, tab_roi: Any) -> Any:
        if self.page_verified(page):
            return True
        if not self.bag_open():
            return False
        self.scrollbar = None
        self.selected_thumb = None
        self.selection_policy = None
        x, y, w, h = tab_roi
        self.click_cell([round(x + w / 2), round(y + h / 2)])
        for attempt in range(12):
            if self.page_verified(page):
                return True
            current = self._screen(self._frame())
            if current not in (None, WENGINE, MATERIAL):
                return False
            if attempt != 11:
                self.pause(0.2)
        return False

    def open_currency_popup(self, page: Any, route: Any) -> Any:
        """Candidate-only Denny tooltip; one click, bounded fresh verification."""
        from zzz_od.application.inventory_support import (
            inventory_native_navigation as navigation,
        )

        navigation.currency_popup_route(page, route)
        if page['game'] != 'zzz':
            raise ValueError('OneDragon currency route must bind ZZZ Denny')
        self.scrollbar = self.selected_thumb = self.selection_policy = None

        def detail_verified() -> Any:
            token = self.read_detail(page['materials'][0]['label_roi'])
            return (
                token is not None
                and compact(token['text']) == '丁尼'
                and self.page_verified(page)
            )

        def verified() -> Any:
            return self.page_verified(page) and detail_verified()

        if self.page_verified(page):
            return detail_verified()
        if not self.bag_open() and (not self.open_bag()):
            return False
        base = {'page_anchor': route['base_page_anchor']}
        if not self.select_tab(base, route['base_tab_roi']) or not self.page_verified(
            base
        ):
            return False
        x, y, w, h = route['open_roi']
        if self._screen(self._frame()) != MATERIAL:
            return False
        self.click_cell([round(x + w / 2), round(y + h / 2)])
        for attempt in range(12):
            frame = self._frame()
            current = self._screen(frame)
            if current != MATERIAL:
                self._currency_rejection(
                    'post_click_screen', current, page, frame, attempt
                )
                if current is not None or 'currency_overlay_identity' not in page:
                    return False
            if verified():
                return True
            if attempt != 11:
                self.pause(0.2)
        return False

    def close_currency_popup(self, page: Any, route: Any) -> Any:
        """Dismiss only the reviewed Denny tooltip; never send repeated Escape."""
        from zzz_od.application.inventory_support import (
            inventory_native_navigation as navigation,
        )

        navigation.currency_popup_route(page, route)
        if page['game'] != 'zzz':
            raise ValueError('OneDragon currency cleanup must bind ZZZ Denny')
        if not self.page_verified(page):
            return False
        self.guard()
        self.op.ctx.controller.keyboard_controller.press('esc', press_time=0.1)
        base = {'page_anchor': route['base_page_anchor']}
        for _attempt in range(12):
            self.pause(0.2)
            if self.page_verified(base) and (not self.page_verified(page)):
                self.event('native_currency_popup_closed', {'currency': 'denny'})
                return True
            current = self._screen(self._frame())
            if current not in (None, MATERIAL):
                return False
        return False

    def click_cell(self, cell: Any) -> Any:
        if (
            not isinstance(cell, list)
            or len(cell) != 2
            or any(type(n) is not int for n in cell)
            or (not 0 <= cell[0] < 1920)
            or (not 0 <= cell[1] < 1080)
        ):
            raise ValueError('Cell outside native controller coordinates')
        self.guard()
        before = self._thumb() if self.scrollbar is not None else None
        self.selected_thumb = before
        target = self.point(*cell)
        if before is not None:
            self.op.ctx.controller.mouse_move(target)
            self.pause(0.15)
            positioned = self._thumb()
            self.event(
                'native_selection_positioned',
                {
                    'cell': list(cell),
                    'before': list(before),
                    'positioned': list(positioned),
                },
            )
            if not same_viewport(positioned, before):
                raise RuntimeError(
                    'Native inventory viewport moved before selection; no click'
                )
            self.guard()
            clicked = self.op.ctx.controller.click(target, press_time=0.1)
        else:
            clicked = self.op.ctx.controller.click(target)
        if clicked is not True:
            raise RuntimeError('Native OneDragon inventory selection refused')
        self.pause(0.15)
        self._frame()
        if before is not None:
            after = self._thumb()
            self.event(
                'native_selection_viewport',
                {
                    'cell': list(cell),
                    'before': list(before),
                    'after': list(after),
                    'moved_during_selection': not same_viewport(after, before),
                    'raster_tolerance_pixels': 1,
                },
            )
            if self.selection_policy is not None and (not same_viewport(after, before)):
                raise RuntimeError(
                    'Native viewport moved during interior selection; stop stale cells'
                )

    def _detail_viewport(self) -> Any:
        if self.selected_thumb is not None:
            current = self._thumb()
            self.event(
                'native_detail_viewport',
                {
                    'selection_before': list(self.selected_thumb),
                    'after': list(current),
                    'moved_since_selection': not same_viewport(
                        current, self.selected_thumb
                    ),
                    'raster_tolerance_pixels': 1,
                },
            )
            if self.selection_policy is not None and (
                not same_viewport(current, self.selected_thumb)
            ):
                raise RuntimeError(
                    'Native viewport moved after interior selection; stop stale cells'
                )

    def read_detail(self, roi: Any) -> Any:
        previous = None
        for attempt in range(8):
            current = self._read(roi, self._frame())
            if (
                current is not None
                and previous is not None
                and (compact(current['text']) == compact(previous['text']))
            ):
                self._detail_viewport()
                return {
                    'text': current['text'],
                    'confidence': min(current['confidence'], previous['confidence']),
                }
            previous = current
            if attempt != 7:
                self.pause(0.15)
        self._detail_viewport()
        return None

    def grid_signature(self, roi: Any) -> Any:
        if self.scrollbar is not None:
            return scrollbar.signature(self._thumb())
        frame = self._frame()
        x, y, w, h = roi
        height, width = frame.shape[:2]
        crop = frame[
            round(y * height / 1080) : round((y + h) * height / 1080),
            round(x * width / 1920) : round((x + w) * width / 1920),
        ]
        if crop.size == 0:
            raise RuntimeError('Native OneDragon grid crop empty')
        return hashlib.sha256(crop.tobytes()).hexdigest()

    def scroll_grid(self, roi: Any, notches: Any) -> Any:
        x, y, w, h = roi
        self.guard()
        before = self._thumb() if self.scrollbar is not None else None
        started = time.monotonic()
        if before is not None:
            self.event(
                'native_scroll_requested', {'notches': notches, 'before': list(before)}
            )
        self.op.ctx.controller.scroll(
            notches, self.point(round(x + w / 2), round(y + h / 2))
        )
        self.pause(0.35)
        if self.scrollbar is not None:
            try:
                after = self._settle_scroll(before, -1 if notches < 0 else 1)
            except Exception as exc:
                self.event(
                    'native_scroll_unsettled',
                    {
                        'notches': notches,
                        'before': list(before),
                        'elapsed_seconds': round(time.monotonic() - started, 3),
                        'error_type': type(exc).__name__,
                    },
                )
                raise
            self.event(
                'native_scroll_settled',
                {
                    'notches': notches,
                    'before': list(before),
                    'after': list(after),
                    'moved': after != before,
                    'elapsed_seconds': round(time.monotonic() - started, 3),
                },
            )
        else:
            self._frame()
