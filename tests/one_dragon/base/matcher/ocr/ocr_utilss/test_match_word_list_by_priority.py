"""
测试 match_word_list_by_priority 函数的各种场景
"""

import pytest
from unittest.mock import patch

from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.matcher.ocr.ocr_utils import match_word_list_by_priority


class TestMatchWordListByPriority:
    @pytest.fixture
    def sample_ocr_result_map(self):
        """创建示例OCR结果映射"""
        result_map = {}

        # 创建一些匹配结果
        claim_result = MatchResultList(only_best=False)
        claim_result.append(MatchResult(0.9, 10, 10, 50, 20, data="领取"))
        result_map["领取"] = claim_result

        claimed_result = MatchResultList(only_best=False)
        claimed_result.append(MatchResult(0.8, 10, 40, 80, 20, data="已领取"))
        result_map["已领取"] = claimed_result

        start_result = MatchResultList(only_best=False)
        start_result.append(MatchResult(0.85, 10, 70, 60, 20, data="开始"))
        result_map["开始"] = start_result

        return result_map

    @pytest.fixture
    def empty_ocr_result_map(self):
        """创建空的OCR结果映射"""
        return {}

    @patch("one_dragon.base.matcher.ocr.ocr_utils.gt")
    @patch("one_dragon.utils.str_utils.find_best_match_by_difflib")
    def test_basic_priority_matching(
        self, mock_find_match, mock_gt, sample_ocr_result_map
    ):
        """测试基本的优先级匹配功能"""
        # Mock gt函数直接返回原值
        mock_gt.side_effect = lambda x, mode: x

        # Mock find_best_match_by_difflib 返回精确匹配
        mock_find_match.side_effect = (
            lambda word, targets: targets.index(word) if word in targets else None
        )

        word_list = ["领取", "已领取", "开始"]

        result_word, result_list = match_word_list_by_priority(
            sample_ocr_result_map, word_list
        )

        assert result_word == "领取"
        assert result_list is not None
        assert len(result_list) == 1
        assert result_list[0].data == "领取"

    @patch("one_dragon.base.matcher.ocr.ocr_utils.gt")
    @patch("one_dragon.utils.str_utils.find_best_match_by_difflib")
    def test_priority_order_respected(
        self, mock_find_match, mock_gt, sample_ocr_result_map
    ):
        """测试优先级顺序被正确遵循"""
        mock_gt.side_effect = lambda x, mode: x

        # 模拟所有词都能匹配，但应该返回优先级最高的
        mock_find_match.side_effect = (
            lambda word, targets: 0 if word == "开始" else targets.index(word)
        )

        word_list = ["开始", "领取", "已领取"]

        result_word, result_list = match_word_list_by_priority(
            sample_ocr_result_map, word_list
        )

        # 应该返回优先级最高的"开始"，即使"领取"在OCR结果中存在
        assert result_word == "开始"

    @patch("one_dragon.base.matcher.ocr.ocr_utils.gt")
    @patch("one_dragon.utils.str_utils.find_best_match_by_difflib")
    def test_ignore_list_functionality(
        self, mock_find_match, mock_gt, sample_ocr_result_map
    ):
        """测试忽略列表功能"""
        mock_gt.side_effect = lambda x, mode: x
        mock_find_match.side_effect = (
            lambda word, targets: targets.index(word) if word in targets else None
        )

        word_list = ["领取", "已领取", "开始"]
        ignore_list = ["领取"]  # 忽略"领取"

        result_word, result_list = match_word_list_by_priority(
            sample_ocr_result_map, word_list, ignore_list
        )

        # 应该跳过"领取"，返回"已领取"
        assert result_word == "已领取"
        assert result_list is not None

    @patch("one_dragon.base.matcher.ocr.ocr_utils.gt")
    @patch("one_dragon.utils.str_utils.find_best_match_by_difflib")
    def test_no_matches_found(self, mock_find_match, mock_gt, sample_ocr_result_map):
        """测试没有找到匹配时的情况"""
        mock_gt.side_effect = lambda x, mode: x
        mock_find_match.return_value = None  # 没有匹配

        word_list = ["不存在", "也不存在"]

        result_word, result_list = match_word_list_by_priority(
            sample_ocr_result_map, word_list
        )

        assert result_word is None
        assert result_list is None

    @patch("one_dragon.base.matcher.ocr.ocr_utils.gt")
    @patch("one_dragon.utils.str_utils.find_best_match_by_difflib")
    def test_empty_ocr_result_map(self, mock_find_match, mock_gt, empty_ocr_result_map):
        """测试空的OCR结果映射"""
        mock_gt.side_effect = lambda x, mode: x

        word_list = ["领取", "开始"]

        result_word, result_list = match_word_list_by_priority(
            empty_ocr_result_map, word_list
        )

        assert result_word is None
        assert result_list is None

    @patch("one_dragon.base.matcher.ocr.ocr_utils.gt")
    @patch("one_dragon.utils.str_utils.find_best_match_by_difflib")
    def test_empty_word_list(self, mock_find_match, mock_gt, sample_ocr_result_map):
        """测试空的词列表"""
        mock_gt.side_effect = lambda x, mode: x
        mock_find_match.return_value = None  # 对于空列表，永远返回 None

        word_list = []

        result_word, result_list = match_word_list_by_priority(
            sample_ocr_result_map, word_list
        )

        assert result_word is None
        assert result_list is None

    @patch("one_dragon.base.matcher.ocr.ocr_utils.gt")
    @patch("one_dragon.utils.str_utils.find_best_match_by_difflib")
    def test_i18n_translation(self, mock_find_match, mock_gt, sample_ocr_result_map):
        """测试国际化翻译功能"""
        # Mock gt函数返回翻译后的值
        mock_gt.side_effect = lambda x, mode: f"{x}_translated"

        # Mock find_best_match_by_difflib 匹配翻译后的值
        mock_find_match.return_value = 0

        word_list = ["领取", "开始"]

        result_word, result_list = match_word_list_by_priority(
            sample_ocr_result_map, word_list
        )

        # 验证gt被调用
        assert mock_gt.call_count == 2
        # 应该返回原始词，不是翻译后的词
        assert result_word == "领取"

    @patch("one_dragon.base.matcher.ocr.ocr_utils.gt")
    @patch("one_dragon.utils.str_utils.find_best_match_by_difflib")
    def test_multiple_matches_for_same_word(self, mock_find_match, mock_gt):
        """测试同一个词有多个匹配结果的情况"""
        mock_gt.side_effect = lambda x, mode: x
        mock_find_match.side_effect = (
            lambda word, targets: targets.index(word) if word in targets else None
        )

        # 创建包含多个匹配结果的OCR映射
        result_map = {}
        claim_results = MatchResultList(only_best=False)
        claim_results.append(MatchResult(0.9, 10, 10, 50, 20, data="领取"))
        claim_results.append(MatchResult(0.8, 70, 10, 50, 20, data="领取"))
        result_map["领取"] = claim_results

        word_list = ["领取"]

        result_word, result_list = match_word_list_by_priority(result_map, word_list)

        assert result_word == "领取"
        assert result_list is not None
        assert len(result_list) == 2

    @patch("one_dragon.base.matcher.ocr.ocr_utils.gt")
    @patch("one_dragon.utils.str_utils.find_best_match_by_difflib")
    def test_fuzzy_matching_with_difflib(
        self, mock_find_match, mock_gt, sample_ocr_result_map
    ):
        """测试使用difflib进行模糊匹配"""
        mock_gt.side_effect = lambda x, mode: x

        # 模拟模糊匹配情况：OCR识别结果"已领取*1"应该匹配到"已领取"
        def mock_fuzzy_match(word, targets):
            if "已领取*1" in word and "已领取" in targets:
                return targets.index("已领取")
            return targets.index(word) if word in targets else None

        # 创建包含模糊匹配的OCR映射
        fuzzy_result_map = {}
        claimed_result = MatchResultList(only_best=False)
        claimed_result.append(MatchResult(0.8, 10, 40, 100, 20, data="已领取*1"))
        fuzzy_result_map["已领取*1"] = claimed_result

        word_list = ["领取", "已领取"]
        mock_find_match.side_effect = mock_fuzzy_match

        result_word, result_list = match_word_list_by_priority(
            fuzzy_result_map, word_list
        )

        assert result_word == "已领取"
        assert result_list is not None
        assert result_list[0].data == "已领取*1"

    @patch("one_dragon.base.matcher.ocr.ocr_utils.gt")
    @patch("one_dragon.utils.str_utils.find_best_match_by_difflib")
    def test_all_ignored_words(self, mock_find_match, mock_gt, sample_ocr_result_map):
        """测试所有词都被忽略的情况"""
        mock_gt.side_effect = lambda x, mode: x
        mock_find_match.side_effect = (
            lambda word, targets: targets.index(word) if word in targets else None
        )

        word_list = ["领取", "已领取"]
        ignore_list = ["领取", "已领取"]  # 忽略所有词

        result_word, result_list = match_word_list_by_priority(
            sample_ocr_result_map, word_list, ignore_list
        )

        assert result_word is None
        assert result_list is None

    @patch("one_dragon.base.matcher.ocr.ocr_utils.gt")
    @patch("one_dragon.utils.str_utils.find_best_match_by_difflib")
    def test_partial_ignore_list(self, mock_find_match, mock_gt, sample_ocr_result_map):
        """测试部分忽略列表的情况"""
        mock_gt.side_effect = lambda x, mode: x
        mock_find_match.side_effect = (
            lambda word, targets: targets.index(word) if word in targets else None
        )

        word_list = ["领取", "已领取", "开始"]
        ignore_list = ["已领取"]  # 只忽略"已领取"

        result_word, result_list = match_word_list_by_priority(
            sample_ocr_result_map, word_list, ignore_list
        )

        # 应该返回"领取"，因为它是第一个非忽略的匹配项
        assert result_word == "领取"
        assert result_list is not None
        assert result_list[0].data == "领取"
