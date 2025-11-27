import time

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.suibian_temple.operations.suibian_temple_adventure_dispatch import (
    SuibianTempleAdventureDispatch,
    SuibianTempleAdventureDispatchDuration,
)
from zzz_od.application.suibian_temple.operations.suibian_temple_craft_dispatch import SuibianTempleCraftDispatch
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class RegularProcurementPos:

    def __init__(self, name: str, pos: Rect):
        self.name = name
        self.pos = pos


class SuibianTempleYumChaSin(ZOperation):

    def __init__(self, ctx: ZContext, submit_only: bool = False):
        """
        随便观 - 饮茶仙

        需要在随便观主界面时候调用，完成后返回随便观主界面

        操作步骤
        0. 进入饮茶仙画面
        1. 切换到 定期采买
        2. 不断点击 提交、刷新
        3. 遍历采办清单 点红色(缺少)材料
        4. 尝试制造
        5. 不可制造则尝试游历
        6. 不可游历则退出
        7. 遍历采办清单结束后退出

        Args:
            ctx: 上下文
        """
        ZOperation.__init__(self, ctx,
                            op_name=f'{gt("随便观", "game")} {gt("饮茶仙", "game")}')

        self.config: SuibianTempleConfig = self.ctx.run_context.get_config(
            app_id='suibian_temple',
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.submit_only: bool = submit_only  # 只进行提交 不进行材料缺失的判断

        self.last_yum_cha_opt: str = ''  # 上一次饮茶仙的选项
        self.last_yum_cha_period: bool = False  # 饮茶仙是否点击过定期采购了

        self.done_procurement_list: list[str] = []  # 已经点击过的定期采办列表
        self.done_material_pos_list: set[Rect] = set()  # 已经点击过的材料位置 每次打开一个委托时候重置
        self.done_material_list: list[str] = []  # 已经点击过的材料名称
        self.done_craft: bool = False  #  是否进行了制造
        self.skip_adventure: bool = False  # 已经无法再派遣了 后续跳过

    @operation_node(name='前往饮茶仙', is_start_node=True)
    def goto_yum_cha_sin(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-饮茶仙'])
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        target_cn_list: list[str] = [
            '邻里街坊',
            '饮茶仙',
        ]
        ignore_cn_list: list[str] = [
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='前往饮茶仙')
    @operation_node(name='前往定期采办')
    def goto_regular_procurement(self) -> OperationRoundResult:
        """
        点击 定期采买
        """
        return self.round_by_find_and_click_area(self.last_screenshot, '随便观-饮茶仙', '按钮-定期采办',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='前往定期采办')
    @operation_node(name='定期采办提交', node_max_retry_times=2)
    def regular_procurement_submit(self) -> OperationRoundResult:
        """
        3. 不断点击 提交、刷新
        """
        target_cn_list: list[str] = [
            '确认',
            '已达上限',
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list)
        if result.is_success:
            if result.status == '已达上限':
                return self.round_success(status=result.status)
            return self.round_wait(status=result.status, wait=1)

        submit_area = self.ctx.screen_loader.get_area('随便观-饮茶仙', '按钮-定期采办-提交')
        submit_part = cv2_utils.crop_image_only(self.last_screenshot, submit_area.rect)
        if self.is_btn_available(submit_part):
            result = self.round_by_find_and_click_area(self.last_screenshot, '随便观-饮茶仙', '按钮-定期采办-提交')
            if result.is_success:
                return self.round_wait(status=result.status, wait=1)

        if self.config.yum_cha_sin_period_refresh:
            refresh_area = self.ctx.screen_loader.get_area('随便观-饮茶仙', '按钮-定期采办-刷新')
            refresh_part = cv2_utils.crop_image_only(self.last_screenshot, refresh_area.rect)
            if self.is_btn_available(refresh_part):
                result = self.round_by_find_and_click_area(self.last_screenshot, '随便观-饮茶仙', '按钮-定期采办-刷新')
                if result.is_success:
                    return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未发现可提交委托', wait=0.3)

    def is_btn_available(self, btn_part: MatLike) -> bool:
        """
        判断按钮是否可用
        Args:
            btn_part: 按钮图片

        Returns:
            bool: 是否可用
        """
        h, s, v = cv2.split(cv2.cvtColor(btn_part, cv2.COLOR_RGB2HSV))
        threshold = int(255 * 0.9)
        high_brightness_pixels = np.sum(v > threshold)
        total_pixels = v.size
        ratio = high_brightness_pixels / total_pixels if total_pixels > 0 else 0
        return ratio > 0.8

    @node_from(from_name='定期采办提交', success=False)
    @node_from(from_name='返回定期采办')
    @operation_node(name='检查定期采办委托', node_max_retry_times=2)
    def check_regular_procurement(self) -> OperationRoundResult:
        """
        4. 遍历采办清单 选择其中一个
        """
        if self.submit_only:
            return self.round_success(status='跳过缺失材料判断')

        current_list = self.get_regular_procurement_pos(self.last_screenshot)
        for current_item in current_list:
            # 使用近似匹配 因为委托名称前的符合会被识别成随机文本
            done_idx = str_utils.find_best_match_by_difflib(current_item.name, self.done_procurement_list)
            if done_idx is not None and done_idx > -1:
                continue

            self.done_procurement_list.append(current_item.name)
            self.ctx.controller.click(current_item.pos.center)

            self.done_material_pos_list = set()
            return self.round_success(status=current_item.name, wait=1)

        area = self.ctx.screen_loader.get_area('随便观-饮茶仙', '区域-任务列表')
        start = area.center
        end = start + Point(0, -400)
        self.ctx.controller.drag_to(start=start, end=end)

        return self.round_retry(status='未发现新委托', wait=0.5)

    def get_regular_procurement_pos(self, screen: MatLike) -> list[RegularProcurementPos]:
        """
        识别获取画面上的任务
        Args:
            screen: 游戏画面

        Returns:
            list[RegularProcurementPos]: 任务列表
        """
        task_list: list[RegularProcurementPos] = []
        area = self.ctx.screen_loader.get_area('随便观-饮茶仙', '区域-任务列表')

        ignore_word_list = [
            gt(i, 'game')
            for i in ['[随便观货品]', '精粹货品', '[随便观货品]精粹货品']
        ]

        ocr_result_map = self.ctx.ocr_service.get_ocr_result_map(screen, rect=area.rect)
        for ocr_result, mrl in ocr_result_map.items():
            ignore_idx = str_utils.find_best_match_by_difflib(
                ocr_result, ignore_word_list
            )
            if ignore_idx is not None and ignore_idx >= 0:
                continue

            for mr in mrl:
                task_list.append(RegularProcurementPos(ocr_result, mr.rect))

        return task_list

    @node_from(from_name='检查定期采办委托')
    @operation_node(name='检查缺少的素材', node_max_retry_times=2)
    def check_lack_of_material(self) -> OperationRoundResult:
        """
        点击缺少的素材 (找红色的数字)
        """
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            self.last_screenshot,
            color_range=[[220, 70, 30], [230, 140, 110]],
            rect=self.ctx.screen_loader.get_area('随便观-饮茶仙', '区域-材料数量').rect,
        )
        for ocr_result in ocr_result_list:
            digit = str_utils.get_positive_digits(ocr_result.data, err=None)
            if digit is None:
                continue

            # 判断之前是否已经点击过了
            done = False
            for rect in self.done_material_pos_list:
                if abs(rect.center.y - ocr_result.rect.center.y) < min(rect.height, ocr_result.rect.height) * 0.3:
                    done = True
                    break

            if done:
                continue

            # 找到最接近的材料
            for i in range(1, 4):
                material_area = self.ctx.screen_loader.get_area(
                    "随便观-饮茶仙", f"区域-材料-{i}"
                )
                material_rect = material_area.rect
                if abs(material_rect.center.y - ocr_result.rect.center.y) < min(material_rect.height, ocr_result.rect.height) * 0.3:
                    self.done_material_pos_list.add(material_rect)
                    self.ctx.controller.click(material_rect.center)
                    return self.round_success(wait=1)

        return self.round_retry(status='未发现缺少的素材', wait=0.5)

    @node_from(from_name='检查缺少的素材')
    @operation_node(name='前往制作')
    def goto_craft(self) -> OperationRoundResult:
        self.done_craft = False
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
            self.last_screenshot,
            rect=self.ctx.screen_loader.get_area('随便观-饮茶仙', '区域-材料名称').rect,
        )

        # 记录已经处理的材料名称 后续可以减少相同材料的处理
        for ocr_result in ocr_result_list:
            done_idx = str_utils.find_best_match_by_difflib(ocr_result.data, self.done_material_list)
            if done_idx is not None and done_idx > -1:
                return self.round_success(status='材料已处理过')
            self.done_material_list.append(ocr_result.data)

        return self.round_by_find_and_click_area(screen_name='随便观-饮茶仙', area_name='按钮-制造',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='前往制作', status='按钮-制造')
    @operation_node(name='制造派驻')
    def craft_dispatch(self) -> OperationRoundResult:
        op = SuibianTempleCraftDispatch(
            self.ctx,
            from_craft=False,
            chosen_item_list=[],
        )
        op_result = op.execute()
        if op_result.success and op_result.data == True:
            self.done_craft = True
        else:
            self.done_craft = False
        return self.round_success(status=op_result.status)

    @node_from(from_name='制造派驻')
    @operation_node(name='前往游历')
    def goto_adventure(self) -> OperationRoundResult:
        if self.done_craft:
            return self.round_success(status='无需前往游历')

        if self.skip_adventure:
            return self.round_success(status='无需前往游历')

        return self.round_by_find_and_click_area(screen_name='随便观-饮茶仙', area_name='按钮-游历',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name="前往游历")
    @operation_node(name='派遣游历小队')
    def do_adventure(self) -> OperationRoundResult:
        op = SuibianTempleAdventureDispatch(
            self.ctx,
            SuibianTempleAdventureDispatchDuration[self.config.adventure_duration],  # type: ignore
        )
        op_result = op.execute()
        if op_result.status == SuibianTempleAdventureDispatch.STATUS_CANT_DISPATCH:
            self.skip_adventure = True

        return self.round_by_op_result(op_result)

    @node_from(from_name='派遣游历小队')
    @operation_node(name='从游历返回材料菜单')
    def back_to_material_menu_2(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(screen_name='随便观-饮茶仙', area_name='按钮-返回')
        if result.is_success:
            time.sleep(0.5)  # 移开鼠标 防止挡住了返回按钮
            area = self.ctx.screen_loader.get_area('随便观-饮茶仙', '按钮-返回')
            self.ctx.controller.mouse_move(area.right_bottom + Point(50, 50))
            return self.round_wait(status=result.status, wait=0.5)

        result = self.round_by_find_area(self.last_screenshot, screen_name='随便观-饮茶仙', area_name='按钮-制造')
        if result.is_success:
            return self.round_success(status=result.status, wait=1)

        return self.round_retry(status='未找到返回按钮', wait=1)

    @node_from(from_name='检查缺少的素材', success=False)
    @node_from(from_name='前往制作', status='材料已处理过')
    @node_from(from_name='前往游历', status='无需前往游历')
    @node_from(from_name='从游历返回材料菜单')
    @operation_node(name='返回定期采办')
    def back_to_regular_procurement(self) -> OperationRoundResult:
        screen = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-饮茶仙'])
        if screen is not None:
            return self.round_success(status=screen)

        result = self.round_by_click_area(screen_name='随便观-饮茶仙', area_name='按钮-返回')
        if result.is_success:
            return self.round_retry(status='未识别当前画面', wait=2)  # 画面加载慢一点 稍微等待

        return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='定期采办提交', status='已达上限')
    @node_from(from_name='检查定期采办委托', success=False)
    @node_from(from_name='检查定期采办委托', status='跳过缺失材料判断')
    @operation_node(name='返回随便观')
    def back_to_entry(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'

    op = SuibianTempleYumChaSin(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
