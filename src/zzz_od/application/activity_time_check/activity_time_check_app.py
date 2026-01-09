import re
from typing import ClassVar

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from zzz_od.application.activity_time_check import activity_time_check_const
from zzz_od.application.activity_time_check.activity_time_check_config import (
    ActivityTimeCheckConfig,
)
from zzz_od.application.activity_time_check.activity_time_check_run_record import (
    ActivityTimeCheckRunRecord,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class ActivityTimeCheckApp(ZApplication):

    STATUS_NO_ACTIVITIES: ClassVar[str] = '无活动'
    STATUS_NO_TIME_DETECTED: ClassVar[str] = '未检测到时间'

    def __init__(self, ctx: ZContext):
        """
        活动剩余时间检测
        1. 识别每个活动标题
        2. 黑白名单过滤
        3. 对于剩下的活动，点击后区域内OCR并提取出疑似时间的字符串
        4. 没识别到时间的活动不通知
        5. 发送总结通知
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=activity_time_check_const.APP_ID,
            op_name=activity_time_check_const.APP_NAME,
        )

        self.config: ActivityTimeCheckConfig = self.ctx.run_context.get_config(
            app_id=activity_time_check_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: ActivityTimeCheckRunRecord = self.ctx.run_context.get_run_record(
            app_id=activity_time_check_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
        )

    def handle_init(self) -> None:
        """
        执行前的初始化
        """
        # 存储活动标题和对应的时间信息
        self._activity_dict: dict[str, str] = {}
        # 当前处理的活动索引
        self._current_activity_idx: int = 0
        # 待检查的活动标题列表
        self._activities_to_check: list[str] = []
        # 活动位置信息列表 (标题, 点击位置y坐标)
        self._activity_positions: list[tuple] = []
        # 当前查看的活动标题
        self._current_activity_title: str = ''

    @operation_node(name='返回大世界', is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        """
        首先确保在大世界
        """
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='返回大世界')
    @operation_node(name='打开菜单')
    def open_menu(self) -> OperationRoundResult:
        """
        打开菜单
        """
        return self.round_by_goto_screen(screen_name='菜单')

    @node_from(from_name='打开菜单')
    @operation_node(name='打开更多功能')
    def open_more(self) -> OperationRoundResult:
        """
        打开更多功能页面
        """
        return self.round_by_goto_screen(screen_name='菜单-更多功能')

    @node_from(from_name='打开更多功能')
    @operation_node(name='进入活动页面')
    def goto_activity(self) -> OperationRoundResult:
        """
        在更多功能页面中点击活动入口
        """
        # 尝试点击活动入口
        result = self.round_by_ocr_and_click(self.last_screenshot, '活动')
        if result.is_success:
            return self.round_success(wait=2)
        return self.round_retry(status='未找到活动入口', wait=1)

    @node_from(from_name='进入活动页面')
    @operation_node(name='识别活动列表')
    def recognize_activities(self) -> OperationRoundResult:
        """
        OCR识别活动列表中的活动标题
        """
        # 获取活动列表区域的截图
        screen = self.last_screenshot

        # 对全屏进行OCR识别
        ocr_results = self.ctx.ocr.run_ocr(screen)

        activity_titles: list[str] = []
        activity_positions: list[tuple] = []

        for ocr_text, mrl in ocr_results.items():
            if mrl.max is None:
                continue

            # 过滤掉太短的文本和常见的UI元素
            if len(ocr_text) < 2:
                continue

            # 过滤常见的非活动文本
            skip_words = ['返回', '菜单', '更多', '设置', '邮件', '活动', '公告', '兑换码', '帮助']
            should_skip = False
            for skip_word in skip_words:
                if skip_word == ocr_text:
                    should_skip = True
                    break
            if should_skip:
                continue

            # 检查是否符合白名单/黑名单过滤规则
            if self.config.should_check_activity(ocr_text):
                activity_titles.append(ocr_text)
                activity_positions.append((ocr_text, mrl.max.center))

        if len(activity_titles) == 0:
            log.info('未识别到需要检查的活动')
            return self.round_success(ActivityTimeCheckApp.STATUS_NO_ACTIVITIES)

        self._activities_to_check = activity_titles
        self._activity_positions = activity_positions
        self._current_activity_idx = 0
        log.info(f'识别到 {len(activity_titles)} 个活动需要检查: {activity_titles}')

        return self.round_success()

    @node_from(from_name='识别活动列表')
    @node_from(from_name='返回活动列表')
    @operation_node(name='点击活动')
    def click_activity(self) -> OperationRoundResult:
        """
        点击当前索引的活动
        """
        if self._current_activity_idx >= len(self._activity_positions):
            return self.round_success(status='所有活动已检查完毕')

        title, position = self._activity_positions[self._current_activity_idx]
        self._current_activity_title = title
        log.info(f'点击活动: {title}')

        self.ctx.controller.click(position)
        return self.round_success(wait=2)

    @node_from(from_name='点击活动')
    @operation_node(name='识别剩余时间')
    def recognize_time(self) -> OperationRoundResult:
        """
        在活动详情页面OCR识别剩余时间
        """
        screen = self.last_screenshot

        # 对活动详情区域进行OCR
        ocr_results = self.ctx.ocr.run_ocr(screen)

        time_str = self._extract_time_from_ocr(ocr_results)

        if time_str:
            self._activity_dict[self._current_activity_title] = time_str
            log.info(f'活动 "{self._current_activity_title}" 剩余时间: {time_str}')
        else:
            log.info(f'活动 "{self._current_activity_title}" 未识别到剩余时间')

        self._current_activity_idx += 1

        return self.round_success()

    def _extract_time_from_ocr(self, ocr_results: dict[str, any]) -> str | None:
        """
        从OCR结果中提取时间字符串

        支持的时间格式:
        - X天X小时
        - X天
        - X小时X分钟
        - X小时
        - 剩余X天
        - 还剩X天X小时
        - XX:XX:XX (时:分:秒)
        - XX月XX日 XX:XX
        """
        time_patterns = [
            # 匹配 "X天X小时" 格式
            r'(\d+)\s*天\s*(\d+)\s*小时',
            # 匹配 "X天" 格式
            r'(\d+)\s*天',
            # 匹配 "X小时X分钟" 格式
            r'(\d+)\s*小时\s*(\d+)\s*分',
            # 匹配 "X小时" 格式
            r'(\d+)\s*小时',
            # 匹配 "剩余X天" 或 "还剩X天" 格式
            r'[剩还][余剩]\s*(\d+)\s*天',
            # 匹配 "剩余X小时" 格式
            r'[剩还][余剩]\s*(\d+)\s*小时',
            # 匹配时间戳格式 XX:XX:XX
            r'(\d{1,2}:\d{2}:\d{2})',
            # 匹配日期时间格式 XX月XX日 或 XX/XX
            r'(\d{1,2}[月/]\d{1,2}[日]?\s*\d{1,2}:\d{2})',
            # 匹配截止日期格式
            r'截止[到至]?\s*(\d{1,2}[月/]\d{1,2})',
            # 匹配活动结束时间
            r'结束时间\s*[：:]\s*(.+)',
            # 匹配活动剩余
            r'活动剩余\s*[：:]?\s*(.+)',
        ]

        for ocr_text, _ in ocr_results.items():
            for pattern in time_patterns:
                match = re.search(pattern, ocr_text)
                if match:
                    # 返回匹配到的完整时间字符串
                    return match.group(0)

        return None

    @node_from(from_name='识别剩余时间')
    @operation_node(name='返回活动列表')
    def back_to_activity_list(self) -> OperationRoundResult:
        """
        返回活动列表
        """
        # 检查是否还有活动需要检查
        if self._current_activity_idx >= len(self._activity_positions):
            return self.round_success(status='所有活动已检查完毕')

        # 点击返回按钮
        return self.round_by_click_area('菜单', '返回', success_wait=1, retry_wait=1)

    @node_from(from_name='识别活动列表', status=STATUS_NO_ACTIVITIES)
    @node_from(from_name='点击活动', status='所有活动已检查完毕')
    @node_from(from_name='返回活动列表', status='所有活动已检查完毕')
    @operation_node(name='发送通知')
    def send_notification(self) -> OperationRoundResult:
        """
        发送活动时间通知
        """
        if len(self._activity_dict) == 0:
            log.info('没有检测到任何活动的剩余时间')
            return self.round_success(ActivityTimeCheckApp.STATUS_NO_TIME_DETECTED)

        message = self._format_notification_message()
        log.info(f'通知内容:\n{message}')

        self.ctx.push_service.push(
            title='活动剩余时间提醒',
            content=message,
            image=self.last_screenshot
        )

        return self.round_success()

    def _format_notification_message(self) -> str:
        """
        格式化通知消息
        """
        parts = ['📅 活动剩余时间汇总\n']

        for activity_title, time_str in self._activity_dict.items():
            parts.append(f'▪ {activity_title}: {time_str}')

        parts.append(f'\n共检测到 {len(self._activity_dict)} 个活动')

        return '\n'.join(parts)

    @node_from(from_name='发送通知')
    @node_from(from_name='发送通知', status=STATUS_NO_TIME_DETECTED)
    @operation_node(name='完成后返回大世界')
    def back_after_finish(self) -> OperationRoundResult:
        """
        完成后返回大世界
        """
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
    app = ActivityTimeCheckApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
