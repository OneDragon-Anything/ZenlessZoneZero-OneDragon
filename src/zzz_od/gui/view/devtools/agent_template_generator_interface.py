from __future__ import annotations

import os
import re
from typing import Optional

from cv2.typing import MatLike
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (
    CaptionLabel,
    SimpleCardWidget,
    FluentIcon,
    InfoBarIcon,
    LineEdit,
    PrimaryPushButton,
    SubtitleLabel,
    BodyLabel,
)

from one_dragon.base.geometry.point import Point
from one_dragon.base.screen.template_info import TemplateInfo
from one_dragon.utils import cv2_utils, os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.devtools.template_card_widget import TemplateCardWidget


TEMPLATE_CONFIGS = [
    {
        'name': '1号位大头像',
        'sub_dir': 'battle',
        'template_id': 'avatar_1_{agent_id}',
        'template_ref': 'avatar_1_template',
    },
    {
        'name': '2号位小头像',
        'sub_dir': 'battle',
        'template_id': 'avatar_2_{agent_id}',
        'template_ref': 'avatar_2_template',
    },
    {
        'name': '连携头像',
        'sub_dir': 'battle',
        'template_id': 'avatar_chain_{agent_id}',
        'template_ref': 'avatar_chain_template',
    },
    {
        'name': '快速支援头像',
        'sub_dir': 'battle',
        'template_id': 'avatar_quick_{agent_id}',
        'template_ref': 'avatar_quick_template',
    },
    {
        'name': '零号空洞头像',
        'sub_dir': 'hollow',
        'template_id': 'avatar_{agent_id}',
        'template_ref': 'avatar_hollow_template',
    },
    {
        'name': '组队预设头像',
        'sub_dir': 'predefined_team',
        'template_id': 'avatar_{agent_id}',
        'template_ref': 'avatar_template_team',
    },
]


class AgentTemplateGeneratorInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='agent_template_generator_interface',
            nav_text_cn='代理人模板生成',
            nav_icon=FluentIcon.PEOPLE,
            parent=parent,
        )
        self.ctx: ZContext = ctx
        self.agent_id: Optional[str] = None
        self.last_screen_dir: Optional[str] = None
        self._template_ref_cache: dict[str, TemplateInfo] = {}
        self._agent_id_pattern = re.compile(r'^[a-z][a-z0-9_]*$')

    def get_content_widget(self) -> QWidget:
        # 创建居中容器
        center_widget = QWidget()
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # 左侧列：标题 + 输入
        left_column = Column(spacing=16, margins=(0, 0, 0, 0))
        left_column.setFixedWidth(300)
        center_layout.addWidget(left_column, alignment=Qt.AlignmentFlag.AlignTop)

        # 标题区域
        title_card = SimpleCardWidget()
        title_layout = Column(spacing=8, margins=(16, 16, 16, 16))
        QVBoxLayout(title_card).addWidget(title_layout)

        title_label = SubtitleLabel(text=gt('代理人模板生成'))
        title_layout.add_widget(title_label)

        hint_label = CaptionLabel(text=gt('为指定角色生成6个头像模板'))
        hint_label.setWordWrap(True)
        title_layout.add_widget(hint_label)

        left_column.add_widget(title_card)

        # 输入区域
        input_card = SimpleCardWidget()
        input_layout = Column(spacing=16, margins=(16, 16, 16, 16))
        QVBoxLayout(input_card).addWidget(input_layout)

        # 输入框
        self.agent_id_edit = LineEdit()
        self.agent_id_edit.setPlaceholderText(gt('输入代理人英文名'))
        self.agent_id_edit.textChanged.connect(self._on_agent_id_changed)
        input_layout.add_widget(self.agent_id_edit)

        # 一键生成按钮
        self.btn_generate_all = PrimaryPushButton(text=gt('一键生成'), icon=FluentIcon.PLAY)
        self.btn_generate_all.clicked.connect(self._on_generate_all_clicked)
        input_layout.add_widget(self.btn_generate_all)

        left_column.add_widget(input_card)

        # 截图说明卡片（紧贴输入卡片）
        hint_card = SimpleCardWidget()
        hint_layout = Column(spacing=12, margins=(16, 16, 16, 16))
        QVBoxLayout(hint_card).addWidget(hint_layout)

        hint_title = BodyLabel(text=gt('截图方法'))
        hint_layout.add_widget(hint_title)

        hint_items = [
            '1号大头像：3人组队，目标角色放前台',
            '2号小头像：目标角色放后台-1',
            '连携头像：2人队，触发目标角色连携',
            '快速支援：触发目标快速支援',
            '空洞头像：进入空洞后，目标角色在编队1号位',
            '预设编队：编队在第一个队伍第一位',
        ]

        for item in hint_items:
            item_label = CaptionLabel(text=item)
            hint_layout.add_widget(item_label)

        left_column.add_widget(hint_card)
        left_column.add_stretch(1)

        # 右侧列：6个模板卡片 - 垂直排列
        right_column = Column(spacing=16, margins=(8, 0, 8, 16))
        right_column.setFixedWidth(650)
        center_layout.addWidget(right_column, alignment=Qt.AlignmentFlag.AlignTop)

        # 模板卡片
        self.template_cards: list[TemplateCardWidget] = []
        for idx, config in enumerate(TEMPLATE_CONFIGS, start=1):
            title = config["name"]
            card = TemplateCardWidget(title=title, template_config=config)
            card.btn_choose_screenshot.clicked.connect(lambda _, c=card: self._on_choose_screenshot(c))
            card.btn_capture_game.clicked.connect(lambda _, c=card: self._on_capture_game(c))
            card.btn_save.clicked.connect(lambda _, c=card: self._on_save_template(c))
            card.set_buttons_enabled(False)
            self.template_cards.append(card)
            right_column.add_widget(card)

        return center_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

    def _set_agent_input_error(self, is_error: bool) -> None:
        if is_error:
            self.agent_id_edit.setProperty('error', True)
            self.agent_id_edit.setStyle(self.agent_id_edit.style())
        else:
            self.agent_id_edit.setProperty('error', False)
            self.agent_id_edit.setStyle(self.agent_id_edit.style())

    def _on_agent_id_changed(self, text: str) -> None:
        self._apply_agent_id(text)

    def _apply_agent_id(self, text: str) -> None:
        agent_id = text.strip().lower()
        previous_agent_id = self.agent_id
        if not agent_id:
            self.agent_id = None
            self._set_agent_input_error(False)
            self._set_cards_enabled(False)
            return

        if self._agent_id_pattern.fullmatch(agent_id) is None:
            self.agent_id = None
            self._set_agent_input_error(True)
            self._set_cards_enabled(False)
            return

        self.agent_id = agent_id
        self._set_agent_input_error(False)
        self._set_cards_enabled(True)
        if previous_agent_id != agent_id:
            for card in self.template_cards:
                card.reset_preview()

    def _set_cards_enabled(self, enabled: bool) -> None:
        for card in self.template_cards:
            card.set_buttons_enabled(enabled)
            if not enabled:
                card.reset_preview()

    def _get_template_ref(self, template_ref: str) -> Optional[TemplateInfo]:
        if template_ref in self._template_ref_cache:
            return self._template_ref_cache[template_ref]

        template = TemplateInfo('template', template_ref)
        if not template.is_file_exists:
            return None
        self._template_ref_cache[template_ref] = template
        return template

    def _preview_template_crop(self, template_ref: str, screen_image: MatLike) -> Optional[MatLike]:
        template = self._get_template_ref(template_ref)
        if template is None:
            return None
        template.screen_image = screen_image
        return template.get_template_raw_by_screen_point()

    def _save_template(self, agent_id: str, template_config: dict, screen_image: MatLike) -> bool:
        template_ref = template_config['template_ref']
        template_ref_info = self._get_template_ref(template_ref)
        if template_ref_info is None:
            return False

        sub_dir = template_config['sub_dir']
        template_id = template_config['template_id'].format(agent_id=agent_id)

        template = TemplateInfo(sub_dir, template_id)
        template.screen_image = screen_image
        template.template_shape = template_ref_info.template_shape
        template.point_list = [Point(p.x, p.y) for p in template_ref_info.point_list]
        template.auto_mask = template_ref_info.auto_mask

        template.save_raw()
        template.save_mask()
        return True

    def _get_template_id(self, template_config: dict) -> Optional[str]:
        if not self.agent_id:
            return None
        return template_config['template_id'].format(agent_id=self.agent_id)

    def _choose_screenshot(self) -> Optional[str]:
        default_dir = os_utils.get_path_under_work_dir('.debug', 'images')
        if self.last_screen_dir is not None:
            default_dir = self.last_screen_dir

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            gt('选择截图'),
            dir=default_dir,
            filter="PNG (*.png)",
        )
        if file_path:
            fix_file_path = os.path.normpath(file_path)
            self.last_screen_dir = os.path.dirname(fix_file_path)
            return fix_file_path
        return None

    def _on_choose_screenshot(self, card: TemplateCardWidget) -> None:
        if self.agent_id is None:
            self.show_info_bar(gt('提示'), gt('请先输入角色ID'), icon=InfoBarIcon.WARNING)
            return

        file_path = self._choose_screenshot()
        if file_path is None:
            return

        screen_image = cv2_utils.read_image(file_path)
        if screen_image is None:
            self.show_info_bar(gt('失败'), gt('截图读取失败'), icon=InfoBarIcon.ERROR)
            return
        self._preview_and_update(card, screen_image)

    def _on_capture_game(self, card: TemplateCardWidget) -> None:
        if self.agent_id is None:
            self.show_info_bar(gt('提示'), gt('请先输入角色ID'), icon=InfoBarIcon.WARNING)
            return

        _, screen = self.ctx.controller.screenshot()
        if screen is None:
            self.show_info_bar(gt('失败'), gt('游戏截图失败'), icon=InfoBarIcon.ERROR)
            return
        self._preview_and_update(card, screen)

    def _preview_and_update(self, card: TemplateCardWidget, screen_image: MatLike) -> None:
        preview_image = self._preview_template_crop(card.template_config['template_ref'], screen_image)
        if preview_image is None:
            self.show_info_bar(gt('失败'), gt('裁剪失败，请检查模板配置'), icon=InfoBarIcon.ERROR)
            return

        card.screen_image = screen_image
        card.set_preview_image(preview_image)
        card.is_saved = False
        card.btn_save.setEnabled(True)

    def _on_save_template(self, card: TemplateCardWidget) -> None:
        if self.agent_id is None:
            self.show_info_bar(gt('提示'), gt('请先输入角色ID'), icon=InfoBarIcon.WARNING)
            return
        if card.screen_image is None:
            self.show_info_bar(gt('提示'), gt('请先选择截图或游戏截图'), icon=InfoBarIcon.WARNING)
            return

        success = self._save_template(self.agent_id, card.template_config, card.screen_image)
        if success:
            card.set_saved(True)
        else:
            self.show_info_bar(gt('失败'), gt('模板保存失败'), icon=InfoBarIcon.ERROR)

    def _on_generate_all_clicked(self) -> None:
        if self.agent_id is None:
            self.show_info_bar(gt('提示'), gt('请先输入角色ID'), icon=InfoBarIcon.WARNING)
            return

        failed: list[str] = []
        for card in self.template_cards:
            screen = card.screen_image
            if screen is None:
                _, screen = self.ctx.controller.screenshot()
            if screen is None:
                failed.append(card.template_config['name'])
                continue

            preview_image = self._preview_template_crop(card.template_config['template_ref'], screen)
            if preview_image is not None:
                card.set_preview_image(preview_image)

            if self._save_template(self.agent_id, card.template_config, screen):
                card.set_saved(True)
            else:
                failed.append(card.template_config['name'])

        if failed:
            self.show_info_bar(gt('部分失败'), f"{gt('失败模板')}: {', '.join(failed)}", icon=InfoBarIcon.WARNING)
        else:
            self.show_info_bar(gt('成功'), gt('全部模板已生成'), icon=InfoBarIcon.SUCCESS)
