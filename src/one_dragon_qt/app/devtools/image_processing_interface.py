from qfluentwidgets import FluentIcon

from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from one_dragon_qt.app.devtools.image_stitching_interface import ImageStitchingInterface
from one_dragon_qt.app.devtools.image_matting_interface import ImageMattingInterface


class ImageProcessingInterface(PivotNavigatorInterface):
    """图像处理界面"""

    def __init__(self, ctx: OneDragonContext, parent=None):
        self.ctx: OneDragonContext = ctx
        
        PivotNavigatorInterface.__init__(
            self,
            object_name='image_processing_interface',
            nav_text_cn='图像处理',
            nav_icon=FluentIcon.PHOTO,
            parent=parent,
        )

    def create_sub_interface(self):
        """创建子界面"""
        
        # 图片拼接
        self.add_sub_interface(ImageStitchingInterface(self.ctx, parent=self))
        
        # 图像扣图
        self.add_sub_interface(ImageMattingInterface(self.ctx, parent=self))
