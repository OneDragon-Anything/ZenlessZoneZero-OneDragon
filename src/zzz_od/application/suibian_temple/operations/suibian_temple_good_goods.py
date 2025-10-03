import re
from typing import Optional

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.suibian_temple.suibian_temple_config import SuibianTempleConfig
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleGoodGoods(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 好物铺

        需要在随便观主界面时调用，完成后返回随便观主界面

        操作步骤
        1. 前往邻里街坊
        2. 进入好物铺
        3. 购买邦布能源插件
        4. 返回随便观主界面

        Args:
            ctx: 上下文
        """
        ZOperation.__init__(self, ctx,
                            op_name=f'{gt("随便观", "game")} {gt("好物铺", "game")}')

        self.config: Optional[SuibianTempleConfig] = self.ctx.run_context.get_config(app_id='suibian_temple')

        self.purchased_count: int = 0  # 已购买商品数量

    @operation_node(name='前往邻里街坊', is_start_node=True, node_max_retry_times=5)
    def goto_linli_jiefang(self) -> OperationRoundResult:
        # 如果已经看到好物铺，说明已经点过邻里街坊了
        if self.round_by_ocr(self.last_screenshot, '好物铺').is_success:
            return self.round_success(status='已在邻里街坊-进入好物铺')

        # 点击按钮
        result = self.round_by_ocr_and_click(self.last_screenshot, '邻里街坊')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1.5)

        return self.round_retry(status='未找到邻里街坊', wait=1)

    @node_from(from_name='前往邻里街坊')
    @operation_node(name='已在邻里街坊-进入好物铺', node_max_retry_times=5)
    def goto_good_goods(self) -> OperationRoundResult:
        """从邻里街坊进入好物铺"""
        # 首先检查是否已经在好物铺界面
        if self.round_by_ocr(self.last_screenshot, '经营购置').is_success:
            return self.round_success(status='已在好物铺-购买')
        # 点击按钮
        result = self.round_by_ocr_and_click(self.last_screenshot, '好物铺')
        if result.is_success:
            return self.round_wait(status=result.status, wait=2)

        return self.round_retry(status='未找到好物铺', wait=1)

    @node_from(from_name='已在邻里街坊-进入好物铺')
    @node_from(from_name='已在好物铺-购买', status='已确认兑换')
    @operation_node(name='已在好物铺-购买')
    def process_good_goods(self) -> OperationRoundResult:
        """执行商品购买逻辑"""
        # 获得
        if self.round_by_ocr(self.last_screenshot, '获得').is_success:
            confirm_result = self.round_by_ocr_and_click(self.last_screenshot, '确认')
            if not confirm_result.is_success:
                return self.round_retry(status='点击获得确认失败')
            self.purchased_count += 1
            log.info(f"成功购买第{self.purchased_count}个商品")
            return self.round_success(status='购买成功')

        # 处理弹窗
        if self.round_by_ocr(self.last_screenshot, '兑换确认').is_success:
            # 直接使用精确坐标拖拽滑块到最大值
            start_point = Point(755, 672)
            end_point = Point(1300, 672)
            self.ctx.controller.drag_to(start=start_point, end=end_point, duration=2)

            # 点击兑换确认
            confirm_result = self.round_by_ocr_and_click(self.last_screenshot, '确认')
            if not confirm_result.is_success:
                return self.round_retry(status='点击兑换确认失败')

            # 等待"获得"弹窗出现
            return self.round_wait(status='已确认兑换', wait=2)

        # 在好物铺主界面，查找并购买商品
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)

        # 查找邦布能源插件
        plugin_mrls = []
        for ocr_result, mrl in ocr_result_map.items():
            if '邦布能源插件' in ocr_result and mrl.max is not None:
                plugin_mrls.append(mrl)

        if not plugin_mrls:
            # 如果找不到商品，尝试切换分页
            change_tab_result = self.round_by_ocr_and_click(self.last_screenshot, '经营购置')
            if change_tab_result.is_success:
                return self.round_wait(status='切换到经营购置', wait=1)
            else:
                # 找不到商品也无法切换，认为任务完成，避免卡死
                return self.round_success(status='找不到商品或已完成')

        # 找到最左下的邦布能源插件（最左的，如果有多个则选择最下面的）
        leftmost_bottom_plugin = min(plugin_mrls,
                                     key=lambda x: (x.max.rect.x1, -x.max.rect.y2))

        # 检查这个商品下方是否有500数字（表示可购买）
        plugin_rect = leftmost_bottom_plugin.max.rect

        # 先检查商品本身区域是否有"已售罄"文本
        plugin_area_img = cv2_utils.crop_image_only(self.last_screenshot, plugin_rect)
        plugin_ocr_map = self.ctx.ocr.run_ocr(plugin_area_img)
        for ocr_text, mrl in plugin_ocr_map.items():
            if '已售罄' in ocr_text or '售罄' in ocr_text:
                return self.round_success(status='跳过购买-已售罄')

        # 在商品下方区域搜索价格信息
        screen_height = self.last_screenshot.shape[0]  # 获取屏幕高度
        price_search_rect = Rect(plugin_rect.x1 - 20, plugin_rect.y2, plugin_rect.x2 + 20, screen_height)

        # 截取并进行OCR
        price_area_img = cv2_utils.crop_image_only(self.last_screenshot, price_search_rect)
        price_ocr_map = self.ctx.ocr.run_ocr(price_area_img)

        has_price = False
        # 检查是否有价格相关文本
        for ocr_text in price_ocr_map.keys():
            # 检查500或其变体
            price_patterns = ['500', '5OO', '50O', 'S00', 'soo', '5oo']
            for pattern in price_patterns:
                if pattern.lower() in ocr_text.lower():
                    has_price = True
                    break
            if has_price:
                break

            # 检查是否包含价格相关的数字（排除等级信息）
            if any(char.isdigit() for char in ocr_text):
                # 排除等级相关的文本 (Lv., 等级等)
                if not any(level_word in ocr_text.lower() for level_word in ['lv', '等级', 'level']):
                    # 如果包含3位数字，很可能是价格
                    numbers = re.findall(r'\d+', ocr_text)
                    for num in numbers:
                        if len(num) >= 3:  # 3位数以上可能是价格
                            has_price = True
                            break

        if not has_price:
            # 没有价格数字，说明已经购买过了或者已售罄
            return self.round_success(status='跳过购买-已售罄')

        # 有价格数字，说明可以购买，点击商品
        click_result = self.ctx.controller.click(leftmost_bottom_plugin.max.rect.center)
        if not click_result:
            return self.round_retry(status='点击邦布能源插件失败')

        # 等待"兑换确认"弹窗出现
        return self.round_wait(status='已点击邦布能源插件', wait=1.5)

    @node_from(from_name='已在好物铺-购买', status='跳过购买-已售罄')
    @node_from(from_name='已在好物铺-购买', status='购买成功')
    @node_from(from_name='已在好物铺-购买', status='找不到商品或已完成')
    @operation_node(name='好物铺-返回邻里')
    def exit_goodgoods(self) -> OperationRoundResult:
        if self.round_by_ocr(self.last_screenshot, '邻里街坊').is_success:
            return self.round_success(status='已返回邻里街坊')

        # 操作：点击左上角返回
        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status='点击左上角返回', wait=1)

        return self.round_retry(status='无法从好物铺返回', wait=1)

    @node_from(from_name='好物铺-返回邻里')
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
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'
    op = SuibianTempleGoodGoods(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()