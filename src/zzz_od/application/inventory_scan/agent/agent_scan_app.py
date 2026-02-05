import cv2
import time
import json
from typing import Optional, TYPE_CHECKING
import numpy as np
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

if TYPE_CHECKING:
    from zzz_od.application.inventory_scan.ocr_worker import OcrWorker


class AgentScanApp(ZApplication):

    def __init__(self, ctx: ZContext, screenshot_cache: Optional[ScreenshotCache] = None,
                 ocr_worker: Optional["OcrWorker"] = None):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id='agent_scan',
            op_name='角色扫描',
        )
        self.screenshot_cache = screenshot_cache
        self.ocr_worker = ocr_worker
        self.screenshots_dir: Optional[str] = None
        self.screenshot_index: int = 0
        self.parser = AgentParser()

        # 临时存储当前角色的截图片段
        self._img_portrait: Optional[MatLike] = None  # 影画
        self._img_name: Optional[MatLike] = None      # 名称
        self._img_level: Optional[MatLike] = None     # 等级
        self._img_skill: Optional[MatLike] = None     # 技能等级
        self._img_core: Optional[MatLike] = None      # 核心等级

        # 点击限流：记录上次点击时间
        self._last_click_time: float = 0

        # 从翻译字典读取角色总数，但最大限制为100
        # 只读取 config/zzz_translation.json（本项目只有这一份字典，预置内容也在这里）
        user_translation_path = os_utils.get_path_under_work_dir('config', 'zzz_translation.json')
        try:
            with open(user_translation_path, 'r', encoding='utf-8') as f:
                translation_data = json.load(f)
                character_count = len(translation_data.get('character', {}))
                self.max_agents = min(character_count, 100)  # 最大不超过100
                log.info(f"角色总数: {character_count}, 最大扫描次数: {self.max_agents}")
        except Exception as e:
            log.error(f"读取角色总数失败: {e}，使用默认值100")
            self.max_agents = 100

    @node_from(from_name='下一位代理人')
    @operation_node(name='进入基础页面', is_start_node=True, node_max_retry_times=30)
    def enter_basic_page(self) -> OperationRoundResult:
        """
        点击基础按钮并等待页面加载完成
        同时检测是否到达列表末尾（没有角色）
        """
        # 点击基础按钮
        btn = self.ctx.screen_loader.get_area('代理人-信息', '按钮-代理人基础')
        self.ctx.controller.click(btn.center)

        # 等待后截图检测
        time.sleep(0.3)
        _, screen = self.ctx.controller.screenshot()

        # 检测是否达到最大扫描次数
        if self.screenshot_index >= self.max_agents:
            log.info(f"已扫描{self.screenshot_index}个角色，达到最大数量{self.max_agents}")
            return self.round_success('扫描完成')

        # 检测是否到达列表末尾（标志点全黑 = 没有角色）
        if self._is_end_of_list(screen):
            log.info(f"已到达列表末尾，扫描完成。共扫描{self.screenshot_index}个角色")
            return self.round_success('扫描完成')

        # 检测按钮是否变为彩色（加载完成）
        if self._is_button_colorful(screen, '代理人-信息', '按钮-代理人基础'):
            return self.round_success('继续扫描')

        return self.round_retry(wait=0.1)

    @node_from(from_name='进入基础页面', status='继续扫描')
    @operation_node(name='截图基础信息')
    def capture_basic_info(self) -> OperationRoundResult:
        """
        裁剪影画、名称、等级区域
        """
        # 重置临时截图变量
        self._reset_temp_images()

        _, screen = self.ctx.controller.screenshot()

        area_portrait = self.ctx.screen_loader.get_area('代理人-信息', '代理人-影画')
        area_name = self.ctx.screen_loader.get_area('代理人-信息', '代理人-名称')
        area_level = self.ctx.screen_loader.get_area('代理人-信息', '代理人-等级')

        self._img_portrait = cv2_utils.crop_image_only(screen, area_portrait.rect)
        self._img_name = cv2_utils.crop_image_only(screen, area_name.rect)
        self._img_level = cv2_utils.crop_image_only(screen, area_level.rect)

        return self.round_success()

    @node_from(from_name='截图基础信息')
    @operation_node(name='进入技能页面', node_max_retry_times=30)
    def enter_skill_page(self) -> OperationRoundResult:
        """
        点击技能按钮并等待页面加载完成
        """
        # 点击技能按钮
        btn = self.ctx.screen_loader.get_area('代理人-信息', '按钮-代理人技能')
        self.ctx.controller.click(btn.center)

        # 等待后截图检测
        time.sleep(0.1)
        _, screen = self.ctx.controller.screenshot()

        # 检测按钮是否变为彩色（加载完成）
        if self._is_button_colorful(screen, '代理人-信息', '按钮-代理人技能'):
            return self.round_success()

        return self.round_retry(wait=0.1)

    @node_from(from_name='进入技能页面')
    @operation_node(name='截图技能信息')
    def capture_skill_info(self) -> OperationRoundResult:
        """
        裁剪技能等级区域
        """
        _, screen = self.ctx.controller.screenshot()

        area_skill = self.ctx.screen_loader.get_area('代理人-信息', '代理人-技能等级')
        self._img_skill = cv2_utils.crop_image_only(screen, area_skill.rect)

        return self.round_success()

    @node_from(from_name='截图技能信息')
    @operation_node(name='进入核心页面', node_max_retry_times=30)
    def enter_core_page(self) -> OperationRoundResult:
        """
        点击核心技等级按钮并等待页面加载完成
        """
        # 点击核心按钮
        btn = self.ctx.screen_loader.get_area('代理人-信息', '按钮-核心技等级')
        self.ctx.controller.click(btn.center)

        # 等待后截图检测
        time.sleep(0.1)
        _, screen = self.ctx.controller.screenshot()

        # 检测街区按钮是否全黑（核心页面加载完成）
        if self._is_area_black(screen, '代理人-信息', '按钮-街区'):
            return self.round_success()

        return self.round_retry(wait=0.1)

    @node_from(from_name='进入核心页面')
    @operation_node(name='截图核心信息')
    def capture_core_info(self) -> OperationRoundResult:
        """
        裁剪核心等级区域
        """
        _, screen = self.ctx.controller.screenshot()

        area_core = self.ctx.screen_loader.get_area('代理人-信息', '代理人-核心等级')
        self._img_core = cv2_utils.crop_image_only(screen, area_core.rect)

        return self.round_success()

    @node_from(from_name='截图核心信息')
    @operation_node(name='返回并保存', node_max_retry_times=50)
    def return_and_save(self) -> OperationRoundResult:
        """
        点击返回按钮，等待返回成功后拼接并保存截图
        点击限流：最多1秒点击一次，检测实时进行
        """
        current_time = time.time()

        # 距离上次点击超过1秒才点击
        if current_time - self._last_click_time >= 1:
            btn_back = self.ctx.screen_loader.get_area('代理人-信息', '按钮-返回')
            self.ctx.controller.click(btn_back.center)
            self._last_click_time = current_time

        # 等待后截图检测
        time.sleep(0.1)
        _, screen = self.ctx.controller.screenshot()

        # 检测街区按钮是否不全黑（返回成功）
        if not self._is_area_black(screen, '代理人-信息', '按钮-街区'):
            self._last_click_time = 0  # 成功后清空
            # 拼接并保存截图
            self._combine_and_save()
            return self.round_success()

        return self.round_retry(wait=0.1)

    @node_from(from_name='返回并保存')
    @operation_node(name='下一位代理人')
    def next_agent(self) -> OperationRoundResult:
        """
        点击下一位代理人按钮
        """
        btn_next = self.ctx.screen_loader.get_area('代理人-信息', '按钮-下一位代理人')
        self.ctx.controller.click(btn_next.center)

        return self.round_success(wait=0.3)

    # ==================== 辅助方法 ====================

    def _reset_temp_images(self):
        """重置临时截图变量"""
        self._img_portrait = None
        self._img_name = None
        self._img_level = None
        self._img_skill = None
        self._img_core = None

    def _is_button_colorful(self, screen: MatLike, screen_name: str, area_name: str) -> bool:
        """
        检测按钮区域是否出现彩色（中间40%区域）
        用于判断基础/技能页面是否加载完成

        Args:
            screen: 当前截图
            screen_name: 画面名称
            area_name: 区域名称

        Returns:
            True 如果区域出现彩色（S通道均值>20），False 否则
        """
        try:
            area = self.ctx.screen_loader.get_area(screen_name, area_name)

            # 获取区域图像
            x1, y1 = int(area.rect.x1), int(area.rect.y1)
            x2, y2 = int(area.rect.x2), int(area.rect.y2)
            region = screen[y1:y2, x1:x2]

            # 左右各裁剪30%，只检测中间40%
            width = region.shape[1]
            crop_left = int(width * 0.3)
            crop_right = int(width * 0.7)
            region = region[:, crop_left:crop_right]

            # 转换为HSV
            region_hsv = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)

            # 计算S通道（饱和度）的平均值
            avg_s = float(region_hsv[:, :, 1].mean())

            # 检测平均S通道是否大于20（有彩色）
            is_colorful = avg_s > 20

            log.debug(f"检测区域 {area_name} 平均S值={avg_s:.1f}, 是否彩色={is_colorful}")

            return is_colorful
        except Exception as e:
            log.error(f"检测按钮彩色失败: {e}")
            return False

    def _combine_and_save(self):
        """拼接5张截图并保存"""
        images = [
            self._img_portrait,
            self._img_name,
            self._img_level,
            self._img_skill,
            self._img_core
        ]

        # 检查是否有缺失的截图
        if any(img is None for img in images):
            log.error("截图不完整，无法拼接保存")
            return

        # 上下拼接（使用黑边padding统一宽度）
        max_width = max(img.shape[1] for img in images)

        padded_images = []
        for img in images:
            if img.shape[1] < max_width:
                pad_left = (max_width - img.shape[1]) // 2
                pad_right = max_width - img.shape[1] - pad_left
                padded = cv2.copyMakeBorder(
                    img, 0, 0, pad_left, pad_right,
                    cv2.BORDER_CONSTANT, value=0
                )
                padded_images.append(padded)
            else:
                padded_images.append(img)

        combined = np.vstack(padded_images)

        # 保存截图
        self._save_screenshot(combined)

    def _save_screenshot(self, combined: MatLike):
        """保存拼接后的截图并提交OCR任务"""
        if self.screenshot_cache is None:
            return

        try:
            # 保存到代理人缓存（调试模式下会同时保存到文件）
            index = self.screenshot_cache.save('agent', combined)
            self.screenshot_index = index + 1

            # 提交OCR任务（异步处理）
            if self.ocr_worker is not None:
                self.ocr_worker.submit('agent', combined, self.parser)
        except Exception as e:
            log.error(f"保存截图失败: {e}")

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

    def _is_area_black(self, screen: MatLike, screen_name: str, area_name: str) -> bool:
        """
        检测指定区域是否全黑（通过计算区域平均亮度）

        Args:
            screen: 当前截图
            screen_name: 画面名称
            area_name: 区域名称

        Returns:
            True 如果区域全黑（平均亮度<10），False 否则
        """
        try:
            area = self.ctx.screen_loader.get_area(screen_name, area_name)

            # 获取整个区域的图像
            x1, y1 = int(area.rect.x1), int(area.rect.y1)
            x2, y2 = int(area.rect.x2), int(area.rect.y2)
            region = screen[y1:y2, x1:x2]

            # 转换为HSV
            region_hsv = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)

            # 计算V通道的平均值
            avg_v = int(region_hsv[:, :, 2].mean())

            # 检测平均V通道是否小于10（全黑）
            is_black = avg_v < 10

            log.debug(f"检测区域 {area_name} 平均V值={avg_v}, 是否黑色={is_black}")

            return is_black
        except Exception as e:
            log.error(f"检测区域黑色失败: {e}")
            return False
