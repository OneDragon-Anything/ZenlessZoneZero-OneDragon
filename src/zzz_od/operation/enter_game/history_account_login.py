"""官服历史账号登录；不输入密码，不处理人工验证。"""

import re
import time
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, os_utils
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.matcher.ocr.ocr_matcher import OcrMatcher
    from zzz_od.context.zzz_context import ZContext


def normalize_phone_number(text: str) -> str | None:
    """整理真实手机号的显示格式，格式无效时返回空值，不纠正数字。"""
    phone = re.sub(r'[\s\-‐‑–—]', '', unicodedata.normalize('NFKC', text))
    if phone.startswith('+86'):
        phone = phone[3:]
    return phone if re.fullmatch(r'1[3-9][0-9]{9}', phone) else None


def normalize_phone_label(text: str) -> str | None:
    """提取完整或脱敏手机号；遮挡符号归一，不猜测被遮挡的数字。"""
    value = re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))
    value = re.sub(r'[*•·●×✱∗﹡]+', '*', value)
    if re.fullmatch(r'1[3-9][0-9]{9}', value):
        return value
    match = re.fullmatch(r'(1[3-9][0-9]{1,7})\*([0-9]{2,7})', value)
    if match is not None and len(match[1]) + len(match[2]) < 11:
        return value
    return None


def phone_label_matches(label: str, phone: str) -> bool:
    """完整号码全等；脱敏号码的所有可见前后数字必须对应真实号码。"""
    if '*' not in label:
        return label == phone
    prefix, suffix = label.split('*')
    return phone.startswith(prefix) and phone.endswith(suffix)


def phone_labels_agree(first: str, second: str) -> bool:
    """比较两次 OCR 的可见数字是否矛盾，避免放大后误读数字而选错账号。"""
    if '*' not in first:
        return phone_label_matches(second, first)
    if '*' not in second:
        return phone_label_matches(first, second)
    prefix_a, suffix_a = first.split('*')
    prefix_b, suffix_b = second.split('*')
    return ((prefix_a.startswith(prefix_b) or prefix_b.startswith(prefix_a))
            and (suffix_a.endswith(suffix_b) or suffix_b.endswith(suffix_a)))


@dataclass
class PhoneCandidate:
    """一行完整识别的手机号文字及其游戏坐标。"""

    label: str
    center: Point


@dataclass
class PhoneReadResult:
    """手机号行识别结果；存在无法可靠识别的号码行时标为不清晰。"""

    candidates: list[PhoneCandidate]
    unreadable: bool


def read_phone_candidates(
    ocr: 'OcrMatcher', screen: MatLike, rect: tuple[int, int, int, int], scale: int = 1,
) -> PhoneReadResult:
    """按同一行的几何位置合并 OCR 碎片，排除下一行时间文字，并还原游戏坐标。"""
    x1, y1, x2, y2 = rect
    image = screen[y1:y2, x1:x2]
    if scale != 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    result = ocr.run_ocr(image)
    fragments: list[tuple[str, float, float, float, float]] = []
    for text, matches in result.items():
        for match in matches:
            fragments.append((text, match.x / scale, match.y / scale,
                              match.w / scale, match.h / scale))
    rows: list[list[tuple[str, float, float, float, float]]] = []
    for fragment in sorted(fragments, key=lambda item: (item[2] + item[4] / 2, item[1])):
        cy = fragment[2] + fragment[4] / 2
        row = next((items for items in rows
                    if abs(cy - (items[0][2] + items[0][4] / 2)) <= 12), None)
        if row is None:
            rows.append([fragment])
        else:
            row.append(fragment)
    candidates: list[PhoneCandidate] = []
    unreadable = False
    for row in rows:
        text = ''.join(item[0] for item in sorted(row, key=lambda item: item[1]))
        if re.fullmatch(r'\s*(?:刚刚|[0-9０-９]+\s*(?:秒|分钟|小时|天|周|个月|月|年)前)\s*', text):
            continue
        label = normalize_phone_label(text)
        if label is None:
            # 没有形成完整号码的数字或遮挡符号需要重读，不猜测缺失部分。
            if re.search(r'[0-9０-９]{3}|[*＊•·●×✱∗﹡]', text):
                unreadable = True
            continue
        left = min(item[1] for item in row)
        right = max(item[1] + item[3] for item in row)
        top = min(item[2] for item in row)
        bottom = max(item[2] + item[4] for item in row)
        candidates.append(PhoneCandidate(label, Point(x1 + (left + right) / 2, y1 + (top + bottom) / 2)))
    return PhoneReadResult(candidates, unreadable or not candidates)


def normalize_login_text(text: str) -> str:
    """界面文字只统一空白、冒号及登录异体写法，不使用子序列相似度。"""
    return re.sub(r'[\s:：]', '', unicodedata.normalize('NFKC', text)).replace('登陆', '登录')


def has_exact_login_text(ctx: 'ZContext', screen: MatLike, area_name: str) -> bool:
    """复用现有区域，要求完整文字一致，避免警告长句误命中短按钮。"""
    area = ctx.screen_loader.get_area('打开游戏', area_name)
    if area is None or not area.is_text_area:
        return False
    target = normalize_login_text(area.text)
    rect = area.rect
    if area_name in ('退出登录-保留登录记录', '退出登录-清除登录记录'):
        # 原区域贴紧文字会截断笔画；余量来自用户提供的退出弹窗截图。
        rect = Rect(max(0, rect.x1 - 8), max(0, rect.y1 - 8),
                    min(screen.shape[1], rect.x2 + 12), min(screen.shape[0], rect.y2 + 8))
    results = ctx.ocr_service.get_ocr_result_list(
        image=screen, rect=rect, color_range=area.color_range, crop_first=True,
    )
    return any(normalize_login_text(result.data) == target for result in results)


def is_startup_warning(ctx: 'ZContext', screen: MatLike) -> bool:
    """按警告页文档及失败截图的标题位置识别纯展示页。"""
    results = ctx.ocr_service.get_ocr_result_list(
        image=screen, rect=Rect(800, 350, 1120, 430), crop_first=True,
    )
    return any(normalize_login_text(result.data) == '警告游戏前详阅' for result in results)


class CnEntryPhase(Enum):
    """同样显示进入游戏文字时，仍需区分加载前后的页面。"""

    UNKNOWN = '等待可识别的登录界面'
    SERVER_SELECTION = '等待服务器选择页自动完成登录'
    LOADING = '等待加载配置完成'
    RESOURCE_DOWNLOAD = '资源下载中'
    READY = '登录页已就绪，可以切换账号'


def classify_cn_entry_phase(ctx: 'ZContext', screen: MatLike) -> CnEntryPhase:
    """用现有 OCR 区域及资源检测图标区分用户截图 3、4、5。"""
    area = ctx.screen_loader.get_area('打开游戏', '进入游戏点击后状态')
    results = ctx.ocr_service.get_ocr_result_list(image=screen, rect=area.rect, crop_first=True)
    texts = {normalize_login_text(result.data) for result in results}
    if any(text.startswith('资源下载中') for text in texts):
        return CnEntryPhase.RESOURCE_DOWNLOAD
    if any(text.startswith(('加载配置数据中', '版本校对中', '登录游戏服务器中')) for text in texts):
        return CnEntryPhase.LOADING
    # 图 3 有服务器文字，即使右下角切换模板也能匹配，仍然不能切号。
    if '新艾利都' in texts:
        return CnEntryPhase.SERVER_SELECTION
    if '点击进入游戏' not in texts:
        return CnEntryPhase.UNKNOWN
    for name in ('资源检测', '切换账号'):
        icon = ctx.screen_loader.get_area('打开游戏', name)
        matches = ctx.tm.crop_and_match_template(
            screen, icon.rect, icon.template_sub_dir, icon.template_id,
            threshold=icon.template_match_threshold,
        )
        if matches.max is None:
            return CnEntryPhase.UNKNOWN
    return CnEntryPhase.READY


def radio_inner_green_ratio(ctx: 'ZContext', screen: MatLike, area_name: str) -> float:
    """只读取单选框内部，排除选中和未选中状态共有的绿色外圈。"""
    rect = ctx.screen_loader.get_area('打开游戏', area_name).rect
    cx, cy = rect.x1 - 31, (rect.y1 + rect.y2) // 2
    crop = screen[cy - 8:cy + 9, cx - 8:cx + 9]
    if crop.shape[:2] != (17, 17):
        return 0.0
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, np.array([35, 90, 90]), np.array([90, 255, 255]))
    yy, xx = np.ogrid[-8:9, -8:9]
    inner = xx * xx + yy * yy <= 64
    return float(np.count_nonzero(mask[inner]) / np.count_nonzero(inner))


def is_history_login_window(op: Operation, screen: MatLike) -> bool:
    """历史登录入口需要完整退出标题或已有下拉箭头模板。"""
    if has_exact_login_text(op.ctx, screen, '标题-退出登录'):
        return True
    return any(
        op.round_by_find_area(screen, '打开游戏', name).is_success
        for name in ('账号下拉-点击展开', '账号下拉-点击收起')
    )


def save_history_login_diagnostic(screen: MatLike | None, prefix: str) -> None:
    """只保存本机失败画面，使用兼容中文路径的图片写入接口。"""
    if screen is None:
        return
    try:
        path = Path(os_utils.get_path_under_work_dir('.debug', 'images')) / f'{prefix}_{time.time_ns()}.png'
        cv2_utils.save_image(screen, str(path))
        if path.is_file():
            log.warning('历史登录失败画面已保存在本机：%s', path)
        else:
            log.warning('历史登录失败画面保存失败')
    except Exception:
        log.warning('历史登录失败画面保存失败', exc_info=True)


class HistoryAccountLogin(Operation):
    """复用登录页模板，有限重试后将异常交给用户。"""

    def __init__(self, ctx: 'ZContext') -> None:
        super().__init__(ctx=ctx, op_name='官服历史账号登录', timeout_seconds=60)
        self.ctx: ZContext = ctx
        self.selected: bool = False
        self.preserve_clicked: bool = False
        self.logout_confirmed: bool = False
        self.scroll_count: int = 0
        self.previous_page: tuple[str, ...] | None = None
        self.page_read_attempts: int = 0
        self.saw_unreadable_page: bool = False
        self.confirmation_frames: int = 0
        self.confirmation_read_attempts: int = 0

    def _present(self, screen: MatLike, name: str) -> bool:
        area = self.ctx.screen_loader.get_area('打开游戏', name)
        if area is not None and area.is_text_area:
            return has_exact_login_text(self.ctx, screen, name)
        return self.round_by_find_area(screen, '打开游戏', name).is_success

    def _click_present_area(self, screen: MatLike, name: str) -> OperationRoundResult:
        """先严格确认文字或模板，再点击已配置区域，避免回到模糊文字点击。"""
        if not self._present(screen, name):
            return self.round_retry(f'未识别到{name}')
        return self.round_by_click_area('打开游戏', name)

    def _read_accounts(
        self, screen: MatLike, rect: tuple[int, int, int, int], phone: str,
    ) -> PhoneReadResult:
        """优先读原图；匹配不可靠时放大重读，两次可见数字矛盾则等待新截图。"""
        original = read_phone_candidates(self.ctx.ocr, screen, rect)
        matches = [item for item in original.candidates if phone_label_matches(item.label, phone)]
        if len(matches) > 1 or len(matches) == 1 and not original.unreadable:
            return original
        enlarged = read_phone_candidates(self.ctx.ocr, screen, rect, scale=2)
        for first in original.candidates:
            for second in enlarged.candidates:
                if abs(first.center.y - second.center.y) <= 12 and not phone_labels_agree(first.label, second.label):
                    return PhoneReadResult(enlarged.candidates, unreadable=True)
        if not enlarged.unreadable:
            return enlarged
        return original if not original.unreadable else enlarged

    def _preserved(self, screen: MatLike) -> bool:
        """确认保留项勾选且清除项未勾选，才允许提交退出。"""
        return (radio_inner_green_ratio(self.ctx, screen, '退出登录-保留登录记录') >= 0.15
                and radio_inner_green_ratio(self.ctx, screen, '退出登录-清除登录记录') < 0.05)

    @operation_node(name='选择历史账号', is_start_node=True, node_max_retry_times=12)
    def select_account(self) -> OperationRoundResult:
        screen = self.last_screenshot
        if screen is None:
            self.confirmation_frames = 0
            return self.round_retry('等待登录截图', wait=1)
        if is_startup_warning(self.ctx, screen):
            self.confirmation_frames = 0
            return self.round_retry('等待游戏启动警告页结束', wait=1)
        phone = normalize_phone_number(self.ctx.game_account_config.account)
        if phone is None:
            return self.round_fail('请在账号栏填写真实的中国大陆 11 位手机号，支持 +86 前缀')

        if self._present(screen, '标题-退出登录'):
            self.confirmation_frames = 0
            if self.logout_confirmed:
                return self.round_retry('已确认退出，等待账号列表出现', wait=1)
            if not self._present(screen, '退出登录-保留登录记录'):
                return self.round_retry('未找到保留登录记录选项', wait=1)
            if not self._preserved(screen) and not self.preserve_clicked:
                result = self._click_present_area(screen, '退出登录-保留登录记录')
                if result.is_success:
                    self.preserve_clicked = True
                    return self.round_wait('已选择保留登录记录', wait=1)
                return self.round_retry('未找到保留登录记录选项', wait=1)
            if not self._preserved(screen):
                return self.round_retry('无法确认保留登录记录的选中状态', wait=1)
            result = self._click_present_area(screen, '按钮-退出登录-确定')
            if result.is_success:
                self.logout_confirmed = True
                return self.round_wait('已确认保留记录，等待账号列表', wait=1)
            return self.round_retry('等待退出登录确认按钮', wait=1)

        expanded = self._present(screen, '账号下拉-点击收起')
        collapsed = self._present(screen, '账号下拉-点击展开')
        if self.selected and collapsed:
            result = self._read_accounts(screen, (720, 470, 1180, 540), phone)
            matches = [item for item in result.candidates if phone_label_matches(item.label, phone)]
            if len(matches) > 1:
                return self.round_fail('账号确认不一致或不唯一，已停止')
            if result.unreadable:
                self.confirmation_frames = 0
                self.confirmation_read_attempts += 1
                if self.confirmation_read_attempts >= 3:
                    return self.round_fail('选中后的手机号识别不清，已停止')
                return self.round_wait('重新识别选中的手机号', wait=1)
            if len(matches) != 1:
                self.confirmation_frames = 0
                return self.round_fail('选中后的手机号与配置不一致，已停止')
            self.confirmation_read_attempts = 0
            self.confirmation_frames += 1
            if self.confirmation_frames < 2:
                return self.round_wait('手机号首次核对一致，等待下一帧确认', wait=1)
            click_result = self._click_present_area(screen, '账号确认-进入游戏')
            if click_result.is_success:
                return self.round_success(wait=2)
            return self.round_retry('等待账号确认按钮', wait=1)
        if self.selected:
            self.confirmation_frames = 0
            return self.round_retry('等待账号列表收起后核对手机号', wait=1)
        if collapsed:
            result = self._click_present_area(screen, '账号下拉-点击展开')
            if result.is_success:
                return self.round_wait('已展开历史账号', wait=1)
            return self.round_retry('等待历史账号下拉按钮', wait=1)
        if expanded:
            # 按展开列表实拍裁剪账号文字，避开左侧手机图标、右侧删除按钮及底部其他账号入口。
            result = self._read_accounts(screen, (720, 565, 1180, 825), phone)
            matches = [item for item in result.candidates if phone_label_matches(item.label, phone)]
            if len(matches) > 1:
                return self.round_fail('历史列表有多个账号符合该手机号的脱敏显示，已停止')
            if matches and not result.unreadable:
                if not self.ctx.controller.click(matches[0].center):
                    return self.round_retry('点击历史账号失败', wait=1)
                self.selected = True
                return self.round_wait('核对选中的账号', wait=1)
            self.page_read_attempts += 1
            if self.page_read_attempts < 3:
                return self.round_wait('重新截图识别历史手机号列表', wait=1)
            self.saw_unreadable_page = self.saw_unreadable_page or result.unreadable
            page = tuple(item.label for item in result.candidates)
            if self.scroll_count >= 6 or not result.unreadable and page == self.previous_page:
                if self.saw_unreadable_page:
                    return self.round_fail('历史列表手机号识别不清，请检查画面是否完整清晰')
                return self.round_fail('历史列表未找到符合该手机号的账号，请检查账号及游戏登录记录')
            self.previous_page = page if not result.unreadable else None
            self.page_read_attempts = 0
            self.scroll_count += 1
            self.ctx.controller.scroll(3, pos=Point(1100, 600))
            return self.round_wait('查找下一页历史账号', wait=1)

        return self.round_retry('未识别到账号选择界面，等待画面稳定', wait=1)

    def after_operation_done(self, result: OperationResult) -> None:
        super().after_operation_done(result)
        if not result.success:
            save_history_login_diagnostic(self.last_screenshot, 'history_account_failure')
