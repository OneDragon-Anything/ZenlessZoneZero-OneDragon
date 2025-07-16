import os
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, HyperlinkCard, ImageLabel

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.utils import cv2_utils, os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.cv2_image import Cv2Image
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class LikeInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonEnvContext, parent=None):
        VerticalScrollInterface.__init__(self, object_name='like_interface',
                                         parent=parent, content_widget=None,
                                         nav_text_cn='点赞', nav_icon=FluentIcon.HEART)
        self.ctx: OneDragonEnvContext = ctx

    def get_content_widget(self) -> QWidget:
        content = Column()

        star_opt = HyperlinkCard(icon=FluentIcon.HOME, title='Star', text=gt('前往'),
                                 content=gt('GitHub主页右上角点一个星星是最简单直接的'),
                                 url=self.ctx.project_config.github_homepage)
        content.add_widget(star_opt)

        help_opt = HyperlinkCard(icon=FluentIcon.HELP, title='访问GitHub指南', text=gt('前往'),
                                 content=gt('没法访问GitHub可以查看帮助文档'),
                                 url='https://one-dragon.com/other/zh/visit_github.html')
        content.add_widget(help_opt)

        cafe_opt = HyperlinkCard(icon=FluentIcon.CAFE, title='赞赏', text=gt('前往'),
                                 content=gt('如果喜欢本项目，你也可以为作者赞助一点维护费用~'),
                                 url='https://one-dragon.com/other/zh/like/like.html')
        content.add_widget(cafe_opt)

        img_label = ImageLabel()
        img = cv2_utils.read_image(os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), 'sponsor_wechat.png'))
        image = Cv2Image(img)
        img_label.setImage(image)
        img_label.setFixedWidth(250)
        img_label.setFixedHeight(250)
        content.add_widget(img_label)

        content.add_stretch(1)
        return content


    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

