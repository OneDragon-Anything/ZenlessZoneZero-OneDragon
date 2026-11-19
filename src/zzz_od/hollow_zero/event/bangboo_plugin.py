import time
from enum import Enum
from typing import ClassVar

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class BangbooPlugin(Enum):
    """枯萎之都里可使用的邦布插件 value 为选中后名称行的识别关键字"""

    BOMB = '交叉爆破'
    MEDICAL = '浓缩医疗'


class UseBangbooPlugin(ZOperation):

    STATUS_CHOSEN: ClassVar[str] = '已选择'
    STATUS_QUICK_USED: ClassVar[str] = '已快速使用'

    SCREEN_NAME: ClassVar[str] = '零号空洞-事件'
    LONG_PRESS_SECONDS: ClassVar[float] = 1.0
    AFTER_USE_WAIT: ClassVar[float] = 2.5  # 使用插件后有后摇 期间点击入口没有响应
    SLOT_FALLBACK_X: ClassVar[list[int]] = [716, 838, 960, 1082, 1203]  # 槽位横坐标兜底 1080p 下一共5个
    SLOT_Y: ClassVar[int] = 422

    def __init__(self, ctx: ZContext, plugin: BangbooPlugin):
        """
        使用一个邦布插件 例如炸弹 医疗包
        打开插件列表 逐个点击圆形槽位 通过OCR名称找到目标 再OCR点击[使用]
        点击和长按哪个是打开列表 取决于游戏设置 因此先试默认的 打不开再换另一种
        有效的手势记录在 ctx.withered_domain.plugin_click_opens_list 里 之后直接使用
        打不开列表的手势 可能把当前选中的插件快速使用掉了 之后列表里找不到目标 就认为已经使用
        失败的情况: 打不开列表 / 列表里没有目标插件 / 使用后弹窗没有关闭

        :param ctx: 上下文
        :param plugin: 需要使用的插件
        """
        ZOperation.__init__(
            self, ctx,
            op_name=f'{gt("使用邦布插件", "game")} {plugin.value}'
        )
        self.plugin: BangbooPlugin = plugin
        self._slots: list[Point] | None = None  # 圆形槽位的中心
        self._slot_idx: int = 0  # 下一个要点击的槽位
        self._gesture_times: int = 0  # 尝试打开列表的手势次数
        self._last_is_click: bool | None = None  # 上一次手势是否点击
        self._quick_used: bool = False  # 是否有手势没能打开列表 即可能快速使用了插件

    @operation_node(name='打开列表', is_start_node=True, node_max_retry_times=3)
    def open_list(self) -> OperationRoundResult:
        if self.round_by_find_area(self.last_screenshot, self.SCREEN_NAME, '邦布插件-标题').is_success:
            if self._last_is_click is not None:
                self.ctx.withered_domain.plugin_click_opens_list = self._last_is_click
            return self.round_success('已打开')

        known = self.ctx.withered_domain.plugin_click_opens_list
        if known is None:
            # 还不知道哪种手势能打开列表
            if self._last_is_click is not None:
                # 上一次手势没能打开列表 可能是快速使用了当前选中的插件
                self._quick_used = True
            # 先试点击 之后每次换另一种手势
            use_click = self._gesture_times % 2 == 0
        else:
            # 已经知道有效的手势 没打开多半是后摇等原因 重试同一种手势 不换
            use_click = known

        entry = self.ctx.screen_loader.get_area(self.SCREEN_NAME, '邦布插件-入口')
        if use_click:
            self.ctx.controller.click(entry.center)
        else:
            self.ctx.controller.click(entry.center, press_time=self.LONG_PRESS_SECONDS)
        self._gesture_times += 1
        self._last_is_click = use_click
        return self.round_retry('打开插件列表', wait=1)

    @node_from(from_name='打开列表')
    @operation_node(name='选择插件', node_max_retry_times=3)
    def choose_plugin(self) -> OperationRoundResult:
        if self._slots is None:
            self._slots = self._find_slots(self.last_screenshot)
            log.info(f'识别到插件槽位 {len(self._slots)} 个')

        if self._slot_idx >= len(self._slots):
            # 关闭插件列表 使用通用的关闭按钮模板
            self.round_by_find_and_click_area(self.screenshot(), '画面-通用', '关闭', success_wait=0.5)
            if self._quick_used:
                log.info(f'列表里没有 {self.plugin.value} 之前的手势应该已经快速使用了')
                return self.round_success(self.STATUS_QUICK_USED)
            return self.round_fail(f'列表里没有 {self.plugin.value}')

        pos = self._slots[self._slot_idx]
        self._slot_idx += 1
        self.ctx.controller.click(pos)
        time.sleep(0.5)

        screen = self.screenshot()
        name_area = self.ctx.screen_loader.get_area(self.SCREEN_NAME, '邦布插件-名称')
        if self.round_by_ocr(screen, self.plugin.value, area=name_area, lcs_percent=0.75).is_success:
            return self.round_success(self.STATUS_CHOSEN)

        return self.round_wait(f'第 {self._slot_idx} 个不是 {self.plugin.value}')

    @node_from(from_name='选择插件', status=STATUS_CHOSEN)
    @operation_node(name='使用', node_max_retry_times=3)
    def click_use(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(self.last_screenshot, self.SCREEN_NAME, '邦布插件-使用',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='使用')
    @operation_node(name='确认关闭', node_max_retry_times=3)
    def check_closed(self) -> OperationRoundResult:
        if self.round_by_find_area(self.last_screenshot, self.SCREEN_NAME, '邦布插件-标题').is_success:
            return self.round_retry('使用后弹窗未关闭', wait=1)
        # 等待使用插件的后摇结束 否则紧接着的点击没有响应
        return self.round_success(wait=self.AFTER_USE_WAIT)

    def _find_slots(self, screen: MatLike) -> list[Point]:
        """
        用圆形检测找出插件槽位 从左到右排序
        找不到时使用固定位置兜底 EMPTY 的槽位点了也无害 名称对不上会被跳过
        """
        area = self.ctx.screen_loader.get_area(self.SCREEN_NAME, '邦布插件-槽位')
        part = cv2_utils.crop_image_only(screen, area.rect)
        gray = cv2.cvtColor(part, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=1, minDist=90,
            param1=100, param2=30, minRadius=40, maxRadius=65,
        )

        slots: list[Point] = []
        if circles is not None:
            for x, y, _ in np.around(circles[0]).astype(int):
                slots.append(Point(int(x) + area.rect.x1, int(y) + area.rect.y1))
            slots.sort(key=lambda p: p.x)

        if len(slots) == 0:
            slots = [Point(x, self.SLOT_Y) for x in self.SLOT_FALLBACK_X]
        return slots
