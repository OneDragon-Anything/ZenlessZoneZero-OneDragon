import csv
import re
import threading
import time
import multiprocessing
from datetime import datetime
from pathlib import Path
from queue import Empty
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


# ============ 多进程 Worker 函数（必须在模块级） ============

def _ocr_worker_process(
    worker_id: int,
    screenshot_queue: multiprocessing.Queue,
    result_queue: multiprocessing.Queue,
    ready_queue: multiprocessing.Queue,  # 就绪信号队列
    warmup_queue: multiprocessing.Queue,  # 预热完成信号队列
    ocr_areas: Dict[str, tuple],  # {area_name: (x, y, w, h)}
    use_gpu: bool,
    det_limit_side_len: int,
    batch_size: int  # 批量大小
):
    """
    OCR Worker 进程函数（支持批量推理）
    每个进程独立创建 OCR 实例，避免 DirectML 内存冲突
    """
    try:
        # 在进程内创建独立的 OCR 实例
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher, OnnxOcrParam

        worker_ocr = OnnxOcrMatcher(
            OnnxOcrParam(
                det_limit_side_len=det_limit_side_len,
                use_gpu=use_gpu,
            )
        )

        log.info(f'Worker-{worker_id} OCR 实例创建完成（进程 PID: {multiprocessing.current_process().pid}），批量大小: {batch_size}')

        # 发送就绪信号
        ready_queue.put(worker_id)

        # 创建一个小的测试图像用于预热（200x300 像素的白色背景）
        warmup_image = np.ones((200, 300, 3), dtype=np.uint8) * 255

        for warmup_round in range(2):
            try:
                _ = worker_ocr.run_ocr(warmup_image)
            except Exception as e:
                log.warning(f'Worker-{worker_id} 预热第 {warmup_round + 1} 次出错: {e}')

        log.info(f'Worker-{worker_id} OCR 模型预热完成')

        # 发送预热完成信号
        warmup_queue.put(worker_id)

        while True:
            # 批量取出截图
            batch = []
            try:
                # 至少取1个，最多取batch_size个
                for _ in range(batch_size):
                    try:
                        item = screenshot_queue.get(timeout=0.1)
                        if item is None:  # 停止信号
                            log.info(f'Worker-{worker_id} 收到停止信号')
                            # 处理完当前batch后退出
                            if batch:
                                break
                            else:
                                return
                        batch.append(item)
                    except Empty:
                        # 队列空了，处理已有的batch
                        break
                
                if not batch:
                    # 没有任务，继续等待
                    continue

                # 按区域类型分组：{area_name: [(global_index, crop_image), ...]}
                area_groups = {}
                for global_index, screen in batch:
                    for area_name, rect_tuple in ocr_areas.items():
                        x, y, w, h = rect_tuple
                        part = screen[y:y+h, x:x+w]
                        if area_name not in area_groups:
                            area_groups[area_name] = []
                        area_groups[area_name].append((global_index, part))

                # 对每个区域类型进行批量OCR
                # 存储所有结果：{global_index: {area_name: result_text}}
                all_results = {global_index: {} for global_index, _ in batch}

                for area_name, items in area_groups.items():
                    indices = [idx for idx, _ in items]
                    images = [img for _, img in items]

                    # 批量OCR识别
                    try:
                        # 直接调用底层text_recognizer进行批量推理
                        # 因为图片已经预裁剪到精确区域，不需要文本检测
                        rec_results = worker_ocr._model.text_recognizer(images)
                        
                        for idx, (text, score) in zip(indices, rec_results):
                            all_results[idx][area_name] = text.strip()
                    except Exception as e:
                        # 降级：批量调用失败时逐个处理
                        log.warning(f'批量OCR识别失败，降级为逐个处理: {e}')
                        for idx, img in zip(indices, images):
                            ocr_result_map = worker_ocr.run_ocr(img)
                            if ocr_result_map:
                                result_text = list(ocr_result_map.keys())[0].strip()
                            else:
                                result_text = ''
                            all_results[idx][area_name] = result_text
                        # 填充空结果
                        for idx in indices:
                            all_results[idx][area_name] = ''

                # 解析并返回结果
                for global_index in all_results.keys():
                    disc_data = all_results[global_index]
                    
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

                    # 将结果放入结果队列
                    result_queue.put((global_index, disc_data))

            except Exception as e:
                log.error(f'Worker-{worker_id} 批量处理异常: {e}', exc_info=True)
                # 对batch中所有任务返回None
                for global_index, _ in batch:
                    result_queue.put((global_index, None))

        log.info(f'Worker-{worker_id} 进程退出')

    except Exception as e:
        log.error(f'Worker-{worker_id} 初始化失败: {e}', exc_info=True)


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

        # 多进程相关
        self.screenshot_queue = multiprocessing.Queue(maxsize=10)
        self.result_queue = multiprocessing.Queue()
        self.ready_queue = multiprocessing.Queue()  # 用于接收 worker 就绪信号
        self.warmup_queue = multiprocessing.Queue()  # 用于接收 worker 预热完成信号
        self.worker_count = self.ctx.model_config.ocr_worker_count
        self.workers = []  # 存储 Process 对象
        self.workers_running = False
        self.ocr_areas = {}  # 预提取的 OCR 区域坐标
        self.collector_thread: Optional[threading.Thread] = None

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
        log.info(f'开始扫描驱动盘 总数:{self.total_disc_count} Worker进程数:{self.worker_count}')

        # 启动 worker 进程
        self._start_workers()

        # 启动结果收集线程
        self.collector_thread = threading.Thread(target=self._result_collector_thread, daemon=True)
        self.collector_thread.start()

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
            self._wait_collector_thread()

        log.info(f'扫描完成 共识别:{len(self.disc_data_dict)}个')
        return self.round_success(f'识别完成: {len(self.disc_data_dict)}个')

    def _start_workers(self):
        """启动 worker 进程（GPU 多进程）"""
        self.workers_running = True
        self.workers = []

        # 预提取所有 OCR 区域坐标（传递给子进程）
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

        log.info(f'正在启动 {self.worker_count} 个 OCR worker 进程（GPU 多进程）...')

        det_limit_side_len = max(
            self.ctx.project_config.screen_standard_width,
            self.ctx.project_config.screen_standard_height
        )

        for i in range(self.worker_count):
            # 启动 worker 进程
            worker = multiprocessing.Process(
                target=_ocr_worker_process,
                args=(
                    i,
                    self.screenshot_queue,
                    self.result_queue,
                    self.ready_queue,  # 传递就绪信号队列
                    self.warmup_queue,  # 传递预热完成信号队列
                    self.ocr_areas,
                    self.ctx.model_config.ocr_gpu,
                    det_limit_side_len,
                    self.ctx.model_config.ocr_batch_size  # 传递批量大小
                ),
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

        # 等待所有 worker 进程就绪（OCR 实例创建完成）
        ready_count = 0
        log.info(f'等待 {self.worker_count} 个 worker 进程就绪...')
        while ready_count < self.worker_count:
            try:
                worker_id = self.ready_queue.get(timeout=30)  # 最多等待 30 秒
                ready_count += 1
                log.info(f'Worker-{worker_id} 已就绪 ({ready_count}/{self.worker_count})')
            except Empty:
                log.error(f'等待 worker 进程就绪超时，已就绪: {ready_count}/{self.worker_count}')
                break

        if ready_count == self.worker_count:
            log.info(f'所有 {self.worker_count} 个 OCR worker 进程已就绪')
        else:
            log.warning(f'只有 {ready_count}/{self.worker_count} 个进程就绪')
            return

        # 等待所有 worker 进程预热完成
        warmup_count = 0
        log.info(f'等待 {self.worker_count} 个 worker 进程预热完成...')
        while warmup_count < self.worker_count:
            try:
                worker_id = self.warmup_queue.get(timeout=60)  # 预热可能需要更长时间
                warmup_count += 1
                log.info(f'Worker-{worker_id} 预热完成 ({warmup_count}/{self.worker_count})')
            except Empty:
                log.error(f'等待 worker 进程预热超时，已完成: {warmup_count}/{self.worker_count}')
                break

        if warmup_count == self.worker_count:
            log.info(f'所有 {self.worker_count} 个 OCR worker 进程预热完成，开始扫描')
        else:
            log.warning(f'只有 {warmup_count}/{self.worker_count} 个进程完成预热')

    def _stop_workers(self):
        """停止 worker 进程"""
        if not self.workers_running:
            return

        # 发送停止信号（None sentinel）给每个 worker
        for _ in range(self.worker_count):
            self.screenshot_queue.put(None)

        # 等待所有进程结束
        for worker in self.workers:
            worker.join(timeout=3)
            if worker.is_alive():
                log.warning(f'Worker 进程 {worker.pid} 未能正常退出，强制终止')
                worker.terminate()

        # 所有 worker 已停止，通知结果收集线程
        self.result_queue.put(None)
        self.workers_running = False

        log.info('所有 worker 进程已停止')

    def _wait_collector_thread(self):
        """等待结果收集线程结束"""
        if self.collector_thread and self.collector_thread.is_alive():
            self.collector_thread.join(timeout=5)
            if self.collector_thread.is_alive():
                log.warning('结果收集线程未在预期时间内退出')
        self.collector_thread = None

    def _result_collector_thread(self):
        """结果收集线程：从 result_queue 收集 worker 进程的识别结果"""
        log.info('结果收集线程已启动')
        while self.workers_running or not self.result_queue.empty():
            try:
                result = self.result_queue.get(timeout=0.5)

                if result is None:  # 停止信号
                    break

                global_index, disc_data = result

                if disc_data:
                    # 解析区域名称到字段映射（level 和 rating 已经在 worker 中解析好了）
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
                        log.warning(f'未识别到驱动盘 [{global_index}]')
                else:
                    log.warning(f'驱动盘识别失败 [{global_index}]')

            except Empty:
                continue
            except Exception as e:
                log.error(f'结果收集异常: {e}', exc_info=True)

        log.info('结果收集线程已退出')

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

        # 从配置读取导出路径
        export_path = self.ctx.one_dragon_config.get('disc_export_path', '')
        
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 解析导出路径，支持相对/绝对路径以及文件/目录两种写法
        if export_path:
            user_path = Path(export_path)
            if not user_path.is_absolute():
                user_path = Path(os_utils.get_work_dir()) / user_path

            if user_path.suffix:  # 指定了文件名
                base_dir = user_path.parent
                file_stem = user_path.stem
                file_suffix = user_path.suffix
            else:  # 指定的是目录
                base_dir = user_path
                file_stem = 'driver_disc_data'
                file_suffix = '.csv'
        else:
            base_dir = Path(os_utils.get_path_under_work_dir('driver_disc'))
            file_stem = 'driver_disc_data'
            file_suffix = '.csv'

        csv_file = base_dir / f'{file_stem}_{timestamp}{file_suffix}'

        # 确保目录存在
        base_dir.mkdir(parents=True, exist_ok=True)

        # 重试写入（防止文件被占用）
        max_retries = 5
        for attempt in range(max_retries):
            try:
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
                return self.round_success(f'已保存 {len(disc_data_list)} 条数据到 {csv_file}')
                
            except PermissionError as e:
                if attempt < max_retries - 1:
                    # 尝试生成新的文件名
                    timestamp_new = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 添加毫秒
                    csv_file = base_dir / f'{file_stem}_{timestamp_new}{file_suffix}'
                    log.warning(f'文件被占用，尝试新文件名: {csv_file}')
                    time.sleep(0.1)
                else:
                    log.error(f'无法保存文件（已尝试 {max_retries} 次），请关闭可能占用文件的程序（如 Excel）')
                    return self.round_fail(f'保存失败: 文件被占用，请关闭 {csv_file.name} 后重试')

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
