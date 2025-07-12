import difflib
import re
from typing import Optional, List, Tuple

from one_dragon.utils.i18_utils import gt

_WITH_CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]+')


def find(source: str, target: str, ignore_case: bool = False) -> int:
    """
    字符串find的封装 在原目标串中招目标字符串
    :param source: 原字符串
    :param target: 目标字符串
    :param ignore_case: 是否忽略大小写
    :return:
    """
    if source is None or target is None:
        return -1
    if ignore_case:
        return source.lower().find(target.lower())
    else:
        return source.find(target)


def find_by_lcs(source: str, target: str, percent: float = 0.3,
                ignore_case: bool = True) -> bool:
    """
    根据最长公共子序列长度和一定阈值 判断字符串是否有包含关系。
    用于OCR结果和目标的匹配
    :param source: OCR目标
    :param target: OCR结果
    :param percent: 最长公共子序列长度 需要占 source长度 的百分比
    :param ignore_case: 是否忽略大小写
    :return: 是否包含
    """
    if source is None or target is None or len(source) == 0 or len(target) == 0:
        return False
    source_usage = source.lower() if ignore_case else source
    target_usage = target.lower() if ignore_case else target

    common_length = longest_common_subsequence_length(source_usage, target_usage)

    return common_length >= len(source) * percent


def longest_common_subsequence_length(str1: str, str2: str) -> int:
    """
    找两个字符串的最长公共子序列长度
    :param str1:
    :param str2:
    :return: 长度
    """
    m = len(str1)
    n = len(str2)

    # 创建一个二维数组用于存储中间结果
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # 动态规划求解
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if str1[i - 1] == str2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    return dp[m][n]


def get_positive_digits(v: str, err: Optional[int] = None) -> Optional[int]:
    """
    返回字符串中的数字部分 不包含符号
    :param v: 字符串
    :param err: 原字符串中没有数字的话返回的值
    :return: 字符串中的数字
    """
    try:
        return int(remove_not_digit(v))
    except Exception:
        return err


def get_positive_float(v: str, err: Optional[int] = None) -> Optional[float]:
    """
    返回字符串中的数字部分 不包含符号
    :param v: 字符串
    :param err: 原字符串中没有数字的话返回的值
    :return: 字符串中的数字
    """
    try:
        fix = re.sub(r'[^\d.]+', '', v)
        return float(fix)
    except Exception:
        return err


def remove_not_digit(v: str) -> str:
    """
    移除字符串中的非数字部分
    :param v:
    :return:
    """
    return re.sub(r"\D", "", v)


def find_best_match_by_lcs(word: str, target_word_list: List[str],
                           lcs_percent_threshold: Optional[float] = None) -> Optional[int]:
    """
    在目标词中，找出LCS比例最大的
    :param word: 候选词
    :param target_word_list: 目标词列表
    :param lcs_percent_threshold: 要求的LCS阈值
    :return: 最符合的目标词的下标
    """
    target_idx: Optional[int] = None
    target_lcs_percent: Optional[float] = None

    for idx, target_word in enumerate(target_word_list):
        lcs = longest_common_subsequence_length(word, target_word)
        if lcs == 0:  # 至少要有一个匹配
            continue
        lcs_percent = lcs * 1.0 / len(target_word)
        if lcs_percent_threshold is not None and lcs_percent < lcs_percent_threshold:
            continue
        if target_idx is None or lcs_percent > target_lcs_percent:
            target_idx = idx
            target_lcs_percent = lcs_percent

    return target_idx


def find_best_match_by_difflib(word: str, target_word_list: List[str], cutoff=0.6) -> Optional[int]:
    """
    在目标列表中，找出最相近的一个词语对应的下标
    :param word:
    :param target_word_list:
    :return:
    """
    results = difflib.get_close_matches(word, target_word_list, n=1, cutoff=cutoff)
    if results is not None and len(results) > 0:
        return target_word_list.index(results[0])
    else:
        return None


def find_most_similar(str_list1: List[str], str_list2: List[str]) -> Tuple[Optional[int], Optional[int]]:
    """
    多个字符串之间的匹配 找出最匹配的一组下标
    :param str_list1:
    :param str_list2:
    :return:
    """
    for str1 in str_list1:
        str2_results = difflib.get_close_matches(str1, str_list2, n=1)
        if str2_results is None or len(str2_results) == 0:
            continue

        str2 = str2_results[0]

        str1_results = difflib.get_close_matches(str2, str_list1, n=1)
        if str1_results is None or len(str1_results) == 0 or str1_results[0] != str1:
            continue

        return (str_list1.index(str1_results[0]), str_list2.index(str2_results[0]))

    return (None, None)


def with_chinese(s: str) -> bool:
    """
    判断一个字符串是否包含中文
    """
    return _WITH_CHINESE_PATTERN.search(s) is not None


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    计算两个字符串之间的 Levenshtein 编辑距离
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def find_best_match_by_similarity(
    ocr_text: str,
    target_texts: List[str],
    threshold: float = 0.5
) -> Tuple[Optional[str], float]:
    """
    在目标列表中，根据编辑距离找出与OCR文本最相似的一个
    :param ocr_text: OCR识别出的文本
    :param target_texts: 目标文本列表
    :param threshold: 相似度阈值，高于此值才被认为有效
    :return: (最佳匹配的文本, 相似度分数)
    """
    if not ocr_text or not target_texts:
        return None, 0.0

    best_match = None
    highest_score = -1.0

    for target in target_texts:
        if not target:
            continue
        distance = levenshtein_distance(ocr_text, target)
        max_len = max(len(ocr_text), len(target))
        if max_len == 0:
            score = 1.0 if distance == 0 else 0.0
        else:
            score = 1.0 - (distance / max_len)

        if score > highest_score:
            highest_score = score
            best_match = target

    if highest_score >= threshold:
        return best_match, highest_score
    else:
        return None, highest_score


def is_target_after_ocr_list(
        target_cn: str,
        order_cn_list: list[str],
        ocr_result_list: list[str],
        gt_mode: str = 'game',
        cutoff: float = 0.6,
) -> bool:
    """
    根据已知的顺序列表，判断目标字符串是否在当前识别的文本列表后方出现

    通常用于一堆副本中找目标副本的位置

    Args:
        target_cn: 目标字符串
        order_cn_list: 已知的有序列表
        ocr_result_list: 当前画面识别的文本列表
        gt_mode: 多语言模式
        cutoff: 相似度阈值

    Returns:
        bool: 目标字符串是否在当前识别的文本列表后方出现
    """
    found_target: bool = False  # 遍历是否已经发现目标
    found_before_target: bool = False  # 遍历是否发现在目标前的内容

    for order_cn in order_cn_list:
        if target_cn == order_cn:
            found_target = True
            break

        target_idx = find_best_match_by_difflib(gt(order_cn, gt_mode), ocr_result_list, cutoff=cutoff)
        if target_idx is None or target_idx < 0:
            continue

        if not found_target:
            found_before_target = True

    return found_target and found_before_target
