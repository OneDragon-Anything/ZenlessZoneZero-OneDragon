import csv
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
import numpy as np

from cv2.typing import MatLike
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.driver_disc_read import driver_disc_read_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class DriverDiscReadApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=driver_disc_read_const.APP_ID,
            op_name=gt(driver_disc_read_const.APP_NAME),
        )

        self.disc_data_dict = {}  # 使用 global_index 作为 key
        self.total_disc_count = 0
        self.current_read_count = 0

        self.grid_config = {
            'start_x': 160,
            'start_y': 260,
            'width': 140,
            'height': 175,
            'cols': 9,
            'rows': 4,
        }

        self.ocr_areas = {}  # 预提取的 OCR 区域坐标

    @operation_node(name='开始前返回', is_start_node=True)
    def back_at_first(self):
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='开始前返回')
    @operation_node(name='前往驱动仓库')
    def goto_drive_disc_storage(self):
        return self.round_by_goto_screen(screen_name='仓库-驱动仓库')

    @node_from(from_name='前往驱动仓库')
    @operation_node(name='读取驱动盘总数')
    def read_total_count(self):
        screen = self.screenshot()
        screen_name = '仓库-驱动仓库'
        area = self.ctx.screen_loader.get_area(screen_name, '驱动仓库总数')

        if area is None:
            self.total_disc_count = 100
            self.current_read_count = 0
            return self.round_success(f'总数: {self.total_disc_count} (默认值)')

        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        log.debug(f'驱动盘总数OCR结果: {ocr_result_map}')

        for ocr_text in ocr_result_map.keys():
            match = re.search(r'\[?(\d+)', ocr_text)
            if match:
                current = int(match.group(1))
                self.total_disc_count = current
                self.current_read_count = 0
                return self.round_success(f'总数: {self.total_disc_count}')

        self.total_disc_count = 36
        self.current_read_count = 0
        return self.round_success(f'总数: {self.total_disc_count} (默认值)')

    @node_from(from_name='读取驱动盘总数')
    @operation_node(name='扫描驱动盘')
    def scan_all_discs(self):
        log.info(f'开始扫描驱动盘 总数:{self.total_disc_count}')

        # 预提取所有 OCR 区域坐标
        screen_name = '仓库-驱动盘'
        area_names = [
            '驱动盘名称', '驱动板等级', '驱动盘主属性', '驱动盘主属性值',
            '驱动盘副属性1', '驱动盘副属性1值',
            '驱动盘副属性2', '驱动盘副属性2值',
            '驱动盘副属性3', '驱动盘副属性3值',
            '驱动盘副属性4', '驱动盘副属性4值',
        ]

        self.ocr_areas = {}
        for area_name in area_names:
            area = self.ctx.screen_loader.get_area(screen_name, area_name)
            if area:
                rect = area.rect
                self.ocr_areas[area_name] = (rect.x1, rect.y1, rect.width, rect.height)

        global_index = 0

        # 第一屏（前 27 个）
        for i in range(27):
            if self.ctx.run_context.is_context_stop:
                return self.round_wait('停止识别', wait=0)
            self._process_disc(i, global_index)
            global_index += 1
            if global_index >= self.total_disc_count:
                break

        # 滚动后续屏幕
        while global_index < self.total_disc_count:
            if self.ctx.run_context.is_context_stop:
                return self.round_wait('停止识别', wait=0)

            # 点击底部位置进行滚动
            scroll_pos = Point(
                self.grid_config['start_x'],
                self.grid_config['start_y'] + 3 * self.grid_config['height']
            )
            self.ctx.controller.click(scroll_pos)
            time.sleep(0.05)

            remaining = self.total_disc_count - global_index
            is_last_screen = remaining <= 9

            if is_last_screen:
                # 最后一屏：直接点击剩余位置（位置 27+）
                read_positions = range(27, 27 + remaining)
            else:
                # 常规屏：点击位置 18-26（共 9 个）
                read_positions = range(18, 27)

            for grid_pos in read_positions:
                if self.ctx.run_context.is_context_stop:
                    return self.round_wait('停止识别', wait=0)
                self._process_disc(grid_pos, global_index)
                global_index += 1

        log.info(f'扫描完成 共识别:{len(self.disc_data_dict)}个')
        return self.round_success(f'识别完成: {len(self.disc_data_dict)}个')

    def _process_disc(self, grid_position: int, global_index: int):
        """点击位置、截图并识别"""
        click_pos = self._get_disc_position(grid_position)
        
        # 点击前获取当前面板签名
        prev_signature = self._get_panel_signature()
        
        self.ctx.controller.click(click_pos)
        
        # 智能等待面板更新（最多150ms）
        panel_updated = self._wait_for_panel_update(prev_signature, timeout=0.15)
        if not panel_updated:
            log.debug(f'面板更新超时 (驱动盘 {global_index})，继续截图')

        screen = self.screenshot()
        if screen is None:
            return

        # 识别
        disc_data = {}
        for area_name, rect_tuple in self.ocr_areas.items():
            x, y, w, h = rect_tuple
            part = screen[y:y+h, x:x+w]
            
            try:
                ocr_result_map = self.ctx.ocr.run_ocr(part)
                result_text = next(iter(ocr_result_map.keys())).strip() if ocr_result_map else ''
            except Exception as e:
                log.warning(f'OCR识别失败 {area_name}: {e}')
                result_text = ''
            
            disc_data[area_name] = result_text

        # 解析等级信息（格式：等级03/15）
        level_text = disc_data.get('驱动板等级', '')
        if level_text:
            # 提取 "等级XX/YY" 中的数字
            level_match = re.search(r'(\d+)/(\d+)', level_text)
            if level_match:
                current_level = level_match.group(1)  # 前面的数字（当前等级）
                max_level = level_match.group(2)      # 后面的数字（最大等级）

                # 根据最大等级判断评级
                if max_level == '15':
                    rating = 'S'
                elif max_level == '12':
                    rating = 'A'
                else:
                    rating = 'B'

                disc_data['level'] = current_level
                disc_data['rating'] = rating
            else:
                disc_data['level'] = level_text
                disc_data['rating'] = ''
        else:
            disc_data['level'] = ''
            disc_data['rating'] = ''

        # 解析区域名称到字段映射
        parsed_data = {
            'name': disc_data.get('驱动盘名称', ''),
            'level': disc_data.get('level', ''),
            'rating': disc_data.get('rating', ''),
            'main_stat': disc_data.get('驱动盘主属性', ''),
            'main_stat_value': disc_data.get('驱动盘主属性值', ''),
            'sub_stat1': disc_data.get('驱动盘副属性1', ''),
            'sub_stat1_value': disc_data.get('驱动盘副属性1值', ''),
            'sub_stat2': disc_data.get('驱动盘副属性2', ''),
            'sub_stat2_value': disc_data.get('驱动盘副属性2值', ''),
            'sub_stat3': disc_data.get('驱动盘副属性3', ''),
            'sub_stat3_value': disc_data.get('驱动盘副属性3值', ''),
            'sub_stat4': disc_data.get('驱动盘副属性4', ''),
            'sub_stat4_value': disc_data.get('驱动盘副属性4值', ''),
        }

        if parsed_data['name'].strip():
            self.disc_data_dict[global_index] = parsed_data
            log.info(f'识别完成 [{len(self.disc_data_dict)}/{self.total_disc_count}]: {parsed_data["name"]}')
        else:
            log.warning(f'未识别到驱动盘 [{global_index}] 原始名称: "{parsed_data["name"]}" 全量数据: {disc_data}')

    def _get_panel_signature(self) -> float:
        """获取当前驱动盘详情面板的签名（用于检测面板是否更新）"""
        screen = self.screenshot()
        if screen is None:
            return 0.0
        
        # 使用详情面板区域的像素均值作为签名
        # 详情面板位置约在 (1100, 200) 到 (1800, 900)
        panel_area = screen[200:900, 1100:1800]
        signature = float(np.mean(panel_area))
        return signature

    def _wait_for_panel_update(self, prev_signature: float, timeout: float = 0.15) -> bool:
        """
        智能等待面板更新
        
        Args:
            prev_signature: 之前的面板签名
            timeout: 最大等待时间（秒）
            
        Returns:
            是否检测到面板更新
        """
        import time
        start_time = time.time()
        check_interval = 0.005  # 5ms 采样间隔
        
        while time.time() - start_time < timeout:
            current_signature = self._get_panel_signature()
            
            # 如果签名差异超过阈值，认为面板已更新
            if abs(current_signature - prev_signature) > 1.0:
                return True
            
            time.sleep(check_interval)
        
        return False

    def _capture_and_queue_disc(self, grid_position: int, global_index: int):
        """点击位置、截图并放入队列（智能等待优化）"""
        click_pos = self._get_disc_position(grid_position)
        
        # 点击前获取当前面板签名
        prev_signature = self._get_panel_signature()
        
        self.ctx.controller.click(click_pos)
        
        # 智能等待面板更新（最多150ms）
        panel_updated = self._wait_for_panel_update(prev_signature, timeout=0.15)
        if not panel_updated:
            log.debug(f'面板更新超时 (驱动盘 {global_index})，继续截图')

        screen = self.screenshot()
        if screen is not None:
            self.screenshot_queue.put((global_index, screen))

    def _get_disc_position(self, position):
        row = position // self.grid_config['cols']
        col = position % self.grid_config['cols']
        click_x = self.grid_config['start_x'] + col * self.grid_config['width']
        click_y = self.grid_config['start_y'] + row * self.grid_config['height']
        return Point(click_x, click_y)


    @node_from(from_name='扫描驱动盘')
    @operation_node(name='保存数据')
    def save_data(self):
        if not self.disc_data_dict:
            return self.round_success('无数据保存')

        # 将字典转换为列表（按 global_index 排序）
        disc_data_list = [self.disc_data_dict[i] for i in sorted(self.disc_data_dict.keys())]

        # 保存到缓存
        cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / 'cache.json'

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(disc_data_list, f, ensure_ascii=False, indent=4)
            log.info(f'数据已缓存到: {cache_file}')
            return self.round_success(f'已缓存 {len(disc_data_list)} 条数据，请在界面预览或导出')
        except Exception as e:
            log.error(f'缓存数据失败: {e}')
            return self.round_fail(f'缓存数据失败: {e}')

    @node_from(from_name='保存数据')
    @operation_node(name='完成后返回')
    def back_at_last(self):
        self.notify_screenshot = self.last_screenshot
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = DriverDiscReadApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
