import os

from PySide6.QtGui import QImage, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, HyperlinkCard, ImageLabel

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.utils import cv2_utils, os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.cv2_image import Cv2Image
from one_dragon_qt.widgets.scroll_credits import ScrollCreditsWidget
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class LikeInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonEnvContext, parent=None):
        VerticalScrollInterface.__init__(self, object_name='like_interface',
                                         parent=parent, content_widget=None,
                                         nav_text_cn='点赞', nav_icon=FluentIcon.HEART)
        self.ctx: OneDragonEnvContext = ctx

    def get_content_widget(self) -> QWidget:
        # 主容器
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(40)

        # 左侧栏
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        star_opt = HyperlinkCard(icon=FluentIcon.HOME, title='Star', text=gt('前往'),
                                 content=gt('GitHub主页右上角点一个星星是最简单直接的'),
                                 url=self.ctx.project_config.github_homepage)
        star_opt.setFixedHeight(50)
        left_layout.addWidget(star_opt)

        help_opt = HyperlinkCard(icon=FluentIcon.HELP, title='访问GitHub指南', text=gt('前往'),
                                 content=gt('没法访问GitHub可以查看帮助文档'),
                                 url='https://one-dragon.com/other/zh/visit_github.html')
        help_opt.setFixedHeight(50)
        left_layout.addWidget(help_opt)

        cafe_opt = HyperlinkCard(icon=FluentIcon.CAFE, title='赞赏', text=gt('前往'),
                                 content=gt('如果喜欢本项目，你也可以为作者赞助一点维护费用~'),
                                 url='https://one-dragon.com/other/zh/like/like.html')
        cafe_opt.setFixedHeight(50)
        left_layout.addWidget(cafe_opt)

        # 左侧图片和遥测说明容器
        left_content_widget = QWidget()
        left_content_layout = QVBoxLayout(left_content_widget)
        left_content_layout.setContentsMargins(0, 0, 0, 0)
        left_content_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        left_content_layout.setSpacing(20)

        img_label = ImageLabel()
        img = cv2_utils.read_image(os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), 'sponsor_wechat.png'))
        image = Cv2Image(img) if img is not None else QImage()
        img_label.setImage(image)
        img_label.setFixedWidth(250)
        img_label.setFixedHeight(250)
        left_content_layout.addWidget(img_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 添加遥测说明文字
        telemetry_label = QLabel(gt('我们匿名收集你的信息用于改进我们的产品，感谢您的参与！'))
        telemetry_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        telemetry_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                padding: 10px;
                background-color: transparent;
            }
        """)
        left_content_layout.addWidget(telemetry_label)

        left_layout.addWidget(left_content_widget)
        left_layout.addStretch(1)

        # 右侧栏 - 滚动字幕
        scroll_credits = ScrollCreditsWidget(self.ctx)
        scroll_credits.setMinimumWidth(400)

        # 添加到主布局
        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(scroll_credits, 2)

        return main_widget
