from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, HyperlinkCard

from one_dragon.utils.os_utils import get_work_dir
from one_dragon_qt.view.standalone_app_run_interface import StandaloneRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.context.zzz_context import ZContext


class ZStandaloneAppRunInterface(StandaloneRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        StandaloneRunInterface.__init__(
            self,
            ctx=ctx,
            object_name='standalone_app_run_interface',
            nav_text_cn='应用运行',
            nav_icon=FluentIcon.APPLICATION,
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        column = Column(spacing=4)
        column.add_widget(HelpCard(
            url='https://one-dragon.com/zzz/zh/feat/feat_standalone_app.html',
            title='应用运行说明',
            content='从应用列表中选择单个功能模块独立运行，无需跑完整的一条龙流程',
        ))
        column.add_widget(HelpCard(
            url='https://onedragon-anyone.github.io/plugin-registry/',
            text='前往应用商城',
            title='应用商城',
            content='插件由第三方提供, 请注意安全风险, 仅供学习交流使用',
        ))

        # 本地插件目录
        plugin_dir = Path(get_work_dir()) / 'plugins'
        folder_card = HyperlinkCard(
            plugin_dir.as_uri(), '打开目录', FluentIcon.FOLDER,
            '本地插件目录', '下载后解压到 plugins 目录',
        )
        folder_card.setFixedHeight(50)
        column.add_widget(folder_card)
        return column
