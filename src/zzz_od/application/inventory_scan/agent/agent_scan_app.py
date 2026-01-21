import cv2
import os
import time
import json
from typing import Optional
import numpy as np
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from one_dragon.utils import cv2_utils, os_utils
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.application.inventory_scan.parser.agent_parser import AgentParser
from zzz_od.application.inventory_scan.screenshot_cache import ScreenshotCache
from cv2.typing import MatLike


class AgentScanApp(ZApplication):

    def __init__(self, ctx: ZContext, screenshot_cache: Optional[ScreenshotCache] = None):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id='agent_scan',
            op_name='角色扫描',
            node_max_retry_times=100000,
        )
        self.screenshot_cache = screenshot_cache
        self.screenshots_dir: Optional[str] = None
        self.screenshot_index: int = 0
        self.scanned_agents: list[dict] = []
        self.parser = AgentParser()

        # 从translation_dict.json读取角色总数，但最大限制为100
        translation_path = os_utils.get_path_under_work_dir('src', 'zzz_od', 'application', 'inventory_scan', 'translation', 'translation_dict.json')
        try:
            with open(translation_path, 'r', encoding='utf-8') as f:
                translation_data = json.load(f)
                character_count = len(translation_data.get('character', {}))
                self.max_agents = min(character_count, 100)  # 最大不超过100
                log.info(f"角色总数: {character_count}, 最大扫描次数: {self.max_agents}")
        except Exception as e:
            log.error(f"读取角色总数失败: {e}，使用默认值100")
            self.max_agents = 100

    @node_from(from_name='扫描角色', status='扫描中')
    @operation_node(name='扫描角色', is_start_node=True)
    def scan_agent(self) -> OperationRoundResult:
        """扫描单个角色"""
        screen = self.last_screenshot

        # 点击"按钮-代理人基础"
        btn_basic = self.ctx.screen_loader.get_area('代理人-信息', '按钮-代理人基础')
        time.sleep(0.2)
        self.ctx.controller.click(btn_basic.center)
        time.sleep(0.3)
        _, screen_basic = self.ctx.controller.screenshot()

        # 检查终止条件：达到最大扫描次数或到达列表末尾
        if self.screenshot_index >= self.max_agents or self._is_end_of_list(screen_basic):
            if self.screenshot_index >= self.max_agents:
                log.info(f"已扫描{self.screenshot_index}个角色，达到最大数量{self.max_agents}")
            else:
                log.info(f"已到达列表末尾，扫描完成。共扫描{self.screenshot_index}个角色")
            return self.round_success('扫描完成')

        # 裁剪3个区域
        area_portrait = self.ctx.screen_loader.get_area('代理人-信息', '代理人-影画')
        area_name = self.ctx.screen_loader.get_area('代理人-信息', '代理人-名称')
        area_level = self.ctx.screen_loader.get_area('代理人-信息', '代理人-等级')

        img_portrait = cv2_utils.crop_image_only(screen_basic, area_portrait.rect)
        img_name = cv2_utils.crop_image_only(screen_basic, area_name.rect)
        img_level = cv2_utils.crop_image_only(screen_basic, area_level.rect)

        # 点击"按钮-代理人技能"
        btn_skill = self.ctx.screen_loader.get_area('代理人-信息', '按钮-代理人技能')
        self.ctx.controller.click(btn_skill.center)
        time.sleep(0.3)
        _, screen_skill = self.ctx.controller.screenshot()

        # 裁剪技能等级区域
        area_skill = self.ctx.screen_loader.get_area('代理人-信息', '代理人-技能等级')
        img_skill = cv2_utils.crop_image_only(screen_skill, area_skill.rect)

        # 点击"按钮-核心技等级"
        btn_core = self.ctx.screen_loader.get_area('代理人-信息', '按钮-核心技等级')
        self.ctx.controller.click(btn_core.center)
        time.sleep(0.3)
        _, screen_core = self.ctx.controller.screenshot()

        # 裁剪核心等级区域
        area_core = self.ctx.screen_loader.get_area('代理人-信息', '代理人-核心等级')
        img_core = cv2_utils.crop_image_only(screen_core, area_core.rect)

        # 点击"按钮-返回"
        btn_back = self.ctx.screen_loader.get_area('代理人-信息', '按钮-返回')
        self.ctx.controller.click(btn_back.center)
        time.sleep(0.3)

        # 上下拼接5个图（使用黑边padding统一宽度）
        images = [img_portrait, img_name, img_level, img_skill, img_core]
        max_width = max(img.shape[1] for img in images)

        padded_images = []
        for img in images:
            if img.shape[1] < max_width:
                pad_left = (max_width - img.shape[1]) // 2
                pad_right = max_width - img.shape[1] - pad_left
                padded = cv2.copyMakeBorder(img, 0, 0, pad_left, pad_right, cv2.BORDER_CONSTANT, value=0)
                padded_images.append(padded)
            else:
                padded_images.append(img)

        combined = np.vstack(padded_images)

        # 保存截图
        self._save_screenshot(combined)

        # 点击"下一位代理人"
        btn_next = self.ctx.screen_loader.get_area('代理人-信息', '按钮-下一位代理人')
        self.ctx.controller.click(btn_next.center)

        return self.round_success('扫描中', wait=0.02)

    def _save_screenshot(self, combined: MatLike):
        """保存拼接后的截图"""
        if self.screenshot_cache is None:
            return

        try:
            # 保存到代理人缓存（调试模式下会同时保存到文件）
            index = self.screenshot_cache.save('agent', combined)
            self.screenshot_index = index + 1
        except Exception as e:
            log.error(f"保存截图失败: {e}")

    def _batch_process_screenshots(self):
        """批量处理所有截图进行OCR和解析"""
        if self.screenshot_cache is None:
            log.error("截图缓存未初始化")
            return

        # 获取所有代理人截图索引
        indices = self.screenshot_cache.get_all_indices('agent')
        total_files = len(indices)

        if total_files == 0:
            log.warning("没有找到任何代理人截图")
            return

        log.info(f"开始批量处理代理人截图，共{total_files}张")

        for idx, index in enumerate(indices, 1):
            try:
                # 从代理人缓存读取截图（先从内存读，没有再从文件读）
                screenshot = self.screenshot_cache.get('agent', index)

                if screenshot is None:
                    log.error(f"读取截图失败(agent-{index})")
                    continue

                # OCR识别
                ocr_result = self.ctx.ocr.run_ocr(screenshot)
                if not ocr_result:
                    log.warning(f"OCR结果为空(agent-{index})")
                    continue

                # 解析数据
                agent_data = self.parser.parse_ocr_result(ocr_result, screenshot)
                if agent_data:
                    self.scanned_agents.append(agent_data)
                    log.info(f"成功解析代理人 {idx}/{total_files}: {agent_data['key']}")
                else:
                    log.error(f"解析失败(agent-{index})")

            except Exception as e:
                log.error(f"处理截图失败(agent-{index}): {e}", exc_info=True)

        log.info(f"批量处理完成，成功解析{len(self.scanned_agents)}个代理人")

    def _is_end_of_list(self, screen: MatLike) -> bool:
        """
        检测是否到达列表末尾（检测标志点是否纯黑色）

        Args:
            screen: 当前截图
        """
        try:
            area = self.ctx.screen_loader.get_area('代理人-信息', '代理人-有无标志')

            # 获取标志点中心位置的颜色
            x, y = int(area.center.x), int(area.center.y)
            pixel = screen[y, x]

            # 转换为HSV并获取V通道值
            pixel_bgr = np.array([[pixel]], dtype=np.uint8)
            pixel_hsv = cv2.cvtColor(pixel_bgr, cv2.COLOR_RGB2HSV)
            v_value = int(pixel_hsv[0, 0, 2])

            # 输出调试信息
            log.info(f"检测标志点位置({x},{y}): RGB={pixel}, V={v_value}")

            # 检测V通道是否小于10
            is_black = v_value < 10

            log.info(f"是否黑色: {is_black} (V<10)")

            return is_black
        except Exception as e:
            log.error(f"检测标志点失败: {e}")
            return False
