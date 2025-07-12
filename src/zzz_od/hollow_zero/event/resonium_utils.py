from cv2.typing import MatLike
from typing import List

from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.game_data.hollow_zero_resonium import Resonium


def get_to_choose_list(ctx: ZContext, screen: MatLike, target_cn: str, target_lcs_percent: float = 1) -> List[MatchResult]:
    """
    识别画面上的鸣徽
    :param screen:
    :param target_cn:
    :return: 按钮的位置 + data=对应鸣徽
    """
    result_list: List[MatchResult] = []

    for i in range(1, 4):
        name_area = ctx.screen_loader.get_area('零号空洞-事件', '鸣徽名称-%d' % i)
        confirm_area = ctx.screen_loader.get_area('零号空洞-事件', '鸣徽选择-%d' % i)

        name_full_str = ctx.ocr.run_ocr_single_line(cv2_utils.crop_image_only(screen, name_area.rect))

        confirm_str = ctx.ocr.run_ocr_single_line(cv2_utils.crop_image_only(screen, confirm_area.rect))
        confirm_str = confirm_str.strip()

        if not str_utils.find_by_lcs(gt(target_cn, 'game'), confirm_str, percent=target_lcs_percent):
            continue

        r = ctx.hollow.data_service.match_resonium_by_ocr_full(name_full_str)
        if r is None:
            continue

        mr = MatchResult(
            1, confirm_area.x1, confirm_area.y1, confirm_area.width, confirm_area.height,
            data=r
        )
        result_list.append(mr)

    return result_list


def choose_resonium_by_priority(item_list: List[Resonium], priority_list: List[str], only_priority: bool = False):
    """
    按优先级 找出第一个
    :param item_list:
    :param priority_list:
    :param only_priority: 结果只保留优先级的
    :return:
    """
    idx_list: List[int] = []  # 最终的下标排序结果

    # 按优先级顺序 将匹配的鸣徽下标加入
    # 同时 优先考虑等级高的
    for target_level in ['S', 'A', 'B', '']:
        for priority_item in priority_list:
            split_idx = priority_item.find(' ')
            if split_idx != -1:
                cate_name = priority_item[:split_idx]
                item_name = priority_item[split_idx + 1:]
            else:
                cate_name = priority_item
                item_name = ''

            for i in range(len(item_list)):
                if i in idx_list:  # 已经加入过了
                    continue
                item = item_list[i]

                if item.level != target_level:
                    continue

                if item.category != cate_name:  # 不符合分类
                    continue

                if item_name == '':  # 不需要匹配名称
                    idx_list.append(i)
                    continue

                if item.name == priority_item:  # 符合名称
                    idx_list.append(i)

    if only_priority:
        return idx_list

    # 不符合优先级的
    for level in ['S', 'A', 'B', '']:
        for i in range(len(item_list)):
            if item_list[i].level != level:
                continue
            if i in idx_list:
                continue
            idx_list.append(i)

    return idx_list
