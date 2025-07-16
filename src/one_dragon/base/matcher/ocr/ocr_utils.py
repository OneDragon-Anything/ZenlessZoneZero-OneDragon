from typing import List, Optional

from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt


def merge_ocr_result_to_single_line(ocr_map, join_space: bool = True) -> str:
    """
    将OCR结果合并成一行 用于过长的文体产生换行
    :param ocr_map: run_ocr的结果
    :param join_space: 连接时是否加入空格
    :return:
    """
    lines: List[List[MatchResult]] = []
    for text, result_list in ocr_map.items():
        for result in result_list:
            in_line: int = -1
            for line_idx in range(len(lines)):
                for line_item in lines[line_idx]:
                    if abs(line_item.center.y - result.center.y) <= 5:
                        in_line = line_idx
                        break
                if in_line != -1:
                    break

            if in_line == -1:
                lines.append([result])
            else:
                lines[in_line].append(result)

    result_str: str = ''
    for line in lines:
        sorted_line = sorted(line, key=lambda x: x.center.x)
        for result_item in sorted_line:
            if len(result_str) == 0:
                result_str = result_item.data
            else:
                result_str += (' ' if join_space else '') + result_item.data

    return result_str


def merge_ocr_result_to_multiple_line(ocr_map, join_space: bool = True, merge_line_distance: float = 40) -> dict[str, MatchResultList]:
    """
    将OCR结果合并成多行 用于过长的文体产生换行
    :param ocr_map: run_ocr的结果
    :param join_space: 连接时是否加入空格
    :param merge_line_distance: 多少行距内合并结果
    :return:
    """
    lines = []
    for text, result_list in ocr_map.items():
        for result in result_list:
            in_line: int = -1
            for line_idx in range(len(lines)):
                for line_item in lines[line_idx]:
                    if abs(line_item.center.y - result.center.y) <= merge_line_distance:
                        in_line = line_idx
                        break
                if in_line != -1:
                    break

            if in_line == -1:
                lines.append([result])
            else:
                lines[in_line].append(result)

    merge_ocr_result_map: dict[str, MatchResultList] = {}
    for line in lines:
        line_ocr_map = {}
        merge_result: MatchResult = MatchResult(1, 9999, 9999, 0, 0)
        for ocr_result in line:
            if ocr_result.data not in line_ocr_map:
                line_ocr_map[ocr_result.data] = MatchResultList()
            line_ocr_map[ocr_result.data].append(ocr_result)

            if ocr_result.x < merge_result.x:
                merge_result.x = ocr_result.x
            if ocr_result.y < merge_result.y:
                merge_result.y = ocr_result.y
            if ocr_result.x + ocr_result.w > merge_result.x + merge_result.w:
                merge_result.w = ocr_result.x + ocr_result.w - merge_result.x
            if ocr_result.y + ocr_result.h > merge_result.y + merge_result.h:
                merge_result.h = ocr_result.y + ocr_result.h - merge_result.y

        merge_result.data = merge_ocr_result_to_single_line(line_ocr_map, join_space=join_space)
        if merge_result.data not in merge_ocr_result_map:
            merge_ocr_result_map[merge_result.data] = MatchResultList()
        merge_ocr_result_map[merge_result.data].append(merge_result)

    return merge_ocr_result_map


def match_word_list_by_priority(
        ocr_result_map: dict[str, MatchResultList],
        word_list: list[str],
        ignore_list: Optional[list[str]] = None
) -> tuple[str, MatchResultList]:
    """
    在OCR匹配结果中 找到目标匹配结果
    最终按传入word_list的顺序 返回第一个匹配的结果
    :param ocr_result_map: OCR识别结果
    :param word_list: 按顺序匹配的目标列表
    :param ignore_list: 目标列表中部分元素只是为了防止匹配错误例如传入 ["领取", "已领取"] 可以防止 "已领取*1" 匹配到 "领取"，而"已领取"又不需要真正匹配
    :return: 匹配结果
    """
    to_match_list: list[str] = [
        gt(i, 'game') for i in word_list
    ]
    match_map: dict[str, MatchResultList] = {}
    for ocr_result, mrl in ocr_result_map.items():
        match_idx: int = str_utils.find_best_match_by_difflib(ocr_result, to_match_list)
        if match_idx is None or match_idx < 0:
            continue

        match_word: str = word_list[match_idx]
        if match_word not in match_map:
            match_map[match_word] = MatchResultList(only_best=False)

        match_map[match_word].extend(mrl)

    for word in word_list:
        if ignore_list is not None and word in ignore_list:
            continue
        result = match_map.get(word)
        if result is not None:
            return word, result

    return None, None
