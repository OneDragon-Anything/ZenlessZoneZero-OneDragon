from __future__ import annotations

import contextlib
import ctypes
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import cv2
import pygit2
from cv2.typing import MatLike
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    BreadcrumbBar,
    CaptionLabel,
    FlowLayout,
    FluentIcon,
    InfoBarIcon,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    SegmentedWidget,
    SimpleCardWidget,
    SubtitleLabel,
    SwitchButton,
    ToolTipFilter,
    TransparentToolButton,
    getFont,
    themeColor,
)

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.template_info import (
    TemplateInfo,
    get_template_dir_path,
    get_template_raw_path,
)
from one_dragon.utils import cv2_utils, os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.config.agent_template_generator_config import AgentTemplateGeneratorConfig
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.devtools.agent_template_float_window import (
    AgentTemplateFloatWindow,
)
from zzz_od.gui.view.devtools.agent_template_hotkey import (
    HotkeyDialog,
    HotkeyListener,
    hotkey_keys,
    normalize_hotkey,
)
from zzz_od.gui.view.devtools.agent_template_list import (
    AgentTemplateItem,
    AgentTemplateList,
)
from zzz_od.gui.view.devtools.agent_template_widgets import (
    ImageSlot,
    ShortcutButton,
    StepThumb,
)


@dataclass(frozen=True)
class TemplateStep:
    """生成一个头像模板的步骤。"""

    key: str
    name: str
    hint: str  # 去游戏哪个画面截图 连携步骤含 {side}
    sub_dir: str
    template_id: str  # 含 {agent_id}
    template_ref: str  # assets/template/template 下的参考模板 提供裁剪区域
    side_selectable: bool = False  # 可选左侧或右侧头像

    def template_id_of(self, agent_id: str) -> str:
        return self.template_id.format(agent_id=agent_id)


@dataclass(frozen=True)
class HotkeyAction:
    """可设置快捷键的操作。"""

    key: str
    name: str
    default_value: str


TEMPLATE_STEPS: list[TemplateStep] = [
    TemplateStep('battle_1', '1 号位', '进入自由训练，配队编入三人，其中把目标角色设为 1 号位',
                 'battle', 'avatar_1_{agent_id}', 'avatar_1_template'),
    TemplateStep('battle_2', '2 号位', '进入自由训练，配队编入三人，其中把目标角色设为 2 号位',
                 'battle', 'avatar_2_{agent_id}', 'avatar_2_template'),
    TemplateStep('chain', '连携', '在自由训练中触发目标角色的连携技（{side}）',
                 'battle', 'avatar_chain_{agent_id}', 'avatar_chain_template', side_selectable=True),
    TemplateStep('quick', '快速支援', '在自由训练中触发目标角色的快速支援',
                 'battle', 'avatar_quick_{agent_id}', 'avatar_quick_template'),
    TemplateStep('hollow', '零号空洞', '进入零号空洞-枯萎之都（走格子）的随意关卡，并设置目标角色为编队 1 号位',
                 'hollow', 'avatar_{agent_id}', 'avatar_hollow_template'),
    TemplateStep('team', '预备编队', '菜单 > 更多 > 预备编队，目标角色在 1 号队伍 1 号位',
                 'predefined_team', 'avatar_{agent_id}', 'avatar_template_team'),
]

HOTKEY_ACTIONS: list[HotkeyAction] = [
    HotkeyAction('capture', '截图', 'f8'),
    HotkeyAction('next', '下一步', 'ctrl+f'),
    HotkeyAction('prev', '上一步', ''),
    HotkeyAction('main', '回到主界面', ''),
]

SCREEN_SIZE: tuple[int, int] = (1920, 1080)
PREVIEW_SIZE: tuple[int, int] = (960, 540)
SCROLL_BOTTOM_MARGIN: int = 11  # VerticalScrollInterface 在滚动内容末尾留出的空白
AGENT_ID_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')


class AgentTemplateGeneratorInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None) -> None:
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='agent_template_generator_interface',
            nav_text_cn='代理人模板生成',
            nav_icon=FluentIcon.PEOPLE,
            parent=parent,
        )
        self.ctx: ZContext = ctx
        self.config: AgentTemplateGeneratorConfig = AgentTemplateGeneratorConfig()

        self.editing: bool = False  # False 为列表页
        self.is_new: bool = True  # 新建时可以修改名称
        self.agent_id: str | None = None
        self.current_step: int = 0
        self.chain_side: str = 'left'
        self.screens: list[MatLike | None] = [None] * len(TEMPLATE_STEPS)  # 本次截图
        self.crops: list[MatLike | None] = [None] * len(TEMPLATE_STEPS)  # 本次截图的裁剪结果
        self.saved_crops: list[MatLike | None] = [None] * len(TEMPLATE_STEPS)  # 已保存的模板
        self.dirty: bool = False
        self.last_screen_dir: Path | None = None
        self._page_visible: bool = False
        self._template_ref_cache: dict[str, TemplateInfo] = {}

        self.hotkeys: dict[str, str] = {
            action.key: normalize_hotkey(self.config.get_hotkey(action.key, action.default_value))
            for action in HOTKEY_ACTIONS
        }
        self.hotkey_listener = HotkeyListener(parent=self)
        self.hotkey_listener.pressed.connect(self._on_hotkey_pressed)
        self._update_listener_combos()

        self.float_window: AgentTemplateFloatWindow | None = None

    def get_fixed_top_widget(self) -> QWidget:
        self.editor_top = QWidget()
        layout = QVBoxLayout(self.editor_top)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(12)

        self.breadcrumb = BreadcrumbBar()
        self.breadcrumb.setFont(getFont(20))
        self.breadcrumb.setSpacing(16)
        self.breadcrumb.addItem('list', gt('代理人模板'))
        self.breadcrumb.currentItemChanged.connect(self._on_breadcrumb_changed)
        layout.addWidget(self.breadcrumb)

        field_row = QHBoxLayout()
        field_row.setContentsMargins(0, 0, 0, 0)
        field_row.setSpacing(12)
        field_row.addWidget(BodyLabel(gt('名称')))
        self.agent_id_edit = LineEdit()
        self.agent_id_edit.setPlaceholderText(gt('代理人英文名'))
        self.agent_id_edit.setFixedWidth(320)
        self.agent_id_edit.textChanged.connect(self._on_agent_id_changed)
        field_row.addWidget(self.agent_id_edit)
        self.agent_id_error = CaptionLabel()
        self.agent_id_error.setTextColor('#c42b1c', '#ff99a4')
        self.agent_id_error.hide()
        field_row.addWidget(self.agent_id_error)
        field_row.addSpacing(12)
        field_row.addWidget(BodyLabel(gt('悬浮窗')))
        self.float_switch = SwitchButton()
        self.float_switch.setOnText(gt('开'))
        self.float_switch.setOffText(gt('关'))
        self.float_switch.checkedChanged.connect(self._on_float_toggled)
        field_row.addWidget(self.float_switch)
        field_row.addStretch(1)
        layout.addLayout(field_row)

        shortcut_row = QHBoxLayout()
        shortcut_row.setContentsMargins(0, 0, 0, 0)
        shortcut_row.setSpacing(24)
        self.shortcut_buttons: dict[str, ShortcutButton] = {}
        for action in HOTKEY_ACTIONS:
            item = QHBoxLayout()
            item.setContentsMargins(0, 0, 0, 0)
            item.setSpacing(8)
            item.addWidget(BodyLabel(gt(action.name)))
            btn = ShortcutButton()
            btn.setAccessibleName(gt(action.name))
            btn.clicked.connect(lambda _=False, a=action: self._on_shortcut_clicked(a))
            item.addWidget(btn)
            shortcut_row.addLayout(item)
            self.shortcut_buttons[action.key] = btn
        shortcut_row.addStretch(1)
        layout.addLayout(shortcut_row)
        self._refresh_shortcut_buttons()

        rail = QWidget()
        rail_layout = FlowLayout(rail, needAni=False)
        rail_layout.setContentsMargins(0, 0, 0, 0)
        rail_layout.setHorizontalSpacing(8)
        rail_layout.setVerticalSpacing(8)
        self.step_thumbs: list[StepThumb] = []
        for idx, step in enumerate(TEMPLATE_STEPS):
            thumb = StepThumb(gt(step.name))
            thumb.clicked.connect(lambda i=idx: self._show_step(i))
            rail_layout.addWidget(thumb)
            self.step_thumbs.append(thumb)
        layout.addWidget(rail)

        return self.editor_top

    def get_content_widget(self) -> QWidget:
        self.agent_list = AgentTemplateList()
        self.agent_list.new_requested.connect(lambda: self._open_editor(None))
        self.agent_list.open_requested.connect(self._open_editor)
        self.agent_list.delete_requested.connect(self._on_delete_agent)

        self.editor_card = SimpleCardWidget()
        layout = QVBoxLayout(self.editor_card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header_text = QVBoxLayout()
        header_text.setContentsMargins(0, 0, 0, 0)
        header_text.setSpacing(8)
        self.step_title = SubtitleLabel()
        header_text.addWidget(self.step_title)
        self.step_hint = BodyLabel()
        self.step_hint.setWordWrap(True)
        header_text.addWidget(self.step_hint)
        header.addLayout(header_text, stretch=1)
        self.side_switch = SegmentedWidget()
        self.side_switch.addItem('left', gt('左侧'))
        self.side_switch.addItem('right', gt('右侧'))
        self.side_switch.setCurrentItem(self.chain_side)
        self.side_switch.currentItemChanged.connect(self._on_side_changed)
        header.addWidget(self.side_switch, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        images = QHBoxLayout()
        images.setContentsMargins(0, 0, 0, 0)
        images.setSpacing(12)
        self.screen_slot = ImageSlot(480, 270)
        self.crop_slot = ImageSlot(270, 270)
        images.addWidget(self.screen_slot)
        images.addWidget(self.crop_slot)
        images.addStretch(1)
        layout.addLayout(images)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        self.btn_capture = PrimaryPushButton(FluentIcon.CAMERA, gt('截图'))
        self.btn_capture.clicked.connect(self._capture_current)
        self.btn_retake = PushButton(FluentIcon.CAMERA, gt('重拍'))
        self.btn_retake.clicked.connect(self._capture_current)
        self.btn_open_file = TransparentToolButton(FluentIcon.FOLDER)
        self.btn_open_file.setToolTip(gt('从文件选择'))
        self.btn_open_file.setAccessibleName(gt('从文件选择'))
        self.btn_open_file.installEventFilter(ToolTipFilter(self.btn_open_file))
        self.btn_open_file.clicked.connect(self._on_choose_screenshot)
        actions.addWidget(self.btn_capture)
        actions.addWidget(self.btn_retake)
        actions.addWidget(self.btn_open_file)
        actions.addStretch(1)
        self.btn_prev = PushButton(gt('上一步'))
        self.btn_prev.clicked.connect(lambda: self._show_step(self.current_step - 1))
        self.btn_next = PrimaryPushButton(gt('下一步'))
        self.btn_next.clicked.connect(self._on_next_clicked)
        actions.addWidget(self.btn_prev)
        actions.addWidget(self.btn_next)
        layout.addLayout(actions)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.agent_list)
        content_layout.addWidget(self.editor_card)
        content_layout.addStretch(1)
        return content

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self._page_visible = True
        if self.editing:
            self._refresh_step()
            self.hotkey_listener.start()
        else:
            self._show_list(open_new_if_empty=True)

    def on_interface_hidden(self) -> None:
        self._page_visible = False
        if not self._is_float_visible():
            self.hotkey_listener.stop()
        VerticalScrollInterface.on_interface_hidden(self)

    def resizeEvent(self, e: QResizeEvent) -> None:
        VerticalScrollInterface.resizeEvent(self, e)
        QTimer.singleShot(0, self._fit_images)

    def _fit_images(self) -> None:
        """按可见高度缩放截图预览，编辑页不需要滚动。"""
        scroll_area = self.findChild(QScrollArea)
        if not self._init or scroll_area is None:
            return
        card_chrome = self.editor_card.sizeHint().height() - self.screen_slot.height()
        h = max(144, min(270, scroll_area.viewport().height() - card_chrome - SCROLL_BOTTOM_MARGIN))
        self.screen_slot.setFixedSize(h * 16 // 9, h)
        self.crop_slot.setFixedSize(h, h)

    # 列表

    def _local_agent_ids(self) -> list[str]:
        battle_dir = Path(os_utils.get_path_under_work_dir('assets', 'template', 'battle'))
        prefix = 'avatar_1_'
        return [
            p.name.removeprefix(prefix) for p in battle_dir.iterdir()
            if p.is_dir() and p.name.startswith(prefix) and p.name != f'{prefix}template'
        ]

    def _committed_agent_ids(self) -> set[str]:
        """当前提交中已有的代理人，读取失败时返回空集合。"""
        prefix = 'avatar_1_'
        try:
            repo = pygit2.Repository(os_utils.get_work_dir())
            tree = repo.head.peel(pygit2.Commit).tree / 'assets' / 'template' / 'battle'
            return {e.name.removeprefix(prefix) for e in tree if e.name.startswith(prefix)}
        except Exception:
            log.error('读取已提交的代理人模板失败', exc_info=True)
            return set()

    def _saved_raw_paths(self, agent_id: str) -> list[Path]:
        return [Path(get_template_raw_path(step.sub_dir, step.template_id_of(agent_id))) for step in TEMPLATE_STEPS]

    def _show_list(self, open_new_if_empty: bool = False) -> None:
        """列表页只显示未提交的代理人，最近修改的排在前面。"""
        committed = self._committed_agent_ids()
        quick_idx = next(i for i, step in enumerate(TEMPLATE_STEPS) if step.key == 'quick')
        rows: list[tuple[float, str, list[Path]]] = []
        for agent_id in self._local_agent_ids():
            if agent_id in committed:
                continue
            paths = [p for p in self._saved_raw_paths(agent_id) if p.exists()]
            rows.append((max((p.stat().st_mtime for p in paths), default=0), agent_id, paths))
        rows.sort(key=lambda row: (-row[0], row[1]))

        if not rows and open_new_if_empty:
            self._open_editor(None)
            return

        self.editing = False
        self.float_switch.setChecked(False)
        self.hotkey_listener.stop()
        self.editor_top.hide()
        self.editor_card.hide()
        self.agent_list.set_items([
            AgentTemplateItem(
                agent_id=agent_id,
                avatar=self._read_rgb(self._saved_raw_paths(agent_id)[quick_idx]),
                done_cnt=len(paths),
                total_cnt=len(TEMPLATE_STEPS),
            )
            for _, agent_id, paths in rows
        ])
        self.agent_list.show()

    def _on_delete_agent(self, agent_id: str) -> None:
        if agent_id in self._committed_agent_ids():
            return
        box = MessageBox(gt('删除 {name}？').format(name=agent_id), '', self.window())
        box.yesButton.setText(gt('删除'))
        box.cancelButton.setText(gt('取消'))
        if not box.exec():
            return
        for step in TEMPLATE_STEPS:
            template_dir = Path(get_template_dir_path(step.sub_dir, step.template_id_of(agent_id)))
            if template_dir.is_dir():
                shutil.rmtree(template_dir)
        self.show_info_bar(gt('已删除'), agent_id, icon=InfoBarIcon.SUCCESS)
        self._show_list()

    # 编辑页

    def _open_editor(self, agent_id: str | None) -> None:
        """进入编辑页，agent_id 为空时新建。"""
        self.screens = [None] * len(TEMPLATE_STEPS)
        self.crops = [None] * len(TEMPLATE_STEPS)
        self.dirty = False
        self.chain_side = 'left'
        self.side_switch.setCurrentItem('left')
        self.current_step = 0
        self.is_new = agent_id is None

        self.editing = True
        self.agent_list.hide()
        self.editor_top.show()
        self.editor_card.show()
        QTimer.singleShot(0, self._fit_images)

        self._set_breadcrumb_agent(agent_id or gt('新建'))
        self.agent_id_edit.setEnabled(self.is_new)
        self.agent_id_edit.setText(agent_id or '')
        self._on_agent_id_changed(agent_id or '')
        if self._page_visible:
            self.hotkey_listener.start()

    def _on_breadcrumb_changed(self, route_key: str) -> None:
        if route_key != 'list':
            return
        if self.dirty and not self._confirm_discard():
            # 点击面包屑时已移除了当前项 取消返回需要加回来
            self._set_breadcrumb_agent(self.agent_id_edit.text() or gt('新建'))
            return
        self._show_list()

    def _set_breadcrumb_agent(self, text: str) -> None:
        self.breadcrumb.blockSignals(True)
        if self.breadcrumb.count() < 2:
            self.breadcrumb.addItem('agent', text)
        else:
            self.breadcrumb.setItemText('agent', text)
        self.breadcrumb.blockSignals(False)

    def _confirm_discard(self) -> bool:
        box = MessageBox(gt('放弃未保存的截图？'), '', self.window())
        box.yesButton.setText(gt('放弃'))
        box.cancelButton.setText(gt('取消'))
        return bool(box.exec())

    def _on_agent_id_changed(self, text: str) -> None:
        agent_id = text.strip().lower()
        error = ''
        if agent_id and not AGENT_ID_PATTERN.fullmatch(agent_id):
            error = gt('只能用小写字母、数字和下划线，以字母开头')
        elif agent_id and self.is_new and agent_id in self._local_agent_ids():
            error = gt('这个名称已存在')
        self.agent_id = agent_id if agent_id and not error else None
        self.agent_id_edit.setError(bool(error))
        self.agent_id_error.setText(error)
        self.agent_id_error.setVisible(bool(error))
        self._load_saved_crops()
        self._refresh_step()

    def _load_saved_crops(self) -> None:
        if self.is_new or self.agent_id is None:
            self.saved_crops = [None] * len(TEMPLATE_STEPS)
        else:
            self.saved_crops = [self._read_rgb(p) for p in self._saved_raw_paths(self.agent_id)]

    @staticmethod
    def _read_rgb(path: Path) -> MatLike | None:
        image = cv2_utils.read_image(str(path))
        if image is not None and image.ndim == 3 and image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
        return image

    # 步骤

    @property
    def _is_last_step(self) -> bool:
        return self.current_step == len(TEMPLATE_STEPS) - 1

    def _display_crop(self, idx: int) -> MatLike | None:
        return self.crops[idx] if self.crops[idx] is not None else self.saved_crops[idx]

    def _step_done(self, idx: int) -> bool:
        return self._display_crop(idx) is not None

    def _can_save(self) -> bool:
        return (self.agent_id is not None
                and any(crop is not None for crop in self.crops)
                and all(self._step_done(i) for i in range(len(TEMPLATE_STEPS))))

    def _can_next(self) -> bool:
        return self._can_save() if self._is_last_step else self._step_done(self.current_step)

    def _show_step(self, idx: int) -> None:
        self.current_step = max(0, min(idx, len(TEMPLATE_STEPS) - 1))
        self._refresh_step()

    def _refresh_step(self) -> None:
        idx = self.current_step
        step = TEMPLATE_STEPS[idx]
        side = gt('右侧') if self.chain_side == 'right' else gt('左侧')

        self.step_title.setText(gt(step.name))
        self.step_hint.setText(gt(step.hint).format(side=side))
        self.side_switch.setVisible(step.side_selectable)
        self.screen_slot.set_image(self._screen_preview(idx))
        self.crop_slot.set_image(self._display_crop(idx))

        done = self._step_done(idx)
        self.btn_capture.setVisible(not done)
        self.btn_retake.setVisible(done)
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setText(gt('保存') if self._is_last_step else gt('下一步'))
        self.btn_next.setIcon(FluentIcon.SAVE if self._is_last_step else None)
        self.btn_next.setEnabled(self._can_next())

        for i, thumb in enumerate(self.step_thumbs):
            thumb.set_selected(i == idx)
            thumb.set_image(self._display_crop(i))

        self._refresh_float_window()

    def _on_next_clicked(self) -> None:
        if not self._can_next():
            return
        if self._is_last_step:
            self._save_all()
        else:
            self._show_step(self.current_step + 1)

    def _on_float_next_clicked(self) -> None:
        """悬浮窗和快捷键只推进步骤，最后一步回到主界面由用户点保存。"""
        if self._is_last_step:
            self._bring_main_window()
        elif self._can_next():
            self._show_step(self.current_step + 1)

    def _on_side_changed(self, side: str) -> None:
        self.chain_side = side
        for idx, step in enumerate(TEMPLATE_STEPS):
            if step.side_selectable and self.screens[idx] is not None:
                self.crops[idx] = self._crop(idx, self.screens[idx])
        self._refresh_step()

    # 截图与裁剪

    def _capture_current(self) -> None:
        controller = self.ctx.controller
        if controller is not None and not controller.is_game_window_ready:
            controller.init_game_win()
        if controller is None or not controller.is_game_window_ready:
            self.show_info_bar(gt('没找到游戏窗口'), '', icon=InfoBarIcon.ERROR)
            return
        try:
            _, screen = controller.screenshot()
        except Exception:
            log.error('代理人模板截图失败', exc_info=True)
            screen = None
        if screen is None:
            self.show_info_bar(gt('截图失败'), '', icon=InfoBarIcon.ERROR)
            return
        self._apply_screen(screen, save_debug=True)

    def _on_choose_screenshot(self) -> None:
        default_dir = self.last_screen_dir or self._debug_dir()
        file_path, _ = QFileDialog.getOpenFileName(self, gt('选择截图'), str(default_dir), 'PNG (*.png)')
        if not file_path:
            return
        self.last_screen_dir = Path(file_path).parent
        screen = self._read_rgb(Path(file_path))
        if screen is None:
            self.show_info_bar(gt('无法读取这张图片'), '', icon=InfoBarIcon.ERROR)
            return
        self._apply_screen(screen, save_debug=False)

    def _apply_screen(self, screen: MatLike, save_debug: bool) -> None:
        """截图只属于当前步骤，同时把整屏原图保存到 .debug 方便回看。"""
        idx = self.current_step
        step = TEMPLATE_STEPS[idx]
        if (screen.shape[1], screen.shape[0]) != SCREEN_SIZE:
            screen = cv2.resize(screen, SCREEN_SIZE, interpolation=cv2.INTER_AREA)

        crop = self._crop(idx, screen)
        if crop is None:
            self.show_info_bar(gt('缺少参考模板'), step.template_ref, icon=InfoBarIcon.ERROR)
            return

        self.screens[idx] = screen
        self.crops[idx] = crop
        self.dirty = True
        if save_debug:
            cv2_utils.save_image(screen, str(self._debug_dir() / f'{step.key}.png'))
        self._refresh_step()

    def _debug_dir(self) -> Path:
        return Path(os_utils.get_path_under_work_dir('.debug', 'agent_template'))

    def _get_template_ref(self, template_ref: str) -> TemplateInfo | None:
        if template_ref not in self._template_ref_cache:
            template = TemplateInfo('template', template_ref)
            if not template.is_file_exists:
                return None
            self._template_ref_cache[template_ref] = template
        return self._template_ref_cache[template_ref]

    def _offset_x(self, idx: int) -> int:
        """连携选右侧时，裁剪区域平移到右侧头像的位置。"""
        if not TEMPLATE_STEPS[idx].side_selectable or self.chain_side != 'right':
            return 0
        left = self.ctx.screen_loader.get_area('战斗画面', '连携技-1')
        right = self.ctx.screen_loader.get_area('战斗画面', '连携技-2')
        return right.rect.x1 - left.rect.x1

    def _ref_rect(self, idx: int) -> Rect | None:
        ref = self._get_template_ref(TEMPLATE_STEPS[idx].template_ref)
        rect = ref.get_template_rect_by_point() if ref is not None else None
        if rect is None:
            return None
        dx = self._offset_x(idx)
        return Rect(rect.x1 + dx, rect.y1, rect.x2 + dx, rect.y2)

    def _crop(self, idx: int, screen: MatLike) -> MatLike | None:
        rect = self._ref_rect(idx)
        return None if rect is None else cv2_utils.crop_image_only(screen, rect, copy=True)

    def _screen_preview(self, idx: int) -> MatLike | None:
        """缩小后的整屏图，并框出裁剪区域。"""
        screen = self.screens[idx]
        if screen is None:
            return None
        preview = cv2.resize(screen, PREVIEW_SIZE, interpolation=cv2.INTER_AREA)
        rect = self._ref_rect(idx)
        if rect is not None:
            scale = PREVIEW_SIZE[0] / SCREEN_SIZE[0]
            color = themeColor()
            cv2.rectangle(
                preview,
                (int(rect.x1 * scale) - 2, int(rect.y1 * scale) - 2),
                (int(rect.x2 * scale) + 2, int(rect.y2 * scale) + 2),
                (color.red(), color.green(), color.blue()),
                2,
            )
        return preview

    # 保存

    def _save_template(self, agent_id: str, idx: int) -> bool:
        step = TEMPLATE_STEPS[idx]
        ref = self._get_template_ref(step.template_ref)
        if ref is None:
            return False
        dx = self._offset_x(idx)
        template = TemplateInfo(step.sub_dir, step.template_id_of(agent_id))
        template.screen_image = self.screens[idx]
        template.template_shape = ref.template_shape
        template.point_list = [Point(p.x + dx, p.y) for p in ref.point_list]
        template.auto_mask = ref.auto_mask
        try:
            template.save_raw()
            template.save_mask()
            return True
        except Exception:
            log.error(f'保存模板失败 {step.sub_dir}/{template.template_id}', exc_info=True)
            return False

    def _save_all(self) -> None:
        """只保存本次重新截图的步骤，其余保留已有模板。"""
        if not self._can_save():
            return
        changed = [i for i, screen in enumerate(self.screens) if screen is not None]
        failed = [gt(TEMPLATE_STEPS[i].name) for i in changed if not self._save_template(self.agent_id, i)]
        if failed:
            self.show_info_bar(gt('部分模板没有保存'), '、'.join(failed), icon=InfoBarIcon.WARNING)
            return

        self.dirty = False
        self.show_info_bar(gt('已保存'), self.agent_id, icon=InfoBarIcon.SUCCESS)
        self._show_list()

    # 快捷键

    def _update_listener_combos(self) -> None:
        self.hotkey_listener.combos = {combo for combo in self.hotkeys.values() if combo}

    def _refresh_shortcut_buttons(self) -> None:
        for key, btn in self.shortcut_buttons.items():
            btn.set_keys(hotkey_keys(self.hotkeys[key]))

    def _on_shortcut_clicked(self, action: HotkeyAction) -> None:
        was_running = self.hotkey_listener.is_running
        dialog = HotkeyDialog(
            self.hotkey_listener, gt(action.name), self.hotkeys[action.key], action.default_value,
            parent=self.window(),
        )
        if dialog.exec():
            self.hotkeys[action.key] = normalize_hotkey(dialog.value)
            self.config.set_hotkey(action.key, self.hotkeys[action.key])
            self._update_listener_combos()
            self._refresh_shortcut_buttons()
        if not was_running:
            self.hotkey_listener.stop()

    def _on_hotkey_pressed(self, combo: str) -> None:
        if not self.editing:
            return
        actions = {key for key, value in self.hotkeys.items() if value == combo}
        if 'main' in actions:
            self._bring_main_window()
        elif 'prev' in actions:
            self._show_step(self.current_step - 1)
        elif {'capture', 'next'} <= actions:
            # 截图和下一步设为同一个键时 未完成先截图 已完成进入下一步
            if not self._step_done(self.current_step):
                self._capture_current()
            else:
                self._on_float_next_clicked()
        elif 'capture' in actions:
            self._capture_current()
        elif 'next' in actions:
            self._on_float_next_clicked()

    def _bring_main_window(self) -> None:
        win = self.window()
        if win.isMinimized():
            win.showNormal()
        win.raise_()
        win.activateWindow()
        # 游戏在前台时 Windows 不允许直接抢焦点 需要先挂接前台窗口的输入线程
        with contextlib.suppress(Exception):
            user32 = ctypes.windll.user32
            hwnd = int(win.winId())
            fg_tid = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
            cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
            attached = fg_tid != cur_tid and user32.AttachThreadInput(fg_tid, cur_tid, True)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            if attached:
                user32.AttachThreadInput(fg_tid, cur_tid, False)

    # 悬浮窗

    def _is_float_visible(self) -> bool:
        return self.float_window is not None and self.float_window.isVisible()

    def _on_float_toggled(self, checked: bool) -> None:
        if not checked:
            if self.float_window is not None:
                self.float_window.hide()
            if not self._page_visible:
                self.hotkey_listener.stop()
            return

        if self.float_window is None:
            self.float_window = AgentTemplateFloatWindow()
            self.float_window.capture_clicked.connect(self._capture_current)
            self.float_window.next_clicked.connect(self._on_float_next_clicked)
            self.float_window.close_clicked.connect(lambda: self.float_switch.setChecked(False))
            self.float_window.moved.connect(self._on_float_moved)
        self._refresh_float_window()
        self.float_window.show_at(self.config.float_x, self.config.float_y)
        self.hotkey_listener.start()

    def _on_float_moved(self, x: int, y: int) -> None:
        self.config.float_x = x
        self.config.float_y = y

    def _refresh_float_window(self) -> None:
        if self.float_window is None:
            return
        idx = self.current_step
        self.float_window.set_step(
            idx, len(TEMPLATE_STEPS), gt(TEMPLATE_STEPS[idx].name), self._display_crop(idx),
            can_next=self._is_last_step or self._step_done(idx), is_last=self._is_last_step,
        )
