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
from zzz_od.application.driver_disc_read.driver_disc_parser import DriverDiscParser
from zzz_od.application.driver_disc_read.drive_disk_exporter import DriveDiskExporter


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
        self.parser = DriverDiscParser()
        self.exporter = DriveDiskExporter()

    @operation_node(name='路由', is_start_node=True)
    def router(self):
        op_type = getattr(self.ctx, 'driver_disc_op_type', 'scan')
        log.info(f'驱动盘识别操作类型: {op_type}')
        return self.round_success(status=op_type)

    @node_from(from_name='路由', status='scan')
    @operation_node(name='开始前返回')
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

        # 初步清洗：解析名称和位置
        raw_name = disc_data.get('驱动盘名称', '')
        name = raw_name
        slot = ''
        # 尝试匹配 [1] 或 【1】 格式
        match = re.search(r'(.+?)[\[【](\d)[\]】]?', raw_name)
        if match:
            name = match.group(1).strip()
            slot = match.group(2)
        else:
            # 兜底：如果最后一位是数字，且前面是中文
            match = re.search(r'(.+?)(\d)$', raw_name)
            if match:
                name = match.group(1).strip()
                slot = match.group(2)

        # 初步清洗：副属性去除 "套装效果"
        substats_data = {}
        for i in range(1, 5):
            k_name = f'驱动盘副属性{i}'
            k_val = f'驱动盘副属性{i}值'
            s_name = disc_data.get(k_name, '')
            s_val = disc_data.get(k_val, '')
            
            if '套装' in s_name:
                s_name = ''
                s_val = ''
            
            substats_data[f'sub_stat{i}'] = s_name
            substats_data[f'sub_stat{i}_value'] = s_val

        # 解析区域名称到字段映射
        parsed_data = {
            'name': name,
            'slot': slot,
            'level': disc_data.get('level', ''),
            'rating': disc_data.get('rating', ''),
            'main_stat': disc_data.get('驱动盘主属性', ''),
            'main_stat_value': disc_data.get('驱动盘主属性值', ''),
            **substats_data
        }

        if parsed_data['name'].strip():
            self.disc_data_dict[global_index] = parsed_data
            log.info(f'识别完成 [{len(self.disc_data_dict)}/{self.total_disc_count}]: {parsed_data["name"]} {parsed_data["slot"]}')
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
            
            # 备份到 history
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            history_dir = cache_dir / 'history'
            history_dir.mkdir(parents=True, exist_ok=True)
            history_file = history_dir / f'scan_{timestamp}.json'
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(disc_data_list, f, ensure_ascii=False, indent=4)

            log.info(f'数据已缓存到: {cache_file}, 备份: {history_file.name}')
            return self.round_success(f'已缓存 {len(disc_data_list)} 条数据，备份已保存')
        except Exception as e:
            log.error(f'缓存数据失败: {e}')
            return self.round_fail(f'缓存数据失败: {e}')

    @node_from(from_name='保存数据')
    @operation_node(name='完成后返回')
    def back_at_last(self):
        self.notify_screenshot = self.last_screenshot
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='路由', status='import')
    @operation_node(name='导入CSV')
    def import_csv(self):
        """
        从 import 目录导入 CSV 文件到缓存
        """
        import_dir = Path(os_utils.get_path_under_work_dir('import'))
        import_file = import_dir / 'driver_disc.csv'

        if not import_file.exists():
            return self.round_fail(f'未找到导入文件: {import_file.name}，请将文件放入 import 目录')

        try:
            data_list = []
            with open(import_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data_list.append(dict(row))
            
            if not data_list:
                return self.round_fail('CSV文件为空')

            # 保存到缓存
            cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / 'cache.json'
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data_list, f, ensure_ascii=False, indent=4)
            
            # 备份一份到 history
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            history_dir = cache_dir / 'history'
            history_dir.mkdir(parents=True, exist_ok=True)
            history_file = history_dir / f'import_{timestamp}.json'
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(data_list, f, ensure_ascii=False, indent=4)

            return self.round_success(f'已导入 {len(data_list)} 条数据')
        except Exception as e:
            return self.round_fail(f'导入失败: {e}')

    @node_from(from_name='路由', status='clean')
    @operation_node(name='数据清洗')
    def clean_data(self):
        """
        读取缓存数据，进行清洗和校验，并保存回缓存（保持扁平结构）
        """
        cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
        cache_file = cache_dir / 'cache.json'

        if not cache_file.exists():
            return self.round_fail('未找到缓存文件，请先运行识别或导入')

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                raw_data_list = json.load(f)
            
            # 备份原始数据
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            history_dir = cache_dir / 'history'
            history_dir.mkdir(parents=True, exist_ok=True)
            backup_file = history_dir / f'pre_clean_{timestamp}.json'
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(raw_data_list, f, ensure_ascii=False, indent=4)

        except Exception as e:
            return self.round_fail(f'读取缓存失败: {e}')

        cleaned_data = []
        
        for raw_item in raw_data_list:
            # 使用 parse_flat 保持扁平结构
            parsed = self.parser.parse_flat(raw_item)
            cleaned_data.append(parsed)

        # 保存回缓存
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=4)

        return self.round_success(f'清洗完成，已更新 {len(cleaned_data)} 条数据')

    @node_from(from_name='路由', status='export_csv')
    @operation_node(name='导出CSV')
    def export_csv(self):
        """
        导出当前缓存数据为 CSV 格式
        """
        cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
        cache_file = cache_dir / 'cache.json'

        if not cache_file.exists():
            return self.round_fail('未找到缓存文件')

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data_list = json.load(f)
            
            if not data_list:
                return self.round_fail('缓存数据为空')

            export_dir = Path(os_utils.get_path_under_work_dir('export'))
            export_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_file = export_dir / f'driver_disc_{timestamp}.csv'

            # 获取所有可能的字段名作为表头
            fieldnames = set()
            for item in data_list:
                fieldnames.update(item.keys())
            
            # 排序字段：name, slot, level, rating, main_stat...
            sorted_fields = ['name', 'slot', 'level', 'rating', 'main_stat', 'main_stat_value']
            other_fields = sorted(list(fieldnames - set(sorted_fields)))
            fieldnames = sorted_fields + other_fields

            with open(export_file, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data_list)

            return self.round_success(f'CSV已导出至: {export_file.name}')
        except Exception as e:
            return self.round_fail(f'导出CSV失败: {e}')

    @node_from(from_name='路由', status='export_zod')
    @operation_node(name='导出ZOD格式')
    def export_zod_data(self):
        """
        将当前缓存数据导出为 ZOD 格式
        """
        cache_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
        cache_file = cache_dir / 'cache.json'

        if not cache_file.exists():
            return self.round_fail('未找到缓存数据')

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                flat_data_list = json.load(f)
            
            # 先转换为嵌套结构，再导出
            nested_data_list = [self.parser.parse(item) for item in flat_data_list]
            zod_data = self.exporter.convert_to_zod_json(nested_data_list)
            
            export_dir = Path(os_utils.get_path_under_work_dir('export'))
            export_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_file = export_dir / f'driver_disc_zod_{timestamp}.json'
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(zod_data, f, ensure_ascii=False, indent=4)
                
            return self.round_success(f'ZOD格式数据已导出至: {export_file.name}')
        except Exception as e:
            return self.round_fail(f'导出失败: {e}')


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = DriverDiscReadApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
