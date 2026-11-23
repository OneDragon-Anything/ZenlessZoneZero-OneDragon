from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.zzz_operation import ZOperation


class TransportByQuickNav(ZOperation):
    """通过快捷导航界面传送:大世界点地图按钮 -> 大地图点快捷导航按钮 -> 点区域卡 -> 点底部目的地卡片 -> 确认传送。

    2.x 大地图改版后，MapTransport 依赖的底部传送点名称列表已不存在，
    地图传送必然失败（issue #3059）。快捷导航的卡片位置固定、文字可 OCR，
    改走全点击链路，不依赖任何键盘按键。
    """

    # 快捷导航的区域网格为固定 3x3 布局，卡片文字位置恒定（1080p）
    REGION_CARD_POS: dict[str, tuple[int, int]] = {
        '布亚斯特城区': (528, 328),
        '[空洞]斯卡莫空洞': (1136, 328),
        '录像店': (1841, 329),
        '澄辉坪': (795, 517),
        '维尔乌姆城区': (526, 606),
        '六分街': (1841, 606),
        '[管制区]布亚斯特': (499, 884),
        '[空洞]航天城': (1163, 884),
        '热望角': (1841, 885),
    }

    # 底部目的地卡片文字所在横条（左右翻页箭头除外）
    BOTTOM_BAR_RECT = Rect(60, 1020, 1860, 1062)

    def __init__(self, ctx: ZContext, region_name: str, dest_name: str,
                 wait_at_last: bool = True,
                 dest_alias_list: list[str] | None = None) -> None:
        ZOperation.__init__(self, ctx, op_name=f'快捷导航传送 {region_name} {dest_name}')

        self.region_name: str = region_name
        self.dest_name: str = dest_name
        self.wait_at_last: bool = wait_at_last
        # 卡片 OCR 实际文字与目的地名不同时，由调用方声明别名（如「随便观」的卡片实际是「随便观外庭」）
        self.dest_alias_list: list[str] = dest_alias_list or []

    def _ocr_in_rect(self, rect: Rect) -> dict[str, object]:
        """指定区域内 OCR，返回 文字 -> 识别结果 的映射"""
        return self.ctx.ocr_service.get_ocr_result_map(
            self.last_screenshot, rect=rect, crop_first=False
        )

    def _ocr_full(self) -> dict[str, object]:
        """整屏 OCR"""
        return self.ctx.ocr_service.get_ocr_result_map(
            self.last_screenshot, crop_first=False
        )

    def _find_and_click_text(self, text: str, rect: Rect | None = None) -> bool:
        """在画面（或指定区域）里找到文字并点击其中心，找到并点击返回 True"""
        ocr_result = self._ocr_full() if rect is None else self._ocr_in_rect(rect)
        for ocr_str, mrl in ocr_result.items():
            if text in ocr_str:
                center = mrl.max.center
                self.ctx.controller.click(center)
                return True
        return False

    @operation_node(name='开始前返回', is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='开始前返回')
    @operation_node(name='打开大地图', node_max_retry_times=5)
    def open_map(self) -> OperationRoundResult:
        """点击大世界右上角的地图按钮，打开大地图（与旧地图传送相同的入口）"""
        ocr_result = self._ocr_full()
        if any('快捷导航' in ocr_str for ocr_str in ocr_result):
            return self.round_success()

        return self.round_by_find_and_click_area(self.last_screenshot, '大世界', '地图',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='打开大地图')
    @operation_node(name='打开快捷导航', node_max_retry_times=5)
    def open_quick_nav(self) -> OperationRoundResult:
        """在大地图右上角点击「快捷导航」按钮，以网格里能看到目标区域卡为成功标志"""
        pos = self.REGION_CARD_POS.get(self.region_name)
        if pos is None:
            return self.round_fail(f'未支持的快捷导航区域 {self.region_name}')

        grid_rect = Rect(60, 280, 1860, 920)
        ocr_result = self._ocr_in_rect(grid_rect)
        if any(self.region_name in ocr_str for ocr_str in ocr_result):
            return self.round_success()

        if self._find_and_click_text('快捷导航'):
            return self.round_retry(wait=1)

        return self.round_retry(wait=1)

    @node_from(from_name='打开快捷导航')
    @operation_node(name='选择区域', node_max_retry_times=5)
    def choose_region(self) -> OperationRoundResult:
        """点击区域卡，让底部快捷栏切换出该区域的目的地。

        底部栏已经有目标目的地时（例如角色就在该区域）跳过点击，
        避免对已选中卡片重复点击弹出区域传送确认。
        """
        bottom_result = self._ocr_in_rect(self.BOTTOM_BAR_RECT)
        if any(self.dest_name in ocr_str for ocr_str in bottom_result):
            return self.round_success(status='目的地已在快捷栏')

        pos = self.REGION_CARD_POS[self.region_name]
        self.ctx.controller.click(Point(pos[0], pos[1]))
        return self.round_success(wait=1)

    @node_from(from_name='选择区域')
    @operation_node(name='选择目的地', node_max_retry_times=8)
    def choose_dest(self) -> OperationRoundResult:
        """在底部快捷栏 OCR 找到目的地卡片并点击；找不到时点右箭头翻页。

        若画面上出现"是否传送至该地点"确认框（点区域卡直接触发时），先取消，
        回到快捷导航再找目的地卡片。
        """
        full_result = self._ocr_full()
        if any('是否传送' in ocr_str for ocr_str in full_result):
            for ocr_str, mrl in full_result.items():
                if ocr_str == '取消':
                    self.ctx.controller.click(mrl.max.center)
                    return self.round_retry(wait=1)

        bottom_result = self._ocr_in_rect(self.BOTTOM_BAR_RECT)
        # 只接受完全一致的卡片名（含调用方声明的 OCR 别名），
        # 宁可翻页重试失败也不误点其他前缀卡片
        exact_names = [self.dest_name, *self.dest_alias_list]
        for ocr_str, mrl in bottom_result.items():
            if ocr_str.strip() in exact_names:
                self.ctx.controller.click(mrl.max.center)
                return self.round_success(wait=1.5)

        # 目的地不在当前可见的 6 张卡片里，点右箭头翻页
        log.info(f'[{self.op_name}] 目的地未命中, 当前底部栏 OCR: {list(bottom_result.keys())}')
        self.ctx.controller.click(Point(1888, 973))
        return self.round_retry(wait=1)

    @node_from(from_name='选择目的地')
    @operation_node(name='确认传送', node_max_retry_times=5)
    def confirm_transport(self) -> OperationRoundResult:
        """点击弹窗中的确认，完成传送"""
        ocr_result = self._ocr_full()
        for ocr_str, mrl in ocr_result.items():
            if ocr_str == '确认':
                self.ctx.controller.click(mrl.max.center)
                return self.round_success(wait=2)

        return self.round_retry(wait=1)

    @node_from(from_name='确认传送')
    @operation_node(name='等待大世界加载')
    def wait_in_world(self) -> OperationRoundResult:
        """与 Transport 同名参数保持一致契约：落地可能触发好感度事件，使用 BackToNormalWorld 处理"""
        if not self.wait_at_last:
            return self.round_success('不等待大世界加载')
        op = BackToNormalWorld(self.ctx, timeout_seconds=120)
        return self.round_by_op_result(op.execute())
