import time

import cv2

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.back_to_world import back_to_world_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.parsers import IAgentNameParser
from zzz_od.game_data.game_data_service import GameDataService
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class BackToWorldApp(ZApplication):

    def __init__(self, ctx: ZContext, agent_name_parser: IAgentNameParser | None = None):
        """
        返回大世界应用
        将游戏从任何状态智能返回到大世界（普通世界）

        Args:
            ctx: ZContext 上下文
            agent_name_parser: 代理人名称解析器（可选，默认 None 会使用默认实现）
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=back_to_world_const.APP_ID,
            op_name=back_to_world_const.APP_NAME,
        )
        self.selected_agent_code = getattr(self.ctx, '_back_to_world_agent_code', None)
        self.selected_drive_disk_set = getattr(self.ctx, '_back_to_world_drive_disk_set', None)
        self.agent_name_parser = self._get_default_parser() if agent_name_parser is None else agent_name_parser
        self.game_data_service = GameDataService()
        log.info(f"返回大世界应用初始化：选择的代理人={self.selected_agent_code}, 选择的驱动盘套装={self.selected_drive_disk_set}")

    def _get_default_parser(self) -> IAgentNameParser:
        """获取默认的代理人名称解析器"""
        try:
            from zzz_od.application.inventory_scan.parser.agent_name_parser import AgentNameParser
            return AgentNameParser()
        except ImportError:
            log.warning("无法导入 AgentNameParser，将无法解析代理人名称")
            # 返回一个简单的占位实现
            class DummyParser(IAgentNameParser):
                def parse_ocr_result(self, ocr_items, screenshot=None):
                    return None

                def reset(self):
                    pass
            return DummyParser()

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        pass

    @operation_node(name='返回大世界', is_start_node=True)
    def back_to_world(self) -> OperationRoundResult:
        """
        返回大世界
        :return:
        """
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='返回大世界')
    @operation_node(name='导航到特定代理人')
    def navigate_to_agent_info(self) -> OperationRoundResult:
        """
        导航到代理人-信息画面
        :return:
        """
        result = self.round_by_goto_screen(screen_name='代理人-信息')
        if not result.is_success:
            return result

        if not self.selected_agent_code:
            log.info("未选择代理人，停留在代理人-信息界面")
            return self.round_success('已导航到代理人-信息界面')

        return self._navigate_to_specific_agent()

    def _navigate_to_specific_agent(self) -> OperationRoundResult:
        """
        导航到指定的代理人
        参考 special_scan_app.py 的实现方式
        :return:
        """
        log.info(f"开始导航到代理人: {self.selected_agent_code}")

        agent_name_area = self.ctx.screen_loader.get_area('代理人-信息', '代理人-名称')
        switch_next_agent_area = self.ctx.screen_loader.get_area('代理人-信息', '按钮-下一位代理人')

        max_iterations = 100
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            screen = self.screenshot()
            if screen is None:
                log.error("截图失败，无法获取屏幕画面")
                return self.round_fail('截图失败')

            cropped_screen = cv2_utils.crop_image_only(screen, agent_name_area.rect)

            ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
                image=cropped_screen,
                rect=None,
                crop_first=False
            )

            if not ocr_result_list or len(ocr_result_list) == 0:
                log.warning("OCR 未识别到任何文本")
                self.ctx.controller.click(switch_next_agent_area.rect.center)
                time.sleep(0.3)
                continue

            ocr_items = [
                {
                    "text": item.data,
                    "confidence": item.confidence
                }
                for item in ocr_result_list
            ]

            parsed_result = self.agent_name_parser.parse_ocr_result(
                ocr_items,
                cropped_screen
            )

            if not parsed_result:
                log.warning("未能解析到代理人名称")
                self.ctx.controller.click(switch_next_agent_area.rect.center)
                time.sleep(0.3)
                continue

            current_agent_code = parsed_result.get('key', '')
            log.info(f"当前代理人代码: {current_agent_code}, 目标代理人代码: {self.selected_agent_code}")

            if current_agent_code == self.selected_agent_code:
                log.info(f"已找到目标代理人: {self.selected_agent_code}")
                return self.round_success(f'已导航到代理人: {self.selected_agent_code}')

            self.ctx.controller.click(switch_next_agent_area.rect.center)
            time.sleep(0.3)

        return self.round_fail(f'未找到目标代理人: {self.selected_agent_code}，已超过最大循环次数')

    @node_from(from_name='导航到特定代理人')
    @operation_node(name='导航到特定代理人装备详细')
    def navigate_to_agent_equipment_detail(self) -> OperationRoundResult:
        """
        导航到特定代理人-装备详细画面
        :return:
        """
        return self.round_by_goto_screen(screen_name='代理人-装备详细')

    @node_from(from_name='导航到特定代理人装备详细')
    @operation_node(name='执行套装筛选')
    def execute_set_filter(self) -> OperationRoundResult:
        """
        执行套装筛选操作
        根据用户选择的驱动盘套装进行筛选

        :return:
        """
        if not self.selected_drive_disk_set:
            log.info("未选择驱动盘套装，跳过筛选")
            return self.round_success('未选择套装')

        log.info(f"开始执行套装筛选，目标是: {self.selected_drive_disk_set}")

        # 将英文代码转换为中文名称
        target_set_name = self._get_set_name_by_code(self.selected_drive_disk_set)
        log.info(f"转换后的中文名称: {target_set_name}")

        try:
            filter_area = self.ctx.screen_loader.get_area('代理人-装备详细', '筛选')
            reset_area = self.ctx.screen_loader.get_area('筛选', '重置')
            set_select_area = self.ctx.screen_loader.get_area('筛选', '套装选择')
            confirm_area = self.ctx.screen_loader.get_area('套装筛选', '确认筛选')
        except Exception as e:
            log.error(f"获取筛选区域失败: {e}")
            return self.round_fail(f'获取筛选区域失败: {e}')

        log.info("点击筛选按钮")
        self.ctx.controller.click(filter_area.rect.center)
        time.sleep(0.5)

        log.info("点击重置按钮")
        self.ctx.controller.click(reset_area.rect.center)
        time.sleep(0.3)

        log.info("点击套装选择按钮")
        self.ctx.controller.click(set_select_area.rect.center)
        time.sleep(0.5)

        log.info(f"在套装列表中查找: {self.selected_drive_disk_set}")

        pipeline = self.ctx.cv_service.load_pipeline('套装筛选')
        if pipeline is None:
            log.error("无法加载套装筛选流水线")
            return self.round_fail('无法加载套装筛选流水线')

        max_loop_count = 10
        loop_count = 0
        found_target = False

        while loop_count < max_loop_count:
            loop_count += 1
            log.info(f"第 {loop_count} 次尝试查找套装")

            screen = self.screenshot()
            result = pipeline.execute(screen, service=self.ctx.cv_service)

            if not result.success:
                log.warning(f"套装筛选流水线执行失败: {result.error_str}")
                time.sleep(0.3)
                continue

            if not result.ocr_result:
                log.warning("未识别到任何OCR结果")
                time.sleep(0.3)
                continue

            offset_x, offset_y = result.crop_offset

            for ocr_text, match_list in result.ocr_result.items():
                if self._match_text(ocr_text, target_set_name):
                    if match_list:
                        match = match_list[0]
                        absolute_x1 = match.rect.x1 + offset_x
                        absolute_y1 = match.rect.y1 + offset_y
                        absolute_x2 = match.rect.x2 + offset_x
                        absolute_y2 = match.rect.y2 + offset_y
                        target_point = Point((absolute_x1 + absolute_x2) / 2, (absolute_y1 + absolute_y2) / 2 - 60)
                        log.info(f"找到匹配套装 {ocr_text}，点击位置: ({target_point.x}, {target_point.y})")
                        self.ctx.controller.click(target_point)
                        time.sleep(0.3)
                        found_target = True
                        break

            if found_target:
                break

            log.info("未匹配到任何目标，执行滚动操作")
            for _i in range(3):
                self.ctx.controller.scroll(1, Point(899, 428))
            time.sleep(0.5)

        if not found_target:
            log.warning(f"未找到匹配套装: {self.selected_drive_disk_set}")
            return self.round_fail(f'未找到匹配套装: {self.selected_drive_disk_set}')

        log.info("点击确认筛选按钮")
        self.ctx.controller.click(confirm_area.rect.center)
        time.sleep(0.5)

        log.info("再次点击确认筛选按钮以回到特定代理人装备详细界面")
        self.ctx.controller.click(confirm_area.rect.center)
        time.sleep(0.5)

        log.info("套装筛选完成")
        return self.round_success('套装筛选完成')

    @node_from(from_name='执行套装筛选')
    @operation_node(name='检测驱动盘方格并滚动至底部')
    def detect_drive_disk_grid_and_scroll_to_bottom(self) -> OperationRoundResult:
        """
        检测驱动盘方格，如果最后一行有4个驱动盘则滚动直至触底

        使用流水线配置文件进行图像处理：
        - assets/image_analysis_pipelines/驱动盘方格-代理人-装备详细.yml
        - assets/image_analysis_pipelines/驱动盘进度条-代理人-装备详细.yml

        :return:
        """
        log.info("开始检测驱动盘方格并滚动至底部")

        pipeline = self.ctx.cv_service.load_pipeline('驱动盘方格-代理人-装备详细')
        if pipeline is None:
            log.error("无法加载驱动盘方格检测流水线")
            return self.round_fail('无法加载驱动盘方格检测流水线')

        try:
            drive_disk_list_area = self.ctx.screen_loader.get_area('代理人-装备详细', '驱动盘列表')
        except Exception as e:
            log.error(f"获取驱动盘列表区域失败: {e}")
            return self.round_fail('获取驱动盘列表区域失败')

        max_scroll_iterations = 100
        scroll_iteration = 0

        while scroll_iteration < max_scroll_iterations:
            scroll_iteration += 1
            log.info(f"第 {scroll_iteration} 次检测驱动盘方格")

            screen = self.screenshot()
            if screen is None:
                log.error("截图失败，无法获取屏幕画面")
                return self.round_fail('截图失败')

            context = pipeline.execute(screen, service=self.ctx.cv_service)
            if not context.success:
                log.error(f"流水线执行失败: {context.error_str}")
                return self.round_fail(f'流水线执行失败: {context.error_str}')

            filtered_contours = context.contours
            if not filtered_contours:
                log.warning("未检测到驱动盘方格")
                return self.round_success('未检测到驱动盘方格', data={'last_row_has_four': False, 'total_grids': 0, 'is_bottom': True})

            log.info(f"检测到 {len(filtered_contours)} 个驱动盘方格")

            all_grids = []
            for contour in filtered_contours:
                x, y, w, h = cv2.boundingRect(contour)
                absolute_x = x + drive_disk_list_area.rect.x1
                absolute_y = y + drive_disk_list_area.rect.y1
                grid_center = Point(absolute_x + w / 2, absolute_y + h / 2)
                all_grids.append(grid_center)

            grid_rows = self._sort_grids(all_grids)

            last_row_has_four = False
            if grid_rows:
                last_row = grid_rows[-1]
                last_row_has_four = len(last_row) == 4
                log.info(f"最后一行驱动盘数量: {len(last_row)}, 是否为4个: {last_row_has_four}")

            if last_row_has_four:
                log.info("最后一行有4个驱动盘，检测进度条判断是否触底")
                log.info(f"当前网格位置信息: 共{len(grid_rows)}行, 最后一行={len(grid_rows[-1]) if grid_rows else 0}个")
                for i, row in enumerate(grid_rows):
                    log.debug(f"行 {i}: {len(row)} 个驱动盘")

                has_progress_bar = self._detect_progress_bar(screen)

                if has_progress_bar:
                    log.info("检测到进度条，已触底")
                    return self.round_success(
                        '已触底',
                        data={
                            'last_row_has_four': True,
                            'total_grids': len(filtered_contours),
                            'row_count': len(grid_rows),
                            'last_row_count': len(grid_rows[-1]) if grid_rows else 0,
                            'is_bottom': True,
                            'scroll_count': scroll_iteration
                        }
                    )
                else:
                    log.info("未检测到进度条，触发滚动")
                    target = grid_rows[-1][0]
                    log.info(f"点击最后一行第一个驱动盘触发滚动: ({target.x}, {target.y})")
                    log.info(f"驱动盘列表区域: ({drive_disk_list_area.rect.x1}, {drive_disk_list_area.rect.y1}, {drive_disk_list_area.rect.x2}, {drive_disk_list_area.rect.y2})")
                    log.info(f"点击前画面中驱动盘网格: {len(all_grids)} 个")

                    for i, grid in enumerate(grid_rows[-1]):
                        log.info(f"最后一行驱动盘 {i}: ({grid.x}, {grid.y})")

                    log.info(f"执行滚动操作，位置: ({target.x}, {target.y})")
                    self.ctx.controller.scroll(1, target)
                    log.info("滚动操作已发送，等待滚动完成")
                    time.sleep(0.5)
            else:
                log.info("最后一行不足4个驱动盘，已触底")
                return self.round_success(
                    '已触底',
                    data={
                        'last_row_has_four': False,
                        'total_grids': len(filtered_contours),
                        'row_count': len(grid_rows),
                        'last_row_count': len(grid_rows[-1]) if grid_rows else 0,
                        'is_bottom': True,
                        'scroll_count': scroll_iteration
                    }
                )

        log.warning(f"已达到最大滚动次数 {max_scroll_iterations}，停止滚动")
        return self.round_success(
            '达到最大滚动次数',
            data={
                'is_bottom': False,
                'scroll_count': scroll_iteration
            }
        )

    def _match_text(self, text1: str, text2: str, threshold: float = 0.6) -> bool:
        """
        判断两个文本是否匹配（模糊匹配）

        Args:
            text1: 文本1
            text2: 文本2
            threshold: 相似度阈值

        Returns:
            bool: 是否匹配
        """
        import difflib
        similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
        return similarity >= threshold

    def _get_set_name_by_code(self, code: str) -> str:
        """
        根据套装代码获取中文名称（使用 GameDataService）

        Args:
            code: 套装英文代码

        Returns:
            str: 套装中文名称，如果未找到则返回原代码
        """
        try:
            for disk_set in self.game_data_service.drive_disk_list:
                if disk_set.get("code") == code:
                    set_name = disk_set.get("set_name")
                    if set_name:
                        log.info(f"找到套装名称: code={code}, name={set_name}")
                        return set_name
            log.warning(f"未找到套装代码 {code} 的中文名称")
            return code
        except Exception as e:
            log.error(f"通过 GameDataService 获取驱动盘名称失败: {e}")
            return code

    def _sort_grids(self, all_disks: list[Point]) -> list[list[Point]]:
        """
        将所有点整理为二维网格（参考 drive_disk_enhance_bundle 的实现）

        Args:
            all_disks: 点列表

        Returns:
            二维网格，每个元素是一行点
        """
        if not all_disks:
            return []

        sorted_by_y = sorted(all_disks, key=lambda d: d.y)

        rows = []
        current_row = [sorted_by_y[0]]
        y_tolerance = 20

        for i in range(1, len(sorted_by_y)):
            disk = sorted_by_y[i]
            if abs(disk.y - current_row[0].y) <= y_tolerance:
                current_row.append(disk)
            else:
                current_row.sort(key=lambda d: d.x)
                rows.append(current_row)
                current_row = [disk]

        if current_row:
            current_row.sort(key=lambda d: d.x)
            rows.append(current_row)

        filtered_rows = []
        for i, row in enumerate(rows):
            if i < len(rows) - 1:
                if len(row) == 4:
                    filtered_rows.append(row)
            else:
                if 1 <= len(row) <= 4:
                    filtered_rows.append(row)

        return filtered_rows

    def _detect_progress_bar(self, screen) -> bool:
        """
        检测驱动盘进度条是否存在

        使用流水线配置文件进行图像处理：
        assets/image_analysis_pipelines/驱动盘进度条-代理人-装备详细.yml

        Args:
            screen: 截图画面

        Returns:
            bool: 进度条是否存在
        """
        pipeline_name = '驱动盘进度条-代理人-装备详细'
        log.info(f"开始检测进度条，流水线名称: {pipeline_name}")

        # 检查流水线文件是否存在
        import os
        pipeline_path = os.path.join(
            self.ctx.cv_service.PIPELINE_DIR,
            f"{pipeline_name}.yml"
        )
        log.info(f"流水线文件路径: {pipeline_path}")
        log.info(f"文件是否存在: {os.path.exists(pipeline_path)}")

        if os.path.exists(pipeline_path):
            with open(pipeline_path, encoding='utf-8') as f:
                content = f.read()
                log.debug(f"流水线文件内容:\n{content}")

        try:
            ctx = self.ctx.cv_service.run_pipeline(pipeline_name, screen)
        except Exception as e:
            log.warning(f"进度条检测流水线执行异常: {e}")
            import traceback
            log.warning(f"异常堆栈:\n{traceback.format_exc()}")
            return False

        if not ctx.success:
            if ctx.error_str is not None:
                # 真正的执行错误
                log.warning(f"进度条检测流水线执行失败: {ctx.error_str}")
                if hasattr(ctx, 'steps_results'):
                    for i, step_result in enumerate(ctx.steps_results):
                        log.info(f"步骤 {i} 结果: success={step_result.success}, error={step_result.error_str if hasattr(step_result, 'error_str') else 'N/A'}")
                return False
            else:
                # success=False 但 error_str=None 表示只是没有找到轮廓，不是错误
                log.info("进度条检测流水线执行完成，未找到轮廓")

        has_progress_bar = ctx.contours is not None and len(ctx.contours) > 0
        log.info(f"进度条检测完成，轮廓数量: {len(ctx.contours) if ctx.contours else 0}, 结果: {has_progress_bar}")

        if has_progress_bar and ctx.contours:
            for i, contour in enumerate(ctx.contours):
                x, y, w, h = cv2.boundingRect(contour)
                log.debug(f"轮廓 {i}: 位置=({x},{y}), 大小={w}x{h}")

        return has_progress_bar


def __debug():
    """
    调试函数
    用于测试返回大世界应用
    """
    ctx = ZContext()
    ctx.init_by_config()
    app = BackToWorldApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
