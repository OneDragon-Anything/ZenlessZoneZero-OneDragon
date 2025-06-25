# coding: utf-8
from typing import Dict, Any
from one_dragon.base.cv_process.cv_step import CvStep, CvPipelineContext


class CvStepCropByArea(CvStep):

    def __init__(self):
        super().__init__('按区域裁剪')

    def get_params(self) -> Dict[str, Any]:
        return {
            'screen_name': {'type': 'enum_screen_name', 'default': '', 'label': '画面名称', 'tooltip': '选择一个已定义的画面。'},
            'area_name': {'type': 'enum_area_name', 'default': '', 'label': '区域名称', 'tooltip': '选择该画面下的一个区域进行裁剪。', 'parent': 'screen_name'}
        }

    def get_description(self) -> str:
        return "根据画面和区域的名称，从画面配置中找到对应区域进行裁剪。"

    def _execute(self, context: CvPipelineContext, screen_name: str = '', area_name: str = '', **kwargs):
        if context.od_ctx is None or context.od_ctx.screen_loader is None:
            context.error_str = "错误: 缺少画面加载器 (ScreenLoader)"
            context.success = False
            return

        if not screen_name or not area_name:
            context.error_str = "错误: 未选择画面名称或区域名称"
            context.success = False
            return

        area = context.od_ctx.screen_loader.get_area(screen_name, area_name)
        if area is None:
            context.error_str = f"错误: 在画面 '{screen_name}' 中未找到区域 '{area_name}'"
            context.success = False
            return

        self._crop_image_and_update_context(context, area.rect, f"按区域 {screen_name}->{area_name} 裁剪")