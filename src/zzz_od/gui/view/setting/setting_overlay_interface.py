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
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import (
    DoubleSpinBoxSettingCard,
    SpinBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.context.zzz_context import ZContext


class SettingOverlayInterface(VerticalScrollInterface):
    """Overlay settings page."""
    _PERF_CORE_METRICS = (
        ("OCR 耗时", "ocr_ms"),
        ("YOLO 耗时", "yolo_ms"),
        ("CV Pipeline 耗时", "cv_pipeline_ms"),
        ("节点轮次耗时", "operation_round_ms"),
        ("Overlay 刷新耗时", "overlay_refresh_ms"),
    )

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
        content_widget.add_widget(self._init_visual_group())
        content_widget.add_widget(self._init_panel_group())
        content_widget.add_widget(self._init_perf_group())
        content_widget.add_widget(self._init_capture_group())
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

    def _init_visual_group(self) -> SettingCardGroup:
        group = SettingCardGroup(gt("视觉绘制"))

        self.vision_layer_opt = SwitchSettingCard(
            icon=FluentIcon.VIEW,
            title="启用视觉层",
            content="显示 YOLO/OCR/Template/CV 绘制结果",
        )
        self.vision_layer_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.vision_layer_opt)

        self.vision_yolo_opt = SwitchSettingCard(
            icon=FluentIcon.DOCUMENT,
            title="显示 YOLO",
        )
        self.vision_yolo_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.vision_yolo_opt)

        self.vision_ocr_opt = SwitchSettingCard(
            icon=FluentIcon.EDIT,
            title="显示 OCR",
        )
        self.vision_ocr_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.vision_ocr_opt)

        self.vision_template_opt = SwitchSettingCard(
            icon=FluentIcon.COPY,
            title="显示 Template",
        )
        self.vision_template_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.vision_template_opt)

        self.vision_cv_opt = SwitchSettingCard(
            icon=FluentIcon.VIDEO,
            title="显示 CV Pipeline",
        )
        self.vision_cv_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.vision_cv_opt)

        self.vision_offset_x_opt = SpinBoxSettingCard(
            icon=FluentIcon.MOVE,
            title="视觉层 X 偏移",
            content="用于校正识别框左右偏移（像素）",
            minimum=-400,
            maximum=400,
            step=1,
        )
        self.vision_offset_x_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.vision_offset_x_opt)

        self.vision_offset_y_opt = SpinBoxSettingCard(
            icon=FluentIcon.MOVE,
            title="视觉层 Y 偏移",
            content="用于校正识别框上下偏移（像素）",
            minimum=-400,
            maximum=400,
            step=1,
        )
        self.vision_offset_y_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.vision_offset_y_opt)

        self.vision_scale_x_opt = DoubleSpinBoxSettingCard(
            icon=FluentIcon.ZOOM,
            title="视觉层 X 缩放",
            minimum=0.50,
            maximum=1.50,
            step=0.01,
        )
        self.vision_scale_x_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.vision_scale_x_opt)

        self.vision_scale_y_opt = DoubleSpinBoxSettingCard(
            icon=FluentIcon.ZOOM,
            title="视觉层 Y 缩放",
            minimum=0.50,
            maximum=1.50,
            step=0.01,
        )
        self.vision_scale_y_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.vision_scale_y_opt)

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

        self.decision_panel_opt = SwitchSettingCard(
            icon=FluentIcon.DOCUMENT,
            title="显示决策链路面板",
        )
        self.decision_panel_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.decision_panel_opt)

        self.timeline_panel_opt = SwitchSettingCard(
            icon=FluentIcon.HISTORY,
            title="显示时间轴面板",
        )
        self.timeline_panel_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.timeline_panel_opt)

        self.performance_panel_opt = SwitchSettingCard(
            icon=FluentIcon.ZOOM,
            title="显示性能面板",
        )
        self.performance_panel_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.performance_panel_opt)

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

        self.panel_opacity_opt = SpinBoxSettingCard(
            icon=FluentIcon.SETTING,
            title="面板透明度(%)",
            minimum=20,
            maximum=100,
            step=1,
        )
        self.panel_opacity_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.panel_opacity_opt)

        self.reset_geometry_opt = PushSettingCard(
            icon=FluentIcon.SYNC,
            title="重置面板位置",
            text="重置",
            content="重置 Overlay 面板到默认位置与尺寸",
        )
        self.reset_geometry_opt.clicked.connect(self._on_reset_geometry_clicked)
        group.addSettingCard(self.reset_geometry_opt)

        return group

    def _init_perf_group(self) -> SettingCardGroup:
        group = SettingCardGroup(gt("性能指标"))
        self.perf_metric_cards: dict[str, SwitchSettingCard] = {}
        for title, metric_key in self._PERF_CORE_METRICS:
            card = SwitchSettingCard(
                icon=FluentIcon.ZOOM,
                title=f"显示 {title}",
            )
            card.value_changed.connect(
                lambda enabled, metric=metric_key: self._on_perf_metric_changed(metric, enabled)
            )
            group.addSettingCard(card)
            self.perf_metric_cards[metric_key] = card
        return group

    def _init_capture_group(self) -> SettingCardGroup:
        group = SettingCardGroup(gt("截图"))

        self.patched_capture_opt = SwitchSettingCard(
            icon=FluentIcon.CAMERA,
            title="保存 patched 合成图",
            content="保留原截图与剪贴板行为，额外输出一张叠加 Overlay 的图片",
        )
        self.patched_capture_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.patched_capture_opt)

        self.patched_suffix_opt = TextSettingCard(
            icon=FluentIcon.TAG,
            title="patched 文件后缀",
            content="默认 _patched",
            input_placeholder="_patched",
            input_max_width=180,
        )
        self.patched_suffix_opt.value_changed.connect(self._on_config_changed)
        group.addSettingCard(self.patched_suffix_opt)

        return group

    def on_interface_shown(self) -> None:
        super().on_interface_shown()
        self.config = OverlayConfig()

        self.enabled_opt.init_with_adapter(self.config.get_prop_adapter("enabled"))
        self.toggle_hotkey_opt.init_with_adapter(self.config.get_prop_adapter("toggle_hotkey"))
        self.visible_opt.init_with_adapter(self.config.get_prop_adapter("visible"))
        self.anti_capture_opt.init_with_adapter(self.config.get_prop_adapter("anti_capture"))
        self.vision_layer_opt.init_with_adapter(self.config.get_prop_adapter("vision_layer_enabled"))
        self.vision_yolo_opt.init_with_adapter(self.config.get_prop_adapter("vision_yolo_enabled"))
        self.vision_ocr_opt.init_with_adapter(self.config.get_prop_adapter("vision_ocr_enabled"))
        self.vision_template_opt.init_with_adapter(self.config.get_prop_adapter("vision_template_enabled"))
        self.vision_cv_opt.init_with_adapter(self.config.get_prop_adapter("vision_cv_enabled"))
        self.vision_offset_x_opt.init_with_adapter(self.config.get_prop_adapter("vision_offset_x"))
        self.vision_offset_y_opt.init_with_adapter(self.config.get_prop_adapter("vision_offset_y"))
        self.vision_scale_x_opt.init_with_adapter(self.config.get_prop_adapter("vision_scale_x"))
        self.vision_scale_y_opt.init_with_adapter(self.config.get_prop_adapter("vision_scale_y"))
        self.log_panel_opt.init_with_adapter(self.config.get_prop_adapter("log_panel_enabled"))
        self.state_panel_opt.init_with_adapter(self.config.get_prop_adapter("state_panel_enabled"))
        self.decision_panel_opt.init_with_adapter(self.config.get_prop_adapter("decision_panel_enabled"))
        self.timeline_panel_opt.init_with_adapter(self.config.get_prop_adapter("timeline_panel_enabled"))
        self.performance_panel_opt.init_with_adapter(self.config.get_prop_adapter("performance_panel_enabled"))
        self.log_max_lines_opt.init_with_adapter(self.config.get_prop_adapter("log_max_lines"))
        self.log_fade_seconds_opt.init_with_adapter(self.config.get_prop_adapter("log_fade_seconds"))
        self.follow_interval_opt.init_with_adapter(self.config.get_prop_adapter("follow_interval_ms"))
        self.state_interval_opt.init_with_adapter(self.config.get_prop_adapter("state_poll_interval_ms"))
        self.panel_opacity_opt.init_with_adapter(self.config.get_prop_adapter("panel_opacity"))
        self.patched_capture_opt.init_with_adapter(
            self.config.get_prop_adapter("patched_capture_enabled")
        )
        self.patched_suffix_opt.init_with_adapter(
            self.config.get_prop_adapter("patched_capture_suffix")
        )
        self._sync_perf_metric_cards()

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

    def _on_perf_metric_changed(self, metric: str, enabled: bool) -> None:
        self.config.set_performance_metric_enabled(metric, enabled)
        self._on_config_changed()

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

    def _sync_perf_metric_cards(self) -> None:
        for _, metric_key in self._PERF_CORE_METRICS:
            card = self.perf_metric_cards.get(metric_key)
            if card is None:
                continue
            card.setValue(
                self.config.is_performance_metric_enabled(metric_key, default=True),
                emit_signal=False,
            )

    @staticmethod
    def _format_hotkey_key(key: str) -> str:
        raw = str(key or "").strip()
        vk = win32_utils.key_to_vk(raw)
        if vk is not None and 65 <= vk <= 90:
            return chr(vk)
        if vk is not None and 48 <= vk <= 57:
            return chr(vk)
        return raw.upper() if raw else "O"
