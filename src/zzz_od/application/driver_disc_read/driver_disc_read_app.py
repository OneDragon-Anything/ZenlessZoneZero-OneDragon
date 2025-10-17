import csv
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
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

        # 多线程相关
        self.screenshot_queue = Queue(maxsize=10)
        self.worker_count = self.ctx.model_config.ocr_worker_count
        self.workers = []
        self.workers_running = False
        self.ocr_lock = threading.Lock()  # OCR 调用锁，确保线程安全

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
        log.info(f'开始扫描驱动盘 总数:{self.total_disc_count} Worker线程数:{self.worker_count}')

        # 启动 worker 线程
        self._start_workers()

        try:
            global_index = 0

            # 第一屏（前 27 个）
            for i in range(27):
                if self.ctx.run_context.is_context_stop:
                    return self.round_wait('停止识别', wait=0)
                self._capture_and_queue_disc(i, global_index)
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
                    self._capture_and_queue_disc(grid_pos, global_index)
                    global_index += 1

        finally:
            # 停止 worker 线程
            self._stop_workers()

        log.info(f'扫描完成 共识别:{len(self.disc_data_dict)}个')
        return self.round_success(f'识别完成: {len(self.disc_data_dict)}个')

    def _start_workers(self):
        """启动 worker 线程"""
        self.workers_running = True
        self.workers = []
        for i in range(self.worker_count):
            worker = threading.Thread(target=self._worker_thread, args=(i,), daemon=True)
            worker.start()
            self.workers.append(worker)
        log.info(f'已启动 {self.worker_count} 个 OCR worker 线程')

    def _stop_workers(self):
        """停止 worker 线程"""
        self.workers_running = False
        # 等待队列清空
        self.screenshot_queue.join()
        # 等待所有线程结束
        for worker in self.workers:
            worker.join(timeout=2)
        log.info('所有 worker 线程已停止')

    def _worker_thread(self, worker_id: int):
        """Worker 线程：从队列获取截图并进行 OCR 识别"""
        log.info(f'Worker-{worker_id} 已启动')
        while self.workers_running or not self.screenshot_queue.empty():
            try:
                # 获取任务（超时 0.5 秒）
                task = self.screenshot_queue.get(timeout=0.5)
                
                try:
                    global_index, screen = task

                    # OCR 识别
                    disc_data = self._read_disc_detail(screen)

                    if disc_data and disc_data.get('name', '').strip():
                        self.disc_data_dict[global_index] = disc_data
                        log.info(f'Worker-{worker_id} 识别完成 [{len(self.disc_data_dict)}/{self.total_disc_count}]: {disc_data.get("name", "未知")}')
                    else:
                        log.warning(f'Worker-{worker_id} 未识别到驱动盘 [{global_index}]')

                except Exception as e:
                    log.error(f'Worker-{worker_id} OCR处理出错 [{global_index}]: {e}', exc_info=True)
                
                finally:
                    # 无论成功失败，都标记任务完成
                    self.screenshot_queue.task_done()

            except Empty:
                # 队列超时，正常情况，继续循环
                continue
            except Exception as e:
                log.error(f'Worker-{worker_id} 未知错误: {e}', exc_info=True)
                continue

        log.info(f'Worker-{worker_id} 已退出')

    def _capture_and_queue_disc(self, grid_position: int, global_index: int):
        """点击位置、截图并放入队列"""
        click_pos = self._get_disc_position(grid_position)
        self.ctx.controller.click(click_pos)
        time.sleep(0.03)

        screen = self.screenshot()
        if screen is not None:
            self.screenshot_queue.put((global_index, screen))

    def _get_disc_position(self, position):
        row = position // self.grid_config['cols']
        col = position % self.grid_config['cols']
        click_x = self.grid_config['start_x'] + col * self.grid_config['width']
        click_y = self.grid_config['start_y'] + row * self.grid_config['height']
        return Point(click_x, click_y)

    def _read_disc_detail(self, screen: MatLike):
        """从截图中识别驱动盘详情"""
        screen_name = '仓库-驱动盘'
        if screen is None:
            return None

        try:
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
        except Exception as e:
            log.error(f'读取驱动盘详情出错: {e}', exc_info=True)
            return None

    def _ocr_area(self, screen, screen_name, area_name):
        """OCR 识别指定区域（线程安全）"""
        try:
            area = self.ctx.screen_loader.get_area(screen_name, area_name)
            if area is None:
                return ''

            part = cv2_utils.crop_image_only(screen, area.rect)
            
            # 使用锁保护 OCR 调用，确保线程安全
            with self.ocr_lock:
                ocr_result_map = self.ctx.ocr.run_ocr(part)

            if ocr_result_map:
                result_text = list(ocr_result_map.keys())[0]
                return result_text.strip()
            return ''
        except Exception as e:
            log.error(f'OCR识别区域 [{area_name}] 出错: {e}', exc_info=True)
            return ''

    @node_from(from_name='扫描驱动盘')
    @operation_node(name='保存数据')
    def save_data(self):
        if not self.disc_data_dict:
            return self.round_success('无数据保存')

        # 将字典转换为列表（按 global_index 排序）
        disc_data_list = [self.disc_data_dict[i] for i in sorted(self.disc_data_dict.keys())]

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
            writer.writerows(disc_data_list)

        log.info(f'数据已保存到: {csv_file}')
        return self.round_success(f'已保存 {len(disc_data_list)} 条数据')

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
