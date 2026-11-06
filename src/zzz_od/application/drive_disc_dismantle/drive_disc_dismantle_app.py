from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from zzz_od.application.drive_disc_dismantle import drive_disc_dismantle_const
from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_config import (
    DriveDiscDismantleConfig,
)
from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_run_record import (
    DriveDiscDismantleRunRecord,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class DriveDiscDismantleApp(ZApplication):

    """驱动盘分解:按配置批量分解驱动盘。销毁道具(不可逆),务必核对配置。"""

    STATUS_NO_DISC: str = '无可拆盘'

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=drive_disc_dismantle_const.APP_ID,
            op_name=drive_disc_dismantle_const.APP_NAME,
        )

        self.config: DriveDiscDismantleConfig = self.ctx.run_context.get_config(
            app_id=drive_disc_dismantle_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: DriveDiscDismantleRunRecord = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=drive_disc_dismantle_const.APP_ID,
        )

    @operation_node(name='开始前返回', is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='开始前返回')
    @operation_node(name='前往分解画面')
    def goto_salvage(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='仓库-驱动仓库-驱动盘拆解')

    @node_from(from_name='前往分解画面')
    @operation_node(name='快速选择')
    def click_filter(self) -> OperationRoundResult:
        # 等待 2s：弹窗打开动画未完成时，后续品质按钮点击会被吞掉（2026-10-27 诊断：0/300 选中）
        return self.round_by_find_and_click_area(self.last_screenshot, '仓库-驱动仓库-驱动盘拆解', '按钮-快速选择',
                                                 success_wait=2, retry_wait=1)

    @node_from(from_name='快速选择')
    @operation_node(name='重置筛选')
    def reset_filter(self) -> OperationRoundResult:
        """先重置弹窗内的全部选择再点选(2026-10-28 诊断)

        游戏会持久化上次弹窗的选择状态: 会话重启后「全选已弃置」丢失导致
        数量读数恒 0 误跳过; 残留的未弃置区选择则可能在确认时误选正常盘。
        重置后数量读数只反映本次节点的点击, 行为确定。
        """
        self.round_by_find_and_click_area(self.last_screenshot, '仓库-驱动仓库-驱动盘拆解',
                                          '按钮-快速选择-重置', success_wait=1, retry_wait=1)
        return self.round_success()

    @node_from(from_name='重置筛选')
    @operation_node(name='选择弃置')
    def choose_abandon(self) -> OperationRoundResult:
        if self.config.dismantle_abandon:
            return self.round_by_find_and_click_area(self.last_screenshot, '仓库-驱动仓库-驱动盘拆解',
                                                     '按钮-全选已弃置', success_wait=1, retry_wait=1)
        # 非弃置模式: 按配置选择品质(只拆未弃置的指定品质)
        return self.round_by_find_and_click_area(
            self.last_screenshot, '仓库-驱动仓库-驱动盘拆解', f'按钮-{self.config.dismantle_level}',
            success_wait=1, retry_wait=1
        )

    @node_from(from_name='选择弃置')
    @operation_node(name='检查可拆数量', node_max_retry_times=5)
    def check_disc_count(self) -> OperationRoundResult:
        """
        2026-10-28 重构后: 弹窗先重置→点选(全选已弃置/品质)→再读数量,
        数量读数只反映本次点击, 不再依赖游戏持久化的弹窗状态。
        - 数量 0: 复查一次(防异步)后仍为 0 → 跳过
        - 弹窗已自动关闭（回到拆解主页面）：直接视为无可拆盘
        """
        import re

        # 临时诊断: 数量读取时保存弹窗截图, 排查「标记2件但读数0」
        try:
            import os

            import cv2
            dbg_dir = os.path.join(os.getcwd(), '.debug', 'dismantle_debug')
            os.makedirs(dbg_dir, exist_ok=True)
            if self.last_screenshot is not None:
                cv2.imwrite(os.path.join(dbg_dir, 'count_screen.png'),
                            cv2.cvtColor(self.last_screenshot, cv2.COLOR_RGB2BGR))
        except Exception:
            pass

        result = self.round_by_find_area(self.last_screenshot, '仓库-驱动仓库-驱动盘拆解', '文本-符合条件数量')
        if result.is_success:
            area = self.ctx.screen_loader.get_area('仓库-驱动仓库-驱动盘拆解', '文本-符合条件数量')
            # 用多行 OCR：single_line 会丢失行尾的橙色数字（2026-10-27 运行时验证）
            ocr_map = self.ctx.ocr.crop_and_run_ocr(self.last_screenshot, area.rect)
            ocr_result = ''.join(ocr_map.keys())
            digits = re.findall(r'\d+', ocr_result)
            if len(digits) == 0:
                log.info('检查可拆数量 OCR 原文: %r', ocr_result)
                return self.round_retry('未识别到符合条件数量', wait=1)
            if int(digits[-1]) == 0:
                # 防异步: 数量行在点击选择后可能延迟刷新, 等1.5s复查一次(2026-10-28)
                import time
                time.sleep(1.5)
                self.screenshot()
                ocr_map2 = self.ctx.ocr.crop_and_run_ocr(self.last_screenshot, area.rect)
                digits2 = re.findall(r'\d+', ''.join(ocr_map2.keys()))
                if digits2 and int(digits2[-1]) > 0:
                    log.info(f'数量复查后非0: {digits2[-1]}(首读为异步旧值)')
                    return self.round_success()
                log.info('快速选择符合条件的驱动盘数量为 0 跳过拆解')
                return self.round_success(DriveDiscDismantleApp.STATUS_NO_DISC)
            log.info(f'快速选择符合条件的驱动盘数量: {digits[-1]}')
            return self.round_success()

        # 弹窗已自动关闭：0 盘时游戏的行为
        result2 = self.round_by_find_area(self.last_screenshot, '仓库-驱动仓库-驱动盘拆解', '标题-驱动盘拆解')
        if result2.is_success:
            log.info('快速选择弹窗已自动关闭 视为无可拆盘')
            return self.round_success(DriveDiscDismantleApp.STATUS_NO_DISC)

        return self.round_retry('弹窗状态未知', wait=1)

    @node_from(from_name='检查可拆数量')
    @node_from(from_name='检查可拆数量', success=False)
    @operation_node(name='快速选择确认')
    def click_filter_confirm(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(self.last_screenshot, '仓库-驱动仓库-驱动盘拆解', '按钮-快速选择-确认',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='快速选择确认')
    @operation_node(name='点击拆解')
    def click_salvage(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(self.last_screenshot, '仓库-驱动仓库-驱动盘拆解', '按钮-拆解',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击拆解')
    @operation_node(name='点击拆解确认')
    def click_salvage_confirm(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(self.last_screenshot, '仓库-驱动仓库-驱动盘拆解', '按钮-拆解-确认',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击拆解确认')
    @operation_node(name='确认获得')
    def confirm_obtained(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(self.last_screenshot, '道具处理-获得', '按钮-确认',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='确认获得')
    @node_from(from_name='确认获得', success=False)
    @node_from(from_name='点击拆解确认', success=False)  # 可能没有需要拆解的
    @node_from(from_name='检查可拆数量', status=STATUS_NO_DISC)
    @node_notify(when=NotifyTiming.CURRENT_SUCCESS)
    @operation_node(name='返回驱动仓库', node_max_retry_times=5)  # issue #2701
    def back_to_storage(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '仓库-驱动仓库-驱动盘拆解', '标题-驱动盘拆解')
        if result.is_success:
            return self.round_by_find_and_click_area(self.last_screenshot, '画面-通用', '返回',
                                                     success_wait=1, retry_wait=1)
        # 无可拆盘跳过时快速选择弹窗可能仍打开 遮挡标题：点弹窗右上角 X 关闭
        popup = self.round_by_find_area(self.last_screenshot, '仓库-驱动仓库-驱动盘拆解', '按钮-快速选择-确认')
        if popup.is_success:
            return self.round_by_click_area('仓库-驱动仓库-驱动盘拆解', '按钮-快速选择-关闭',
                                            success_wait=1, retry_wait=1)
        return self.round_retry(result.status, wait=1)

    @node_from(from_name='返回驱动仓库')
    @operation_node(name='返回大世界')
    def back_at_last(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init()
    app = DriveDiscDismantleApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
