import time

import cv2
import difflib
from cv2.typing import MatLike
from typing import Optional, List

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_utils import FindAreaResultEnum
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event.event_ocr_result_handler import EventOcrResultHandler
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent, HallowZeroEvent
from zzz_od.operation.zzz_operation import ZOperation


def check_event_at_right(ctx: ZContext, screen: MatLike, ignore_events: set[str]) -> Optional[str]:
    """
    识别右边区域 当前是什么事件
    """
    area = get_event_text_area(ctx)
    part = cv2_utils.crop_image_only(screen, area.rect)
    white = cv2.inRange(part, (230, 230, 230), (255, 255, 255))
    white = cv2_utils.dilate(white, 5)
    to_ocr = cv2.bitwise_and(part, part, mask=white)
    ocr_result_map = ctx.ocr.run_ocr(to_ocr)

    event_name_list = []
    event_name_gt_list = []
    for event in ctx.hollow.data_service.normal_events:
        if event.event_name in ignore_events:
            continue
        event_name_list.append(event.event_name)
        event_name_gt_list.append(gt(event.event_name, 'game'))

    for event_enum in HollowZeroSpecialEvent:
        event = event_enum.value
        if not event.on_the_right:
            continue
        if event.is_entry_opt:
            continue
        if event.event_name in ignore_events:
            continue
        event_name_list.append(event.event_name)
        event_name_gt_list.append(gt(event.event_name, 'game'))

    # 事件标题一定在最上方 因此找y最小的
    min_y = 9999
    for ocr_result, mrl in ocr_result_map.items():
        if mrl.max.y < min_y:
            min_y = mrl.max.y

    ocr_result_list = []
    for ocr_result, mrl in ocr_result_map.items():
        if mrl.max.y - min_y < 20:
            ocr_result_list.append(ocr_result)

    event_idx, _ = str_utils.find_most_similar(event_name_gt_list, ocr_result_list)

    if event_idx is not None:
        return event_name_list[event_idx]


def check_entry_opt_at_right(ctx: ZContext, screen: MatLike, ignore_events: set[str]) -> Optional[str]:
    """
    识别右边区域 当前是否有事件的入口
    """
    mr = check_entry_opt_pos_at_right(ctx, screen, ignore_events)
    if mr is not None:
        event: HollowZeroSpecialEvent = mr.data
        return event.value.event_name


def check_entry_opt_pos_at_right(ctx: ZContext, screen: MatLike, ignore_events: set[str]) -> Optional[MatchResult]:
    """
    识别右边区域 当前是否有事件的入口
    返回的是带坐标的识别结果 MathcResult.data=HollowZeroSpecialEvent
    """
    area = ctx.screen_loader.get_area('零号空洞-事件', '格子入口选项')
    part = cv2_utils.crop_image_only(screen, area.rect)
    white = cv2.inRange(part, (230, 230, 230), (255, 255, 255))
    white = cv2_utils.dilate(white, 5)
    to_ocr = cv2.bitwise_and(part, part, mask=white)
    ocr_result_map = ctx.ocr.run_ocr(to_ocr)

    event_enum_list = []
    event_name_gt_list = []

    for event_enum in HollowZeroSpecialEvent:
        event = event_enum.value
        if not event.on_the_right:
            continue
        if not event.is_entry_opt:
            continue
        if event.event_name in ignore_events:
            continue
        event_enum_list.append(event_enum)
        event_name_gt_list.append(gt(event.event_name, 'game'))

    # 事件标题一定在最上方 因此找y最小的
    min_y = 9999
    for ocr_result, mrl in ocr_result_map.items():
        if mrl.max.y < min_y:
            min_y = mrl.max.y

    ocr_result_list = []
    ocr_mrl_list = []
    for ocr_result, mrl in ocr_result_map.items():
        if mrl.max.y - min_y < 20:
            ocr_result_list.append(ocr_result)
            ocr_mrl_list.append(mrl)

    event_idx, ocr_idx = str_utils.find_most_similar(event_name_gt_list, ocr_result_list)

    if event_idx is not None:
        event = event_enum_list[event_idx]
        mr = ocr_mrl_list[ocr_idx].max
        mr.data = event
        mr.add_offset(area.left_top)
        return mr


def check_event_text_and_run(op: ZOperation, screen: MatLike, handlers: List[EventOcrResultHandler]) -> OperationRoundResult:
    """
    识别当前事件的文本 并做出选择
    """
    area = get_event_text_area(op.ctx)
    part = cv2_utils.crop_image_only(screen, area.rect)
    white = cv2.inRange(part, (230, 230, 230), (255, 255, 255))
    white = cv2_utils.dilate(white, 5)
    to_ocr = cv2.bitwise_and(part, part, mask=white)

    ocr_result_map = op.ctx.ocr.run_ocr(to_ocr)

    target_handler: Optional[EventOcrResultHandler] = None
    target_mrl: Optional[MatchResultList] = None

    event_mark_handler: Optional[EventOcrResultHandler] = None
    event_mark_mrl: Optional[MatchResultList] = None

    ocr_result_list: List[str] = []
    mrl_list: List[MatchResultList] = []
    bottom_opt_pos: Optional[MatchResult] = None  # 最下面的文本 用于兜底时候选择
    for ocr_result, mrl in ocr_result_map.items():
        mrl.add_offset(area.left_top)
        ocr_result_list.append(ocr_result)
        mrl_list.append(mrl)

        if bottom_opt_pos is None or mrl.max.center.y > bottom_opt_pos.center.y:
            bottom_opt_pos = mrl.max

    handler_str_list = [gt(handler.target_cn, 'game') for handler in handlers]

    # 由于选项和识别的文本都是多个，多对多的情况下需要双向匹配才算成功匹配
    for handler in handlers:
        handler_event_str = gt(handler.target_cn, 'game')
        results = difflib.get_close_matches(handler_event_str, ocr_result_list, n=1)

        if results is None or len(results) == 0:
            continue

        ocr_result = results[0]
        # 同时需要反向匹配到一样的
        results2 = difflib.get_close_matches(ocr_result, handler_str_list, n=1)
        if results2 is None or len(results2) == 0 or results2[0] != handler_event_str:
            continue

        ocr_result_idx = ocr_result_list.index(ocr_result)
        mrl = mrl_list[ocr_result_idx]

        if handler.is_event_mark:
            if event_mark_handler is None:
                event_mark_handler = handler
                event_mark_mrl = mrl
        elif target_handler is None:
            target_handler = handler
            target_mrl = mrl

    if op.ctx.env_config.is_debug:
        # 调试模式下 不进行兜底 尽量补全事件选项
        bottom_opt_pos = None

    if target_handler is not None:
        log.debug('识别事件选项 %s' % target_handler.target_cn)
        return run_event_handler(op, target_handler, target_mrl.max)
    elif event_mark_handler is not None:
        log.debug('识别事件无选项 %s' % event_mark_handler.target_cn)
        return click_empty(op, bottom_opt_pos)
    else:
        click_empty(op, bottom_opt_pos)  # 做一个兜底点击 感觉可以跟上面合并
        return op.round_retry('未匹配合适的处理方法', wait=1)


def click_empty(op: ZOperation, bottom_opt_pos: Optional[MatchResult] = None) -> OperationRoundResult:
    if bottom_opt_pos is not None:
        op.ctx.controller.click(bottom_opt_pos.center)
        time.sleep(0.2)
    return op.round_by_click_area('零号空洞-事件', '事件文本', click_left_top=True,
                                  success_wait=0.2, retry_wait=0.2)


def click_rect(op: ZOperation, status: str, rect: Rect, wait: float = 1) -> OperationRoundResult:
    """
    点击一个位置
    """
    click = op.ctx.controller.click(rect.center)
    if click:
        time.sleep(0.1)
        click_empty(op)
        return op.round_success(status, wait=wait)
    else:
        return op.round_retry(f'点击失败 {status}', wait=1)


def get_event_text_area(ctx: ZContext) -> ScreenArea:
    """
    获取事件文本区域
    """
    return ctx.screen_loader.get_area('零号空洞-事件', '事件文本')


def run_event_handler(op: ZOperation, handler: EventOcrResultHandler, mr: MatchResult) -> OperationRoundResult:
    if handler.method is None:
        if handler.click_result:
            return click_rect(op, handler.status, mr.rect, wait=handler.click_wait)
    else:
        return handler.method(handler.target_cn, mr.rect)

    return op.round_retry(f'未配置应对方法 {handler.status}', wait=1)


def check_dialog_confirm(op: ZOperation, screen: MatLike) -> Optional[str]:
    """
    是有有对话框的确认
    """
    result = op.round_by_find_area(screen, '零号空洞-事件', '消息-确认')
    if result.is_success:
        return result.status
    else:
        return None


def check_bottom_choose(ctx: ZContext, screen: MatLike) -> Optional[str]:
    """
    底部是否有 选择、确认、催化、丢弃、交换、抵押欠款
    - 鸣徽选择、催化
    - 奖励确认
    - 邦布选择
    """
    area = ctx.screen_loader.get_area('零号空洞-事件', '底部-选择列表')
    part = cv2_utils.crop_image_only(screen, area.rect)
    ocr_result_map = ctx.ocr.run_ocr(part)

    event_list = [
        HollowZeroSpecialEvent.RESONIUM_CHOOSE.value,
        HollowZeroSpecialEvent.RESONIUM_CONFIRM_1.value,
        HollowZeroSpecialEvent.RESONIUM_CONFIRM_2.value,
        HollowZeroSpecialEvent.RESONIUM_UPGRADE.value,
        HollowZeroSpecialEvent.RESONIUM_DROP.value,
        HollowZeroSpecialEvent.RESONIUM_DROP_2.value,
        HollowZeroSpecialEvent.RESONIUM_SWITCH.value,
        HollowZeroSpecialEvent.SWIFT_SUPPLY_LIFE.value,
        HollowZeroSpecialEvent.SWIFT_SUPPLY_COIN.value,
        HollowZeroSpecialEvent.SWIFT_SUPPLY_PRESS.value
    ]

    for event in event_list:
        for ocr_result in ocr_result_map.keys():
            if str_utils.find_by_lcs(gt(event.event_name, 'game'), ocr_result, percent=event.lcs_percent):
                return event.event_name


def check_bottom_remove(ctx: ZContext, screen: MatLike) -> Optional[str]:
    """
    底部是否有 清除
    - 侵蚀症状
    """
    area = ctx.screen_loader.get_area('零号空洞-事件', '底部-清除列表')
    part = cv2_utils.crop_image_only(screen, area.rect)
    ocr_result_map = ctx.ocr.run_ocr(part)

    event = HollowZeroSpecialEvent.CORRUPTION_REMOVE.value
    for ocr_result in ocr_result_map.keys():
        if str_utils.find_by_lcs(gt(event.event_name, 'game'), ocr_result, percent=event.lcs_percent):
            return event.event_name


def check_full_in_bag(ctx: ZContext, screen: MatLike) -> Optional[str]:
    """
    中间是否有背包已满
    """
    result = screen_utils.find_area(ctx, screen, '零号空洞-事件', '背包已满')
    if result == FindAreaResultEnum.TRUE:
        return HollowZeroSpecialEvent.FULL_IN_BAG.value.event_name


def check_screen(ctx: ZContext, screen: MatLike, ignore_events: set[str]) -> Optional[str]:
    """
    识别当前画面的状态
    :param ignore_events: 忽略的事件 当前只有格子的入口选项需要忽略
    """
    choose = check_bottom_choose(ctx, screen)
    if choose is not None:
        return choose

    event = check_event_at_right(ctx, screen, ignore_events)
    if event is not None:
        return event

    event = check_entry_opt_at_right(ctx, screen, ignore_events)
    if event is not None:
        return event

    # 不同的消息框高度不一样 很难捕捉到确定的按钮
    # confirm = check_dialog_confirm(op, screen)
    # if confirm is not None:
    #     return confirm

    remove = check_bottom_remove(ctx, screen)
    if remove is not None:
        return remove

    battle = check_battle_screen(ctx, screen)
    if battle is not None:
        return battle

    complete = check_mission_complete(ctx, screen)
    if complete is not None:
        return complete

    full_in_bag = check_full_in_bag(ctx, screen)
    if full_in_bag is not None:
        return full_in_bag

    # 零号银行 不宜久留 会触发这个，启用的话会卡死在银行
    # need_interact = check_interact(ctx, screen)
    # if need_interact is not None:
    #     return need_interact

    in_hollow = check_in_hollow(ctx, screen)
    if in_hollow is not None:
        return in_hollow

    old_capital = check_old_capital(ctx, screen)
    if old_capital is not None:
        return old_capital

def check_battle_screen(ctx: ZContext, screen: MatLike) -> Optional[str]:
    result = screen_utils.find_area(ctx, screen, '战斗画面', '按键-普通攻击')

    if result == FindAreaResultEnum.TRUE:
        return HollowZeroSpecialEvent.IN_BATTLE.value.event_name


def check_mission_complete(ctx: ZContext, screen: MatLike) -> Optional[str]:
    result = screen_utils.find_area(ctx, screen, '零号空洞-事件', '通关-完成')

    if result == FindAreaResultEnum.TRUE:
        return HollowZeroSpecialEvent.MISSION_COMPLETE.value.event_name


def check_in_hollow(ctx: ZContext, screen: MatLike) -> Optional[str]:
    result = screen_utils.find_area(ctx=ctx, screen=screen,
                                    screen_name='零号空洞-事件', area_name='背包')

    if result == FindAreaResultEnum.TRUE:
        return HollowZeroSpecialEvent.HOLLOW_INSIDE.value.event_name


def check_old_capital(ctx: ZContext, screen: MatLike) -> Optional[str]:
    """
    旧都失物 左上角的返回
    """
    result = screen_utils.find_area(ctx=ctx, screen=screen,
                                    screen_name='零号空洞-事件', area_name='旧都失物-返回')

    if result == FindAreaResultEnum.TRUE:
        return HollowZeroSpecialEvent.OLD_CAPITAL.value.event_name


def get_special_event_by_name(event_name: str) -> Optional[HallowZeroEvent]:
    """
    根据事件名称 获取对应的特殊事件
    """
    for event_enum in HollowZeroSpecialEvent:
        event = event_enum.value
        if event.event_name == event_name:
            return event

def check_interact(ctx: ZContext, screen: MatLike) -> Optional[str]:
    """
    识别下方是否有提示交互的文本
    @param ctx: 上下文
    @param screen: 游戏画面
    @return:
    """
    result = screen_utils.find_area(ctx=ctx, screen=screen,
                                    screen_name='零号空洞-事件', area_name='交互可再次触发事件')
    if result == FindAreaResultEnum.TRUE:
        return HollowZeroSpecialEvent.NEED_INTERACT.value.event_name
