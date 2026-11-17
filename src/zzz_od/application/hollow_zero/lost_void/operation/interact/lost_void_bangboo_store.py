import time

import cv2
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.lost_void import lost_void_const
from zzz_od.application.hollow_zero.lost_void.context.lost_void_artifact import (
    LostVoidArtifact,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_artifact_pos import (
    LostVoidArtifactPos,
)
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_common import (
    LostVoidChooseCommon,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidBangbooStore(ZOperation):

    def __init__(self, ctx: ZContext):
        ZOperation.__init__(self, ctx, op_name='迷失之地-邦布商店')

        self.refresh_times: int = 0  # 刷新次数
        self.store_type: str = '标识-金币'  # 商店类型
        self.slide_to_right: bool = False  # 滑动到右侧看更多的商品
        self.pending_buy: LostVoidArtifact | None = None  # 点了购买还没确认的商品 确认后写进本局记录
        self.is_last_rest_area: bool = False  # 是否第三层终结之役前的最后一个休息区 留硬币规则下刷新不限次数

    @operation_node(name='识别商店类型', is_start_node=True)
    def check_store_type(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '迷失之地-邦布商店', '标识-金币')
        if result.is_success:
            self.store_type = result.status
            self.ctx.lost_void.run_memory.start_store()
            self.is_last_rest_area = self.ctx.lost_void.is_last_rest_area()
            return self.round_success(result.status)

        result = self.round_by_find_area(self.last_screenshot, '迷失之地-邦布商店', '标识-血量')
        if result.is_success:
            self.store_type = result.status
            self.ctx.lost_void.run_memory.start_store()
            return self.round_success(result.status)

        return self.round_retry(status='未识别商店类型', wait=1)

    @node_from(from_name='识别商店类型')
    @node_from(from_name='识别商店类型', success=False)
    @node_from(from_name='确认后处理')
    @operation_node(name='购买藏品')
    def buy_artifact_gold(self) -> OperationRoundResult:
        # 移动鼠标到空的区域 防止阻碍识别
        area = self.ctx.screen_loader.get_area('迷失之地-邦布商店', '文本-详情')
        self.ctx.controller.mouse_move(area.center + Point(0, 100))
        time.sleep(0.1)

        if self.store_type == '标识-血量':
            if not self.ctx.lost_void.challenge_config.store_blood:
                return self.round_fail('不使用血量购买')

            if not self.check_min_blood_valid(self.last_screenshot):
                return self.round_fail('血量低于设定最小值')
        elif self.store_type == '标识-金币':
            if not self.ctx.lost_void.challenge_config.store_gold:
                return self.round_fail('不使用金币购买')

        # 按刷新之后的确认
        result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-邦布商店', '按钮-刷新-确认')
        if result.is_success:
            self.refresh_times += 1
            self.ctx.lost_void.run_memory.add_store_refresh()
            if self.ctx.lost_void.challenge_config.store_save_coin and self.slide_to_right:
                # 刷新后货架可能还停在右边 拖回左端从头看
                time.sleep(1)
                self._slide_to_end(towards_right=False)
            return self.round_wait(result.status, wait=1)

        screen_name = self.check_and_update_current_screen()
        if screen_name != '迷失之地-邦布商店':
            # 进入本指令之前 有可能识别错画面
            # 处理小概率可能会漏掉的武备升级环节
            if screen_name == '迷失之地-通用选择':
                op = LostVoidChooseCommon(self.ctx)
                op_result = op.execute()
                if op_result.success:
                    return self.round_wait(status='武备升级', wait=1)
                else:
                    return self.round_retry(status='武备升级失败', wait=1)
            return self.round_retry(status=f'当前画面 {screen_name}', wait=1)

        all_artifact_list, art_list = self.get_artifact_pos(self.last_screenshot)
        if self.ctx.lost_void.challenge_config.store_save_coin:
            return self._choose_by_save_coin(all_artifact_list, art_list)

        if len(art_list) == 0:
            if len(all_artifact_list) >= 4:
                return self.round_fail('已识别藏品但无可购买项')
            if not self.slide_to_right:
                start = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
                end = start + Point(-400, 0)
                self.ctx.controller.drag_to(start=start, end=end)
                self.slide_to_right = True
                return self.round_wait(status='向右滑动')
            return self.round_retry(status='未识别可购买藏品', wait=1)

        # 规则日志只在第1轮和放行状态变化轮打印，其他轮次不重复刷
        release_round = self.ctx.lost_void.challenge_config.buy_only_priority_2 - 1
        if self.refresh_times == 0 or self.refresh_times == release_round:
            self._log_priority_rules(self.refresh_times + 1)

        priority_list: list[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_by_priority(
            art_list, 1,
            consider_priority_1=True,
            consider_priority_2=self.refresh_times >= self.ctx.lost_void.challenge_config.buy_only_priority_2 - 1,
            consider_not_in_priority=self.refresh_times >= self.ctx.lost_void.challenge_config.buy_only_priority_2 - 1,
            consider_priority_new=self.ctx.lost_void.challenge_config.artifact_priority_new
        )

        if len(priority_list) == 0:
            if not self.slide_to_right:
                start = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
                end = start + Point(-400, 0)
                self.ctx.controller.drag_to(start=start, end=end)
                self.slide_to_right = True
                return self.round_wait(status='向右滑动')

            log.info(f'邦布商店 第{self.refresh_times + 1}轮 | 结果 | 未选中可购买藏品 下一步=刷新')
            result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-邦布商店', '按钮-刷新-可用')
            if result.is_success:
                self.slide_to_right = False  # 刷新后 重置滑动
                return self.round_wait(result.status, wait=1)

            # 不可以刷新了 就不管优先级都买了
            priority_list = self.ctx.lost_void.get_artifact_by_priority(art_list, len(art_list))

        if len(priority_list) == 0:
            return self.round_retry(status='按优先级选择藏品失败', wait=1)

        return self._buy(priority_list[0])

    def _choose_by_save_coin(self, all_artifact_list: list[LostVoidArtifactPos],
                             art_list: list[LostVoidArtifactPos]) -> OperationRoundResult:
        """
        挑战配置开启「商店留硬币」(store_save_coin) 时的购买逻辑
        普通商店最多刷新 3 次 还能刷新时只买高优先级 不能刷新后只买已有武备派系的 硬币留到最后一个休息区
        :param all_artifact_list: 识别到的全部商品
        :param art_list: 可购买的商品
        """
        if len(art_list) == 0:
            # 左边的都买完了 先看右边有没有
            if not self.slide_to_right:
                self._slide_to_end(towards_right=True)
                return self.round_wait(status='向右滑动')
            if len(all_artifact_list) >= 4:
                # 货架上的都买完了 还能刷新就刷新再看 和没有想买的商品时一样
                if self._can_refresh(self.last_screenshot):
                    result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-邦布商店', '按钮-刷新-可用')
                    if result.is_success:
                        log.info(f'邦布商店 第{self.refresh_times + 1}轮 | 结果 | 货架已买完 下一步=刷新')
                        return self.round_wait(result.status, wait=1)
                return self.round_fail('已识别藏品但无可购买项')
            return self.round_retry(status='未识别可购买藏品', wait=1)

        # 规则日志只在第1轮打印，其他轮次不重复刷
        if self.refresh_times == 0:
            self._log_priority_rules(self.refresh_times + 1)

        # 还能刷新时只买第0级(已有武备派系)、NEW、第1、2级 其余的(如通用鸣徽)宁可刷新换一批
        # 其他商店不能再刷新后 只买已有武备派系的 硬币留到最后一个休息区
        can_refresh = self._can_refresh(self.last_screenshot)
        if can_refresh:
            priority_list: list[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_by_priority(
                art_list, 1,
                consider_priority_1=True,
                consider_priority_2=False,
                consider_not_in_priority=False,
                consider_priority_new=self.ctx.lost_void.challenge_config.artifact_priority_new
            )
        elif self.is_last_rest_area:
            # 最后一个休息区刷新不了了 就不管优先级都买了
            priority_list = self.ctx.lost_void.get_artifact_by_priority(art_list, len(art_list))
        else:
            priority_list = [i for i in art_list if self.ctx.lost_void.is_gear_faction_match(i)]

        if len(priority_list) == 0:
            if not self.slide_to_right:
                self._slide_to_end(towards_right=True)
                return self.round_wait(status='向右滑动')

            if can_refresh:
                log.info(f'邦布商店 第{self.refresh_times + 1}轮 | 结果 | 未选中可购买藏品 下一步=刷新')
                result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-邦布商店', '按钮-刷新-可用')
                if result.is_success:
                    return self.round_wait(result.status, wait=1)

            if not self.is_last_rest_area:
                log.info(f'邦布商店 第{self.refresh_times + 1}轮 | 结果 | 没有已有武备派系的鸣徽 下一步=离开 硬币留到最后休息区')
                return self.round_fail('没有已有武备派系的鸣徽')

            # 最后一个休息区刷新按钮点不了(硬币不够) 就不管优先级都买了
            priority_list = self.ctx.lost_void.get_artifact_by_priority(art_list, len(art_list))

        if len(priority_list) == 0:
            return self.round_retry(status='按优先级选择藏品失败', wait=1)

        return self._buy(priority_list[0])

    def _buy(self, target: LostVoidArtifactPos) -> OperationRoundResult:
        """
        点击商品的购买按钮
        :param target: 要买的商品
        """
        target_item: LostVoidArtifact = target.artifact
        log.info(f'邦布商店 第{self.refresh_times + 1}轮 | 结果 | 购买 {target_item.display_name}')
        self.ctx.controller.click(target.store_buy_rect.center)
        self.pending_buy = target_item
        return self.round_success(target_item.name, wait=1)

    def _slide_to_end(self, towards_right: bool) -> None:
        """
        货架拖到最右或最左 经商友好战略等会增加商品槽位 只拖一张卡的距离会漏掉最右边的商品
        拖到底之后内容不会再动 所以距离给够即可
        :param towards_right: True 拖到最右 False 拖回最左
        """
        left = Point(200, self.ctx.controller.standard_height // 2)
        right = Point(1700, left.y)
        if towards_right:
            self.ctx.controller.drag_to(start=right, end=left)
        else:
            self.ctx.controller.drag_to(start=left, end=right)
        self.slide_to_right = towards_right

    def _can_refresh(self, screen: MatLike) -> bool:
        """
        留硬币规则下是否还允许刷新 最后一个休息区不限次数 其他商店花 200 硬币刷新(第 3 次)后不再刷新
        刷新后剩下的硬币不够买最便宜的鸣徽 刷新了也买不了 就不刷新
        :param screen: 游戏画面
        """
        if not self.is_last_rest_area and self.refresh_times >= lost_void_const.STORE_MAX_REFRESH_TIMES:
            return False

        coin = self._ocr_digits(screen, '区域-硬币数量')
        cost = self._ocr_digits(screen, '区域-刷新费用')
        if coin is None or cost is None:
            # 识别不到就按次数规则 点刷新失败(硬币不够)时后面会处理
            log.info(f'邦布商店 硬币或刷新费用识别失败 硬币={coin} 刷新费用={cost}')
            return True
        if coin - cost < lost_void_const.STORE_MIN_ARTIFACT_PRICE:
            log.info(f'邦布商店 硬币={coin} 刷新费用={cost} 刷新后不够买鸣徽(最低{lost_void_const.STORE_MIN_ARTIFACT_PRICE}) 不刷新')
            return False
        return True

    def _ocr_digits(self, screen: MatLike, area_name: str) -> int | None:
        """
        识别区域里的数字
        :param screen: 游戏画面
        :param area_name: 邦布商店画面的区域名称
        :return: 识别到的数字 识别不到返回 None
        """
        area = self.ctx.screen_loader.get_area('迷失之地-邦布商店', area_name)
        part = cv2_utils.crop_image_only(screen, area.rect)
        return str_utils.get_positive_digits(self.ctx.ocr.run_ocr_single_line(part))

    def _log_priority_rules(self, round_num: int) -> None:
        """
        打印当前轮次生效的优先级规则，便于日志直接看出为什么买/不买。
        只在第1轮和放行状态变化轮调用。
        """
        lv = self.ctx.lost_void
        level_parts = []
        faction_list = lv.get_owned_gear_faction_list() if lv.challenge_config.same_faction_first else []
        if len(faction_list) > 0:
            level_parts.append(f'第0级(已有武备派系)={",".join(faction_list)}')
        if len(lv.dynamic_priority_list) > 0:
            level_parts.append(f'第1级(动态)={",".join(lv.dynamic_priority_list)}')
        if len(lv.challenge_config.artifact_priority) > 0:
            level_parts.append(f'第2级(配置一)={",".join(lv.challenge_config.artifact_priority)}')
        if len(lv.challenge_config.artifact_priority_2) > 0:
            level_parts.append(f'第3级(配置二)={",".join(lv.challenge_config.artifact_priority_2)}')
        if len(lv.challenge_config.artifact_priority_in_battle) > 0:
            level_parts.append(f'第4级(战斗组)={",".join(lv.challenge_config.artifact_priority_in_battle)}')
        level_text = ' '.join(level_parts) if len(level_parts) > 0 else '无'
        abandon_text = ', '.join(lv.dynamic_abandon_list) if len(lv.dynamic_abandon_list) > 0 else '空'
        if lv.challenge_config.store_save_coin:
            refresh_text = '不限' if self.is_last_rest_area else f'{lost_void_const.STORE_MAX_REFRESH_TIMES}次'
            log.info(f'邦布商店 第{round_num}轮 | 规则 | {level_text} 放弃组={abandon_text} 最后休息区={self.is_last_rest_area} 刷新上限={refresh_text}')
        else:
            log.info(f'邦布商店 第{round_num}轮 | 规则 | {level_text} 放弃组={abandon_text}')

    def get_artifact_pos(self, screen: MatLike) -> tuple[list[LostVoidArtifactPos], list[LostVoidArtifactPos]]:
        """
        获取藏品的位置
        @param screen: 游戏画面
        @return: 全部识别到的藏品、可购买的藏品
        """
        artifact_pos_list: list[LostVoidArtifactPos] = self.ctx.lost_void.get_artifact_pos(
            screen,
            screen_name='迷失之地-邦布商店'
        )

        # 识别价格
        area = self.ctx.screen_loader.get_area('迷失之地-邦布商店', '区域-价格')
        part = cv2_utils.crop_image_only(screen, area.rect)
        mask = cv2.inRange(part, (200, 200, 200), (255, 255, 255))
        mask = cv2_utils.dilate(mask, 2)
        to_ocr = cv2.bitwise_and(part, part, mask=mask)
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)
        for ocr_result, mrl in ocr_result_map.items():
            price = str_utils.get_positive_digits(ocr_result)
            if price is None:
                continue

            for mr in mrl:
                mr.add_offset(area.left_top)
                for artifact_pos in artifact_pos_list:
                    artifact_pos.add_price(price, mr.rect)

        # 识别购买按钮
        area = self.ctx.screen_loader.get_area('迷失之地-邦布商店', '区域-购买按钮')
        part = cv2_utils.crop_image_only(screen, area.rect)
        mask = cv2.inRange(part, (200, 200, 200), (255, 255, 255))
        mask = cv2_utils.dilate(mask, 2)
        to_ocr = cv2.bitwise_and(part, part, mask=mask)
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)
        for ocr_result, mrl in ocr_result_map.items():
            if not str_utils.find_by_lcs(gt('购买', 'game'), ocr_result):
                continue

            for mr in mrl:
                mr.add_offset(area.left_top)
                for artifact_pos in artifact_pos_list:
                    artifact_pos.add_buy(mr.rect)

        can_buy_list = [i for i in artifact_pos_list if i.store_buy_rect is not None]
        display_text = ', '.join([i.artifact.display_name for i in can_buy_list]) if len(can_buy_list) > 0 else '无'
        log.info(f'当前可购买藏品 {display_text}')

        return artifact_pos_list, can_buy_list

    def check_min_blood_valid(self, screen: MatLike) -> bool:
        """
        识别当前血量是否满足购买
        @param screen: 游戏画面
        @return:
        """
        min_blood = self.ctx.lost_void.challenge_config.store_blood_min

        area = self.ctx.screen_loader.get_area('迷失之地-邦布商店', '区域-角色头像')
        ocr_result_map = self.ctx.ocr.crop_and_run_ocr(screen, area.rect)
        for ocr_result, _mrl in ocr_result_map.items():
            blood = str_utils.get_positive_digits(ocr_result)
            if blood is None:
                continue
            if blood < min_blood:
                return False

        return True

    @node_from(from_name='购买藏品')
    @operation_node(name='点击确认')
    def click_confirm(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='迷失之地-邦布商店', area_name='按钮-购买-确认',
                                                 success_wait=1, retry_wait=1,
                                                 until_not_find_all=[('迷失之地-邦布商店', '按钮-购买-确认')])

    @node_from(from_name='点击确认')
    @operation_node(name='确认后处理')
    def after_confirm(self) -> OperationRoundResult:
        """
        处理可能出现的武备升级环节
        @return:
        """
        screen_name = self.check_and_update_current_screen(self.last_screenshot)

        if screen_name == '迷失之地-通用选择':
            op = LostVoidChooseCommon(self.ctx)
            op_result = op.execute()
            if op_result.success:
                return self.round_wait(status='武备升级', wait=1)
            else:
                return self.round_retry(status='武备升级失败', wait=1)
        elif screen_name == '迷失之地-邦布商店':
            if self.pending_buy is not None:
                memory = self.ctx.lost_void.run_memory
                memory.add_artifact(self.pending_buy)
                memory.add_store_buy(self.pending_buy.display_name)
                self.pending_buy = None
            return self.round_success(status=self.store_type, wait=1)
        else:
            return self.round_retry(status=f'未知画面 {screen_name}', wait=1)

    @node_from(from_name='购买藏品', success=False)
    @operation_node(name='购买结束')
    def finish(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='迷失之地-邦布商店', area_name='按钮-返回',
                                                 success_wait=1, retry_wait=1,
                                                 until_not_find_all=[('迷失之地-邦布商店', '按钮-返回')])


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.init_ocr()
    ctx.lost_void.init_before_run()
    ctx.run_context.start_running()

    op = LostVoidBangbooStore(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
