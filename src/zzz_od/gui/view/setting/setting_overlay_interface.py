from __future__ import annotations

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, SettingCardGroup

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.overlay.overlay_config import OverlayConfig
from one_dragon_qt.overlay.overlay_manager import OverlayManager
from one_dragon_qt.overlay.utils import win32_utils
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.key_setting_card import KeySettingCard
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.context.zzz_context import ZContext


class SettingOverlayInterface(VerticalScrollInterface):
    """Overlay settings page."""

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx = ctx
        self.config = OverlayConfig()

        super().__init__(
            content_widget=None,
            object_name="setting_overlay_interface",
            nav_text_cn="Overlay",
            nav_icon=FluentIcon.VIEW,
            parent=parent,
        )

    def get_content_widget(self) -> QWidget:
        content_widget = Column()
        content_widget.add_widget(self._init_basic_group())
        content_widget.add_widget(self._init_panel_group())
        content_widget.add_stretch(1)
        return content_widget

    def _init_basic_group(self) -> SettingCardGroup:
        group = SettingCardGroup(gt("Overlay 基础"))

        self.enabled_opt = SwitchSettingCard(
            icon=FluentIcon.PLAY,
            title="启用 Overlay",
            content="启用后可通过 Ctrl+Alt+O 切换显隐",
        )
        self.enabled_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.enabled_opt)

        self.toggle_hotkey_opt = KeySettingCard(
            icon=FluentIcon.SETTING,
            title="显隐热键主键",
            content="组合键固定 Ctrl+Alt，主键可自定义",
        )
        self.toggle_hotkey_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.toggle_hotkey_opt)

        self.visible_opt = SwitchSettingCard(
            icon=FluentIcon.VIEW,
            title="默认显示",
            content="启动后 Overlay 是否默认可见",
        )
        self.visible_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.visible_opt)

        self.anti_capture_opt = SwitchSettingCard(
            icon=FluentIcon.CAMERA,
            title="防截图保护",
            content="使用 WDA_EXCLUDEFROMCAPTURE 隐藏 Overlay",
        )
        self.anti_capture_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.anti_capture_opt)

        return group

    def _init_panel_group(self) -> SettingCardGroup:
        group = SettingCardGroup(gt("面板与刷新"))

        self.log_panel_opt = SwitchSettingCard(
            icon=FluentIcon.DOCUMENT,
            title="显示日志面板",
        )
        self.log_panel_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.log_panel_opt)

        self.state_panel_opt = SwitchSettingCard(
            icon=FluentIcon.SETTING,
            title="显示状态面板",
        )
        self.state_panel_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.state_panel_opt)

        self.font_size_opt = SpinBoxSettingCard(
            icon=FluentIcon.SETTING,
            title="字体大小",
            minimum=10,
            maximum=28,
            step=1,
        )
        self.font_size_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.font_size_opt)

        self.text_opacity_opt = SpinBoxSettingCard(
            icon=FluentIcon.SETTING,
            title="文字透明度(%)",
            minimum=20,
            maximum=100,
            step=5,
        )
        self.text_opacity_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.text_opacity_opt)

        self.panel_opacity_opt = SpinBoxSettingCard(
            icon=FluentIcon.SETTING,
            title="面板透明度(%)",
            minimum=20,
            maximum=100,
            step=5,
        )
        self.panel_opacity_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.panel_opacity_opt)

        self.log_max_lines_opt = SpinBoxSettingCard(
            icon=FluentIcon.SETTING,
            title="日志最大行数",
            minimum=20,
            maximum=500,
            step=10,
        )
        self.log_max_lines_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.log_max_lines_opt)

        self.log_fade_seconds_opt = SpinBoxSettingCard(
            icon=FluentIcon.SETTING,
            title="日志过期秒数",
            minimum=3,
            maximum=120,
            step=1,
        )
        self.log_fade_seconds_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.log_fade_seconds_opt)

        self.follow_interval_opt = SpinBoxSettingCard(
            icon=FluentIcon.ZOOM,
            title="窗口跟随间隔(ms)",
            minimum=30,
            maximum=500,
            step=10,
        )
        self.follow_interval_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.follow_interval_opt)

        self.state_interval_opt = SpinBoxSettingCard(
            icon=FluentIcon.SYNC,
            title="状态刷新间隔(ms)",
            minimum=80,
            maximum=1000,
            step=20,
        )
        self.state_interval_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.state_interval_opt)

        self.reset_geometry_opt = PushSettingCard(
            icon=FluentIcon.SYNC,
            title="重置面板位置",
            text="重置",
            content="重置日志/状态面板到默认位置与尺寸",
        )
        self.reset_geometry_opt.clicked.connect(self._on_reset_geometry_clicked)
        group.addSettingCard(self.reset_geometry_opt)

        return group

    def on_interface_shown(self) -> None:
        super().on_interface_shown()
        self.config = OverlayConfig()

        self.enabled_opt.init_with_adapter(self.config.get_prop_adapter("enabled"))
        self.toggle_hotkey_opt.init_with_adapter(self.config.get_prop_adapter("toggle_hotkey"))
        self.visible_opt.init_with_adapter(self.config.get_prop_adapter("visible"))
        self.anti_capture_opt.init_with_adapter(self.config.get_prop_adapter("anti_capture"))
        self.log_panel_opt.init_with_adapter(self.config.get_prop_adapter("log_panel_enabled"))
        self.state_panel_opt.init_with_adapter(self.config.get_prop_adapter("state_panel_enabled"))
        self.font_size_opt.init_with_adapter(self.config.get_prop_adapter("font_size"))
        self.text_opacity_opt.init_with_adapter(self.config.get_prop_adapter("text_opacity"))
        self.panel_opacity_opt.init_with_adapter(self.config.get_prop_adapter("panel_opacity"))
        self.log_max_lines_opt.init_with_adapter(self.config.get_prop_adapter("log_max_lines"))
        self.log_fade_seconds_opt.init_with_adapter(self.config.get_prop_adapter("log_fade_seconds"))
        self.follow_interval_opt.init_with_adapter(self.config.get_prop_adapter("follow_interval_ms"))
        self.state_interval_opt.init_with_adapter(self.config.get_prop_adapter("state_poll_interval_ms"))

        if not win32_utils.is_windows_build_supported(19041):
            self.anti_capture_opt.setDisabled(True)
            self.enabled_opt.setDisabled(True)
            self.show_info_bar(
                title=gt("Overlay 不可用"),
                content=gt("系统版本低于 Windows 10 2004，Overlay 已禁用"),
                duration=4000,
            )
        else:
            self.anti_capture_opt.setDisabled(False)
            self.enabled_opt.setDisabled(False)
        self._refresh_hotkey_content()

    def _on_config_changed(self, *_args) -> None:
        self._refresh_hotkey_content()
        manager = OverlayManager.instance()
        if manager is not None:
            manager.reload_config()

    def _on_reset_geometry_clicked(self) -> None:
        self.config.reset_panel_geometry()
        manager = OverlayManager.instance()
        if manager is not None:
            manager.reset_panel_geometry()
        self.show_info_bar(
            title=gt("已重置"),
            content=gt("Overlay 面板位置已重置"),
            duration=2500,
        )

    def _refresh_hotkey_content(self) -> None:
        key = self._format_hotkey_key(self.config.toggle_hotkey)
        self.enabled_opt.setContent(f"启用后可通过 Ctrl+Alt+{key} 切换显隐")

    @staticmethod
    def _format_hotkey_key(key: str) -> str:
        raw = str(key or "").strip()
        vk = win32_utils.key_to_vk(raw)
        if vk is not None and 65 <= vk <= 90:
            return chr(vk)
        if vk is not None and 48 <= vk <= 57:
            return chr(vk)
        return raw.upper() if raw else "O"
