import csv
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

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
            need_notify=True,
        )

        self.disc_data_list = []
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

        for i in range(27):
            if self.ctx.run_context.is_context_stop:
                return self.round_wait('停止识别', wait=0)
            if not self._read_and_record_disc(i):
                continue

        while self.current_read_count < self.total_disc_count:
            if self.ctx.run_context.is_context_stop:
                return self.round_wait('停止识别', wait=0)

            scroll_pos = Point(self.grid_config['start_x'], self.grid_config['start_y'] + 3 * self.grid_config['height'])
            self.ctx.controller.click(scroll_pos)
            time.sleep(0.1)

            remaining = self.total_disc_count - self.current_read_count
            read_positions = range(18, 27) if remaining > 9 else range(18, 18 + remaining)

            for i in read_positions:
                if self.ctx.run_context.is_context_stop:
                    return self.round_wait('停止识别', wait=0)
                if not self._read_and_record_disc(i):
                    continue

        log.info(f'扫描完成 共识别:{self.current_read_count}个')
        return self.round_success(f'识别完成: {self.current_read_count}个')

    def _get_disc_position(self, position):
        row = position // self.grid_config['cols']
        col = position % self.grid_config['cols']
        click_x = self.grid_config['start_x'] + col * self.grid_config['width']
        click_y = self.grid_config['start_y'] + row * self.grid_config['height']
        return Point(click_x, click_y)

    def _read_and_record_disc(self, position):
        click_pos = self._get_disc_position(position)
        self.ctx.controller.click(click_pos)
        time.sleep(0.1)

        disc_data = self._read_disc_detail()

        if not disc_data or not disc_data.get('name', '').strip():
            return False

        self.disc_data_list.append(disc_data)
        self.current_read_count += 1
        log.info(f'识别驱动盘 {self.current_read_count}/{self.total_disc_count}: {disc_data.get("name", "未知")}')
        return True

    def _read_disc_detail(self):
        screen_name = '仓库-驱动盘'
        screen = self.screenshot()
        if screen is None:
            return None

        disc_data = {}
        disc_data['name'] = self._ocr_area(screen, screen_name, '驱动盘名称')

        level_text = self._ocr_area(screen, screen_name, '驱动板等级')
        level_match = re.search(r'(\d+)/(\d+)', level_text)
        if level_match:
            disc_data['rating'] = level_match.group(1)
            disc_data['level'] = level_match.group(2)
        else:
            disc_data['rating'] = ''
            disc_data['level'] = level_text

        disc_data['main_stat'] = self._ocr_area(screen, screen_name, '驱动盘主属性')
        disc_data['main_stat_value'] = self._ocr_area(screen, screen_name, '驱动盘主属性值')

        for i in range(1, 5):
            disc_data[f'sub_stat{i}'] = self._ocr_area(screen, screen_name, f'驱动盘副属性{i}')
            sub_value = self._ocr_area(screen, screen_name, f'驱动盘副属性{i}值')
            disc_data[f'sub_stat{i}_value'] = sub_value.strip() if sub_value else ''

        return disc_data

    def _ocr_area(self, screen, screen_name, area_name):
        area = self.ctx.screen_loader.get_area(screen_name, area_name)
        if area is None:
            return ''

        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)

        if ocr_result_map:
            result_text = list(ocr_result_map.keys())[0]
            return result_text.strip()
        return ''

    @node_from(from_name='扫描驱动盘')
    @operation_node(name='保存数据')
    def save_data(self):
        if not self.disc_data_list:
            return self.round_success('无数据保存')

        output_dir = Path(os_utils.get_path_under_work_dir('config', 'driver_disc_data'))
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = output_dir / f'driver_disc_{timestamp}.csv'

        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['name', 'level', 'rating', 'main_stat', 'main_stat_value',
                          'sub_stat1', 'sub_stat1_value', 'sub_stat2', 'sub_stat2_value',
                          'sub_stat3', 'sub_stat3_value', 'sub_stat4', 'sub_stat4_value']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow({'name': '驱动盘名称', 'level': '等级', 'rating': '评级',
                             'main_stat': '主属性', 'main_stat_value': '主属性值',
                             'sub_stat1': '副属性1', 'sub_stat1_value': '副属性1值',
                             'sub_stat2': '副属性2', 'sub_stat2_value': '副属性2值',
                             'sub_stat3': '副属性3', 'sub_stat3_value': '副属性3值',
                             'sub_stat4': '副属性4', 'sub_stat4_value': '副属性4值'})
            writer.writerows(self.disc_data_list)

        log.info(f'数据已保存到: {csv_file}')
        return self.round_success(f'已保存 {len(self.disc_data_list)} 条数据')

    @node_from(from_name='保存数据')
    @operation_node(name='完成后返回')
    def back_at_last(self):
        self.notify_screenshot = self.save_screenshot_bytes()
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
