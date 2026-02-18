import cv2
from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.matcher.match_result import MatchResultList, MatchResult
from one_dragon.base.screen.template_info import TemplateInfo
from one_dragon.base.screen.template_loader import TemplateLoader
from one_dragon.utils import cv2_utils
from one_dragon.utils.log_utils import log


class TemplateMatcher:

    def __init__(self, template_loader: TemplateLoader):
        self.template_loader: TemplateLoader = template_loader

    def match_template(self, source: MatLike,
                       template_sub_dir: str,
                       template_id: str,
                       template_type: str = 'raw',
                       threshold: float = 0.5,
                       mask: MatLike = None,
                       ignore_template_mask: bool = False,
                       only_best: bool = True,
                       ignore_inf: bool = True) -> MatchResultList:
        """
        在原图中 匹配模板 如果模板图中有掩码图 会自动使用
        :param source: 原图
        :param template_sub_dir: 模板的子文件夹
        :param template_id: 模板id
        :param template_type: 模板类型
        :param threshold: 匹配阈值
        :param mask: 额外使用的掩码 与原模板掩码叠加
        :param ignore_template_mask: 是否忽略模板自身的掩码
        :param only_best: 只返回最好的结果
        :param ignore_inf: 是否忽略无限大的结果
        :return: 所有匹配结果
        """
        template: TemplateInfo = self.template_loader.get_template(template_sub_dir, template_id)
        if template is None:
            log.error('未加载模板 %s' % template_id)
            return MatchResultList()

        mask_usage: Optional[MatLike] = None
        if not ignore_template_mask:
            mask_usage = cv2.bitwise_or(mask_usage, template.mask) if mask_usage is not None else template.mask
        if mask is not None:
            mask_usage = cv2.bitwise_or(mask_usage, mask) if mask_usage is not None else mask
        return cv2_utils.match_template(source, template.get_image(template_type), threshold, mask=mask_usage,
                                        only_best=only_best, ignore_inf=ignore_inf)

    def match_one_by_feature(self, source: MatLike,
                             template_sub_dir: str,
                             template_id: str,
                             source_mask: MatLike = None,
                             knn_distance_percent: float = 0.7
                             ) -> Optional[MatchResult]:
        """
        使用特征匹配找到模板的位置
        @param source:
        @param template_sub_dir:
        @param template_id:
        @param source_mask:
        @param knn_distance_percent: 越小要求匹配程度越高
        @return:
        """
        source_kps, source_desc = cv2_utils.feature_detect_and_compute(source, source_mask)
        template = self.template_loader.get_template(template_sub_dir, template_id)
        if template is None:
            return None
        template_kps, template_desc = template.features

        return cv2_utils.feature_match_for_one(
            source_kps, source_desc,
            template_kps, template_desc,
            template_width=template.raw.shape[1], template_height=template.raw.shape[0],
            source_mask=source_mask,
            knn_distance_percent=knn_distance_percent
        )

    def match_template_binary(self, source: MatLike,
                              template_sub_dir: str,
                              template_id: str,
                              threshold: float = 0.5,
                              binary_threshold: int = 127,
                              mask: MatLike = None,
                              ignore_template_mask: bool = False,
                              only_best: bool = True,
                              ignore_inf: bool = True) -> MatchResultList:
        """
        使用二值化图像进行模板匹配
        :param source: 原图
        :param template_sub_dir: 模板的子文件夹
        :param template_id: 模板id
        :param threshold: 匹配阈值
        :param binary_threshold: 二值化阈值，默认为127
        :param mask: 额外使用的掩码 与原模板掩码叠加
        :param ignore_template_mask: 是否忽略模板自身的掩码
        :param only_best: 只返回最好的结果
        :param ignore_inf: 是否忽略无限大的结果
        :return: 所有匹配结果
        """
        template: TemplateInfo = self.template_loader.get_template(template_sub_dir, template_id)
        if template is None:
            log.error('未加载模板 %s' % template_id)
            return MatchResultList()

        # 对原图和模板都进行二值化处理
        source_binary = cv2_utils.to_binary(source, threshold=binary_threshold)
        template_binary = cv2_utils.to_binary(template.raw, threshold=binary_threshold)

        # 处理掩码
        mask_usage: Optional[MatLike] = None
        if not ignore_template_mask and template.mask is not None:
            mask_usage = template.mask
        if mask is not None:
            mask_usage = cv2.bitwise_or(mask_usage, mask) if mask_usage is not None else mask

        # 使用二值化图像进行匹配
        return cv2_utils.match_template(
            source_binary,
            template_binary,
            threshold,
            mask=mask_usage,
            only_best=only_best,
            ignore_inf=ignore_inf
        )
