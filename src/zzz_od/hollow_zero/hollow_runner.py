import time

from cv2.typing import MatLike
from typing import Type, ClassVar, List, Optional

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cal_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.withered_domain.hollow_zero_config import HollowZeroExtraTask, HollowZeroExtraExitEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.bamboo_merchant import BambooMerchant
from zzz_od.hollow_zero.event.call_for_support import CallForSupport
from zzz_od.hollow_zero.event.choose_resonium import ChooseResonium
from zzz_od.hollow_zero.event.confirm_resonium import ConfirmResonium
from zzz_od.hollow_zero.event.critical_stage import CriticalStage
from zzz_od.hollow_zero.event.door_battle import DoorBattle
from zzz_od.hollow_zero.event.drop_resonium import DropResonium, DropResonium2
from zzz_od.hollow_zero.event.full_in_bag import FullInBag
from zzz_od.hollow_zero.event.leave_random_zone import LeaveRandomZone
from zzz_od.hollow_zero.event.normal_event_handler import NormalEventHandler
from zzz_od.hollow_zero.event.old_capital import OldCapital
from zzz_od.hollow_zero.event.remove_corruption import RemoveCorruption
from zzz_od.hollow_zero.event.swift_supply import SwiftSupply
from zzz_od.hollow_zero.event.switch_resonium import SwitchResonium
from zzz_od.hollow_zero.event.upgrade_resonium import UpgradeResonium
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent
from zzz_od.hollow_zero.hollow_battle import HollowBattle
from zzz_od.hollow_zero.hollow_exit_by_menu import HollowExitByMenu
from zzz_od.hollow_zero.hollow_map.hollow_zero_map import HollowZeroMap, HollowZeroMapNode
from zzz_od.operation.zzz_operation import ZOperation


class HollowRunner(ZOperation):

    STATUS_LEAVE: ClassVar[str] = '离开空洞'

    def __init__(self, ctx: ZContext):
        ZOperation.__init__(
            self, ctx,
            op_name=gt('空洞操作器', 'game')
        )

        self._special_event_handlers: dict[str, Type] = {
            HollowZeroSpecialEvent.CALL_FOR_SUPPORT.value.event_name: CallForSupport,

            HollowZeroSpecialEvent.RESONIUM_STORE_0.value.event_name: BambooMerchant,
            HollowZeroSpecialEvent.RESONIUM_STORE_1.value.event_name: BambooMerchant,
            HollowZeroSpecialEvent.RESONIUM_STORE_2.value.event_name: BambooMerchant,
            HollowZeroSpecialEvent.RESONIUM_STORE_3.value.event_name: BambooMerchant,
            HollowZeroSpecialEvent.RESONIUM_STORE_4.value.event_name: BambooMerchant,
            # HollowZeroSpecialEvent.RESONIUM_STORE_5.value.event_name: BambooMerchant,

            HollowZeroSpecialEvent.RESONIUM_CHOOSE.value.event_name: ChooseResonium,
            HollowZeroSpecialEvent.RESONIUM_CONFIRM_1.value.event_name: ConfirmResonium,
            HollowZeroSpecialEvent.RESONIUM_CONFIRM_2.value.event_name: ConfirmResonium,
            HollowZeroSpecialEvent.RESONIUM_UPGRADE.value.event_name: UpgradeResonium,
            HollowZeroSpecialEvent.RESONIUM_DROP.value.event_name: DropResonium,
            HollowZeroSpecialEvent.RESONIUM_DROP_2.value.event_name: DropResonium2,
            HollowZeroSpecialEvent.RESONIUM_SWITCH.value.event_name: SwitchResonium,
            HollowZeroSpecialEvent.SWIFT_SUPPLY_LIFE.value.event_name: SwiftSupply,
            HollowZeroSpecialEvent.SWIFT_SUPPLY_COIN.value.event_name: SwiftSupply,
            HollowZeroSpecialEvent.SWIFT_SUPPLY_PRESS.value.event_name: SwiftSupply,

            HollowZeroSpecialEvent.CORRUPTION_REMOVE.value.event_name: RemoveCorruption,

            HollowZeroSpecialEvent.CRITICAL_STAGE_ENTRY.value.event_name: CriticalStage,
            HollowZeroSpecialEvent.CRITICAL_STAGE_ENTRY_2.value.event_name: CriticalStage,

            HollowZeroSpecialEvent.IN_BATTLE.value.event_name: HollowBattle,
            HollowZeroSpecialEvent.FULL_IN_BAG.value.event_name: FullInBag,
            HollowZeroSpecialEvent.OLD_CAPITAL.value.event_name: OldCapital,

            # HollowZeroSpecialEvent.DOOR_BATTLE_ENTRY.value.event_name: DoorBattle,
            # HollowZeroSpecialEvent.NEED_INTERACT.value.event_name: HollowInteract,
        }

        # 部分格子有一个选项作为入口
        self._entry_event_handlers: dict[str, Type] = {
            '邦布商人': BambooMerchant,
            '守门人': CriticalStage,
            '门扉禁闭-善战': DoorBattle,
            '门扉禁闭-侵蚀': DoorBattle,
            '不宜久留': LeaveRandomZone
        }
        self._entry_events: dict[str, List[str]] = {
            '邦布商人': ['进入商店'],
        }

        self._last_save_image_time: float = 0
        self._last_move_time: float = 0  # 上一次移动的时间

        self._handled_events: set[str] = set()  # 当前已处理过的事件 移动后清空

    @operation_node(name='画面识别', is_start_node=True, node_max_retry_times=60)
    def check_screen(self) -> OperationRoundResult:
        now = time.time()
        screen = self.screenshot()
        result = hollow_event_utils.check_screen(self.ctx, screen, self._handled_events)
        if result is not None and result not in [
            HollowZeroSpecialEvent.HOLLOW_INSIDE.value.event_name,  # 空洞内部比较特殊 仅为识别使用 不做响应处理
            HollowZeroSpecialEvent.RESONIUM_STORE_5.value.event_name,  # 商人格子不会消失 为了防止循环进入商店 仅在移动格子时候触发进入商店 平时出现这个选项不做点击
            HollowZeroSpecialEvent.DOOR_BATTLE_ENTRY.value.event_name,  # 这扇门在第一次过去的时候就会开 如果没开到 说明上场战斗没有S 开不了 就不继续了
        ]:
            return self._handle_event(screen, result)

        if result in [
            HollowZeroSpecialEvent.HOLLOW_INSIDE.value.event_name,  # 当前有显示背包 可以尝试识别地图
            HollowZeroSpecialEvent.RESONIUM_STORE_5.value.event_name,  # 商人格子也需要寻路
            HollowZeroSpecialEvent.DOOR_BATTLE_ENTRY.value.event_name,  # 门扉禁闭-善战 开不了门 就移动去其他地方
        ]:
            current_map = self.ctx.hollow.map_service.cal_map_by_screen(screen, now)
            if current_map is not None:
                result = self.try_move_by_map(screen, now, current_map)
                if result is not None:
                    return result
            # 识别不到地图 说明可能是空洞里有需要确认的对话框 随便点击一下吧对话框取消掉
            else:
                self.round_by_click_area('零号空洞-事件', '空白')
        else:
            # 未知的情况 点击一下继续
            self.round_by_click_area('零号空洞-事件', '空白')

        return self.round_retry('未能识别当前画面', wait=1)

    def _handle_event(self, screen: MatLike, event_name: str) -> OperationRoundResult:
        """
        识别到事件时 进行处理
        :param event_name:
        :return:
        """
        normal_event = self.ctx.hollow.data_service.get_normal_event_by_name(event_name=event_name)
        any_match = False
        if normal_event is not None:
            any_match = True
            log.info('匹配普通事件 [%s]', event_name)
            if normal_event.is_entry_opt:
                self._handled_events.add(event_name)
            op = NormalEventHandler(self.ctx, normal_event)
            op_result = op.execute()
            if op_result.success:  # 失败的时候继续尝试特殊事件 防止错误匹配到普通事件上
                return self.round_wait()

        if event_name in self._special_event_handlers:
            any_match = True
            log.info('匹配特殊事件 [%s]', event_name)
            special_event = hollow_event_utils.get_special_event_by_name(event_name)
            if special_event.is_entry_opt:
                self._handled_events.add(event_name)

            op: ZOperation = self._special_event_handlers[event_name](self.ctx)
            op_result = op.execute()
            if op_result.success:
                return self.round_wait()

        if event_name == HollowZeroSpecialEvent.MISSION_COMPLETE.value.event_name:
            return self.round_success(status='通关-完成')

        if any_match:
            return self.round_retry('事件处理失败', wait=1)
        else:
            return self.round_retry('当前事件未有对应指令', wait=1)

    def try_move_by_map(self, screen: MatLike, screen_time: float, current_map: HollowZeroMap) -> Optional[OperationRoundResult]:
        """
        识别到地图后 尝试自动寻路并移动
        :param screen: 游戏画面
        :param screen_time: 截图时间
        :param current_map: 分析得到的地图
        :return:
        """
        target_node: HollowZeroMapNode = self.ctx.hollow.get_next_to_move(current_map)
        if target_node is None:
            return None

        # if target_node.entry.entry_name == '不宜久留':  # 测试代码 在特殊情况停下
        #     return self.round_fail('不宜久留')
        next_to_move = target_node.next_node_to_move
        log.info(f"前往目标: [{target_node.entry.entry_name}] 当前移动: [{next_to_move.entry.entry_name}]")

        # 999 是寻路兜底策略的特殊标识 是在识别识别的情况下使用的
        pathfinding_success = next_to_move is not None and next_to_move.path_step_cnt != 999
        if not pathfinding_success:
            self._save_debug_image(screen)
            if next_to_move is None:
                return self.round_retry('自动寻路失败')

        # 寻路失败的话 间隔1秒才尝试一次兜底策略的移动
        if not pathfinding_success and screen_time - self._last_move_time < 1:
            return self.round_retry('自动寻路失败')

        if pathfinding_success:
            self.ctx.hollow.check_info_before_move(screen, current_map)
            # self._try_click_speed_up(screen)  # 可以在游戏内设置继承上一次
            extra_finished = self._check_extra_task_finished(screen, current_map)
            if extra_finished:
                return self.round_success(HollowRunner.STATUS_LEAVE)

        self._last_move_time = screen_time
        to_click = self.get_map_node_pos_to_click(screen, next_to_move)
        self.ctx.controller.click(to_click)
        # 每个格子大概需要0.25秒移动 再加一秒等待格子事件触发
        move_time = next_to_move.path_node_cnt * 0.25 + 1
        time.sleep(move_time)

        # 如果是特殊需要选项的格子 则使用对应的事件指令处理 可以同时用来等待移动的时间
        op: Optional[ZOperation] = None
        entry_name = next_to_move.entry.entry_name
        if entry_name in self._entry_event_handlers and not self.ctx.hollow.had_been_entry(entry_name):
            op = self._entry_event_handlers[entry_name](self.ctx)

        self.ctx.hollow.update_context_after_move(current_map, next_to_move)
        self._handled_events.clear()

        # 如果是特殊需要选项的格子 则使用对应的事件指令处理 可以同时用来等待移动的时间
        entry_name = next_to_move.entry.entry_name
        if op is not None:
            op_result = op.execute()
            if op_result.success:
                events = self._entry_events.get(entry_name, [])
                for e in events:
                    self._handled_events.add(e)
                return self.round_wait()
            else:
                return self.round_retry()

        return self.round_wait()

    def get_map_node_pos_to_click(self, screen: MatLike, node: HollowZeroMapNode) -> Point:
        """
        获取格子的点击位置 要避开画面上可能出现的选项
        :param screen: 游戏画面
        :param node: 需要点击的格子
        :return: 需要点击的位置
        """
        # 识别画面上是否有选项
        opt = hollow_event_utils.check_entry_opt_pos_at_right(self.ctx, screen, set())
        if opt is None:  # 没有选项的时候 随便点击
            return node.pos.center
        else:
            # 有选项的时候 点击离选项最远的一个角
            node_rect: Rect = node.pos
            opt_rect: Rect = opt.rect

            # 格子的4个角 往里面移动一点 防止最终点击到格子外
            offset = 15
            pos_list = [
                Point(node_rect.x1, node_rect.y1) + Point(offset, offset),
                Point(node_rect.x1, node_rect.y2) + Point(offset, -offset),
                Point(node_rect.x2, node_rect.y1) + Point(-offset, offset),
                Point(node_rect.x2, node_rect.y2) + Point(-offset, -offset),
            ]

            # 找出离选项中点最远的点
            target_pos = None
            for pos in pos_list:
                if target_pos is None or cal_utils.distance_between(pos, opt_rect.center) > cal_utils.distance_between(target_pos, opt_rect.center):
                    target_pos = pos

            return target_pos

    def _try_click_speed_up(self, screen: MatLike) -> None:
        # 快进
        if not self.ctx.hollow.speed_up_clicked:
            result = self.round_by_find_and_click_area(screen, '零号空洞-事件', '快进')
            time.sleep(0.2)
            if result.is_success:
                self.ctx.hollow.speed_up_clicked = True

    def _check_extra_task_finished(self, screen: MatLike, current_map: HollowZeroMap) -> bool:
        """
        判断额外业绩是否刷完了
        :param screen:
        :param current_map:
        :return:
        """
        level_info = self.ctx.hollow.level_info

        if self.ctx.hollow_zero_record.is_finished_by_day():
            # 已经完成了
            return True

        # 完成指定次数后才会触发刷业绩的选项
        if not self.ctx.hollow_zero_record.is_finished_by_weekly_times():
            return False

        if self.ctx.hollow_zero_config.extra_task == HollowZeroExtraTask.NONE.value.value:
            return False

        # 判断是否到达层数退出
        extra_exit_by_level: bool = False
        if current_map.contains_entry('业绩考察点空'):
            self.ctx.hollow_zero_record.no_eval_point = True
        if self.ctx.hollow_zero_config.extra_exit == HollowZeroExtraExitEnum.LEVEL_2_EVA.value.value:
            if level_info.level > 2 or (level_info.level == 2 and level_info.phase > 1):  # 已经过了指定的楼层
                extra_exit_by_level = True
            if level_info.level == 2 and level_info.phase == 1:
                if self.ctx.hollow.had_been_entry('业绩考察点') and not current_map.contains_entry('业绩考察点'):
                    extra_exit_by_level = True
                if current_map.contains_entry('业绩考察点空'):
                    extra_exit_by_level = True
        elif self.ctx.hollow_zero_config.extra_exit == HollowZeroExtraExitEnum.LEVEL_3_EVA.value.value:
            if level_info.level == 3 and level_info.phase > 1:  # 已经过了指定的楼层
                extra_exit_by_level = True
            if level_info.level == 3 and level_info.phase == 1:
                if self.ctx.hollow.had_been_entry('业绩考察点') and not current_map.contains_entry('业绩考察点'):
                    extra_exit_by_level = True
                if current_map.contains_entry('业绩考察点空'):
                    extra_exit_by_level = True


        if self.ctx.hollow_zero_config.extra_task == HollowZeroExtraTask.EVA_POINT.value.value:
            if self.ctx.hollow_zero_config.extra_exit == HollowZeroExtraExitEnum.COMPLETE.value.value:
                return False
            else:
                return extra_exit_by_level
        elif self.ctx.hollow_zero_config.extra_task == HollowZeroExtraTask.PERIOD_REWARD.value.value:
            # 周期性奖励在关键进展的战斗后判断
            if self.ctx.hollow_zero_config.extra_exit == HollowZeroExtraExitEnum.COMPLETE.value.value:
                return False
            else:
                return extra_exit_by_level

        return False

    def _save_debug_image(self, screen: MatLike,enforce:bool = False) -> None:
        """
        保存图片用于优化模型
        """
        if not ( self.ctx.env_config.is_debug or enforce ):
            return
        now = time.time()
        if now - self._last_save_image_time < 1:
            return
        self._last_save_image_time = now
        from one_dragon.utils import debug_utils
        debug_utils.save_debug_image(screen, prefix='pathfinding_fail')

    @node_from(from_name='画面识别', status=STATUS_LEAVE)
    @operation_node(name='离开空洞')
    def exit_hollow(self) -> OperationRoundResult:
        op = HollowExitByMenu(self.ctx)
        result = op.execute()
        if result.success:
            self.ctx.hollow_zero_record.add_daily_times()
        return self.round_by_op_result(result)

    @node_from(from_name='画面识别', status='通关-完成')
    @operation_node(name='通关-完成', node_max_retry_times=60)
    def mission_complete(self) -> OperationRoundResult:
        screen = self.screenshot()
        result = self.round_by_find_and_click_area(screen, '零号空洞-事件', '通关-完成')
        if result.is_success:
            reward = self.round_by_find_area(screen, '零号空洞-战斗', '通关-丁尼奖励')
            if not reward.is_success:
                # 领满奖励了
                self.ctx.hollow_zero_record.period_reward_complete = True
                self.save_screenshot()
            else:
                # 防止因为动画效果 奖励还没有出现 就出现了按钮
                self.ctx.hollow_zero_record.period_reward_complete = False
            return self.round_wait(result.status, wait=1)

        # 一直尝试点击直到出现街区
        result = self.round_by_find_area(screen, '零号空洞-入口', '街区')
        if result.is_success:
            self.ctx.hollow_zero_record.add_daily_times()
            return self.round_success(result.status)

        return self.round_retry(result.status, wait=1)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.start_running()
    ctx.init_ocr()
    ctx.hollow.init_before_hollow_start('旧都列车', '旧都列车-核心')
    op = HollowRunner(ctx)
    # from one_dragon.utils import debug_utils
    # screen = debug_utils.get_debug_image('_1723977819253')
    # result = op.round_by_find_and_click_area(screen, '零号空洞-事件', '快进')
    # print(result.is_success)
    op.execute()


if __name__ == '__main__':
    __debug()
