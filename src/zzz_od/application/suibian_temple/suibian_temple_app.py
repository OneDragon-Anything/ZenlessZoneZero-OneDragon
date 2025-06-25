import cv2
import re

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class SuibianTempleApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='suibian_temple',
            op_name=gt('随便观'),
            run_record=ctx.suibian_temple_record,
            retry_in_od=True,  # 传送落地有可能会歪 重试
            need_notify=True,
        )

        self.last_squad_opt: str = ''  # 上一次的游历小队选项
        self.chosen_item_list: list[str] = []  # 已经选择过的货品列表
        self.new_item_after_drag: bool = False  # 滑动后是否有新商品

        self.last_yum_cha_opt: str = ''  # 上一次饮茶仙的选项
        self.last_yum_cha_period: bool = False  # 饮茶仙是否点击过定期采购了

    @operation_node(name='识别初始画面', is_start_node=True)
    def check_initial_screen(self) -> OperationRoundResult:
        screen = self.screenshot()

        current_screen_name, can_go = self.check_screen_with_can_go(screen, '快捷手册-目标')
        if can_go is not None and can_go == True:
            return self.round_by_goto_screen(screen, '快捷手册-目标',
                                             success_wait=1, retry_wait=1)

        current_screen_name, can_go = self.check_screen_with_can_go(screen, '随便观-入口')
        if can_go is not None and can_go == True:
            return self.round_success(status='随便观-入口')

        return self.round_retry(status='未识别初始画面', wait=1)

    @node_from(from_name='识别初始画面', status='未识别初始画面', success=False)
    @operation_node(name='开始前返回大世界')
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别初始画面', status='快捷手册-目标')
    @node_from(from_name='开始前返回大世界')
    @operation_node(name='前往快捷手册-目标')
    def goto_category(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_goto_screen(screen, '快捷手册-目标')

    @node_from(from_name='前往快捷手册-目标')
    @operation_node(name='前往随便观', node_max_retry_times=10)
    def goto_suibian_temple(self) -> OperationRoundResult:
        screen = self.screenshot()

        target_cn_list: list[str] = [
            '前往随便观',
            '确认',
            '累计获得称愿',
        ]

        result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list)
        if result.is_success:
            if result.status == '累计获得称愿':
                self.round_by_find_and_click_area(screen, '菜单', '返回')
            return self.round_wait(status=result.status, wait=1)

        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()
        else:
            return self.round_retry(status='未识别当前画面', wait=1)

    @node_from(from_name='识别初始画面', status='随便观-入口')
    @node_from(from_name='前往随便观')
    @operation_node(name='点击-邻里街坊')
    def goto_linli_jiefang(self) -> OperationRoundResult:
        screen = self.screenshot()
        # 如果已经看到好物铺，说明已经点过邻里街坊了
        if self.round_by_ocr(screen, '好物铺').is_success:
            return self.round_success(status='已在邻里街坊')

        # 点击按钮
        result = self.round_by_ocr_and_click(screen, '邻里街坊')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1.5)

        return self.round_retry(status='未找到邻里街坊', wait=1)

    @node_from(from_name='点击-邻里街坊')
    @operation_node(name='点击-好物铺')
    def goto_goodgoods(self) -> OperationRoundResult:
        screen = self.screenshot()

        # 检查是否已经进入好物铺
        if self.round_by_ocr(screen, '经营购置').is_success:
            return self.round_success(status='已在好物铺')

        # 点击按钮
        result = self.round_by_ocr_and_click(screen, '好物铺')
        if result.is_success:
            return self.round_wait(status=result.status, wait=2)

        return self.round_retry(status='未找到好物铺', wait=1)

    @node_from(from_name='点击-好物铺')
    @operation_node(name='好物铺-购买')
    def process_goodgoods(self) -> OperationRoundResult:
        screen = self.screenshot()

        # 获得
        if self.round_by_ocr(screen, '获得').is_success:
            confirm_result = self.round_by_ocr_and_click(screen, '确认')
            if not confirm_result.is_success:
                return self.round_retry(status='点击获得确认失败')
            return self.round_success(status='购买成功')

        # 处理弹窗
        if self.round_by_ocr(screen, '兑换确认').is_success:
            # 直接使用精确坐标拖拽滑块到最大值
            start_point = Point(755, 672)
            end_point = Point(1200, 672)
            self.ctx.controller.drag_to(start=start_point, end=end_point)

            # 点击兑换确认
            confirm_result = self.round_by_ocr_and_click(screen, '确认')
            if not confirm_result.is_success:
                return self.round_retry(status='点击兑换确认失败')

            # 等待"获得"弹窗出现
            return self.round_wait(status='已确认兑换', wait=2)

        # 在好物铺主界面，查找并购买商品
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        
        # 查找邦布能源插件
        plugin_mrls = []
        for ocr_result, mrl in ocr_result_map.items():
            if '邦布能源插件' in ocr_result and mrl.max is not None:
                plugin_mrls.append(mrl)
        
        if not plugin_mrls:
            # 如果找不到商品，尝试切换分页
            change_tab_result = self.round_by_ocr_and_click(screen, '经营购置')
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

        # todo 售罄检测不可靠
        # 先检查商品本身区域是否有"已售罄"文本
        plugin_area_img = cv2_utils.crop_image_only(screen, plugin_rect)
        plugin_ocr_map = self.ctx.ocr.run_ocr(plugin_area_img)
        for ocr_text, mrl in plugin_ocr_map.items():
            if '已售罄' in ocr_text or '售罄' in ocr_text:
                return self.round_success(status='跳过购买-已售罄')
        
        # 在商品下方区域搜索价格信息
        screen_height = screen.shape[0]  # 获取屏幕高度
        price_search_rect = Rect(plugin_rect.x1 - 20, plugin_rect.y2, plugin_rect.x2 + 20, screen_height)
        
        # 截取并进行OCR
        price_area_img = cv2_utils.crop_image_only(screen, price_search_rect)
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

    @node_from(from_name='好物铺-购买', status='跳过购买-已售罄')
    @node_from(from_name='好物铺-购买')
    @operation_node(name='好物铺-返回邻里')
    def exit_goodgoods(self) -> OperationRoundResult:
        screen = self.screenshot()

        if self.round_by_ocr(screen, '邻里街坊').is_success:
            return self.round_success(status='已返回邻里街坊')

        # 操作：点击左上角返回
        result = self.round_by_find_and_click_area(screen, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status='点击左上角返回', wait=1)

        return self.round_retry(status='无法从好物铺返回', wait=1)

    @node_from(from_name='好物铺-返回邻里')
    @operation_node(name='邻里-返回主页')
    def exit_linli_jiefang(self) -> OperationRoundResult:
        screen = self.screenshot()

        # 回到随便观主页（能看到"游历"）
        if self.round_by_ocr(screen, '游历').is_success:
            return self.round_success(status='已返回随便观主页')

        # 操作：点击"关闭"
        result = self.round_by_ocr_and_click(screen, '关闭')
        if result.is_success:
            return self.round_wait(status='点击关闭', wait=1)

        return self.round_retry(status='无法从邻里街坊返回', wait=1)

    @node_from(from_name='邻里-返回主页')
    @operation_node(name='随便观-游历')
    def goto_adventure(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(
            screen, '随便观-入口', '按钮-游历',
            success_wait=1, retry_wait=1,
            until_not_find_all=[('随便观-入口', '按钮-游历')]
        )

    @node_from(from_name='随便观-游历')
    @operation_node(name='选择游历小队')
    def choose_adventure_squad(self) -> OperationRoundResult:
        screen = self.screenshot()

        target_cn_list: list[str] = [
            '自动选择邦布',
            '派遣',
            '确认',
            '可收获',
            '游历完成',
            '待派遣小队',
            '可派遣小队',  # 空白区域上的提取 用于避免 待派遣小队 匹配错误 需要忽略
            '游历小队',
        ]
        ignore_cn_list: list[str] = [
            '剩余时间',
            '可派遣小队',
        ]
        if self.last_squad_opt in ['游历小队', '自动选择邦布']:  # 不能一直点击
            ignore_cn_list.append(self.last_squad_opt)
        result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            self.last_squad_opt = result.status
            if result.status == '待派遣小队':
                return self.round_retry(status='未识别游历完成小队', wait=1)

            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别游历完成小队', wait=1)

    @node_from(from_name='选择游历小队', success=False)
    @operation_node(name='游历后返回')
    def after_adventure(self) -> OperationRoundResult:
        screen = self.screenshot()

        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        result = self.round_by_find_and_click_area(screen, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='游历后返回')
    @operation_node(name='前往经营')
    def goto_business(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(
            screen, '随便观-入口', '按钮-经营',
            success_wait=1, retry_wait=1,
            until_not_find_all=[('随便观-入口', '按钮-经营')]
        )

    @node_from(from_name='前往经营')
    @operation_node(name='前往制造')
    def goto_craft(self) -> OperationRoundResult:
        self.chosen_item_list = []
        self.new_item_after_drag = False
        screen = self.screenshot()
        return self.round_by_ocr_and_click(screen, '制造', success_wait=1, retry_wait=1)

    @node_from(from_name='前往制造')
    @operation_node(name='开工')
    def click_lets_go(self) -> OperationRoundResult:
        screen = self.screenshot()

        target_cn_list: list[str] = [
            '开工',
            '开物',
        ]
        ignore_cn_list: list[str] = [
            '开物',
        ]
        result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        result = self.round_by_find_area(screen, '随便观-入口', '标题-制造坊')
        if result.is_success:
            target_cn_list: list[str] = [
                '所需材料不足',
                '开始制造',
            ]
            result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list, ignore_cn_list=ignore_cn_list)
            if result.is_success and result.status == '开始制造':
                return self.round_wait(status=result.status, wait=1)

            # 不能制造的 换一个货品
            area = self.ctx.screen_loader.get_area('随便观-入口', '区域-制造坊商品列表')
            part = cv2_utils.crop_image_only(screen, area.rect)
            mask = cv2_utils.color_in_range(part, (230, 230, 230), (255, 255, 255))
            to_ocr_part = cv2.bitwise_and(part, part, mask=mask)
            ocr_result_map = self.ctx.ocr.run_ocr(to_ocr_part)
            for ocr_result, mrl in ocr_result_map.items():
                if mrl.max is None:
                    continue
                if ocr_result in self.chosen_item_list:
                    continue
                self.new_item_after_drag = True
                self.chosen_item_list.append(ocr_result)
                self.ctx.controller.click(area.left_top + mrl.max.right_bottom + Point(50, 0))  # 往右方点击 防止遮挡到货品名称
                return self.round_wait(status='选择下一个货品', wait=1)

            if self.new_item_after_drag:
                # 已经都选择过了 就往下滑动一定距离
                start = area.center
                end = start + Point(0, -300)
                self.ctx.controller.drag_to(start=start, end=end)
                self.new_item_after_drag = False
                return self.round_retry(status='滑动找未选择过的货品', wait=1)

        return self.round_retry(status='未识别开工按钮', wait=1)

    @node_from(from_name='开工', success=False)
    @operation_node(name='制造后返回')
    def after_lets_go(self) -> OperationRoundResult:
        screen = self.screenshot()

        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        result = self.round_by_find_and_click_area(screen, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='制造后返回')
    @operation_node(name='前往饮茶仙')
    def goto_yum_cha_sin(self) -> OperationRoundResult:
        screen = self.screenshot()

        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['随便观-饮茶仙'])
        if current_screen_name is not None:
            # 引入饮茶仙前做一些初始化
            self.last_yum_cha_opt = ''
            self.last_yum_cha_period = False
            return self.round_success(status=current_screen_name)

        target_cn_list: list[str] = [
            '邻里街坊',
            '饮茶仙',
        ]
        ignore_cn_list: list[str] = [
        ]
        result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未识别当前画面', wait=1)


    @node_from(from_name='前往饮茶仙')
    @operation_node(name='饮茶仙-提交委托')
    def yum_cha_sin_submit(self) -> OperationRoundResult:
        screen = self.screenshot()

        target_cn_list: list[str] = [
            '确认',
            '提交',
            '定期采办',
        ]
        ignore_cn_list: list[str] = []
        if self.last_yum_cha_opt != '':
            ignore_cn_list.append(self.last_yum_cha_opt)
        if self.last_yum_cha_period:
            ignore_cn_list.append('定期采办')

        result = self.round_by_ocr_and_click_by_priority(screen, target_cn_list, ignore_cn_list=ignore_cn_list)
        if result.is_success:
            self.last_yum_cha_opt = result.status
            if result.status == '定期采办':
                self.last_yum_cha_period = True
            return self.round_wait(status=result.status, wait=1)

        return self.round_retry(status='未发现可提交委托', wait=1)

    @node_from(from_name='饮茶仙-提交委托', success=False)
    @operation_node(name='饮茶仙后返回')
    def after_yum_cha_sin(self) -> OperationRoundResult:
        screen = self.screenshot()

        current_screen_name = self.check_and_update_current_screen(screen, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success(status=current_screen_name)

        result = self.round_by_find_and_click_area(screen, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='饮茶仙后返回')
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = SuibianTempleApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
