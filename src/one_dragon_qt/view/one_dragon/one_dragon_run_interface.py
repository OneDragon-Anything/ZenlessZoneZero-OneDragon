from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QEvent, QPoint, QTimer, QPropertyAnimation
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget, QLabel, QFrame, QGraphicsOpacityEffect, QGraphicsDropShadowEffect
from PySide6.QtGui import QPixmap, QCursor
from qfluentwidgets import (
    FluentIcon,
    PrimaryPushButton,
    PushButton,
    SettingCardGroup,
    SingleDirectionScrollArea,
    SubtitleLabel,
)

from one_dragon.base.config.one_dragon_config import AfterDoneOpEnum, InstanceRun
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfig,
    ApplicationGroupConfigItem,
)
from one_dragon.base.operation.application_base import ApplicationEventId
from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.base.operation.one_dragon_context import (
    ContextInstanceEventEnum,
    ContextKeyboardEventEnum,
    OneDragonContext,
)
from one_dragon.utils import cmd_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.view.app_run_interface import AppRunner
from one_dragon_qt.view.context_event_signal import ContextEventSignal
from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon_qt.widgets.notify_dialog import NotifyDialog
from one_dragon_qt.widgets.setting_card.app_run_card import AppRunCard
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class OneDragonRunInterface(VerticalScrollInterface):

    run_all_apps_signal = Signal()

    def __init__(self, ctx: OneDragonContext,
                 nav_text_cn: str = '一条龙运行',
                 object_name: str = 'one_dragon_run_interface',
                 need_multiple_instance: bool = True,
                 need_after_done_opt: bool = True,
                 help_url: Optional[str] = None, parent=None):
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name=object_name,
            parent=parent,
            nav_text_cn=nav_text_cn
        )

        self.ctx: OneDragonContext = ctx

        self.config: Optional[ApplicationGroupConfig] = None
        self._app_run_cards: List[AppRunCard] = []
        self._context_event_signal = ContextEventSignal()
        self.help_url: str = help_url  # 使用说明的链接
        self.need_multiple_instance: bool = need_multiple_instance  # 是否需要多实例
        self.need_after_done_opt: bool = need_after_done_opt  # 结束后

        # 拖拽相关属性
        self._dragging_app_id: Optional[str] = None
        self._drag_insert_line: Optional[QWidget] = None
        self._scroll_area: Optional[SingleDirectionScrollArea] = None
        # 容器级拖拽（兜底）
        self._drag_filter_installed: bool = False
        self._container_drag_watchers: list[QWidget] = []
        self._container_drag_active: bool = False
        self._container_drag_started: bool = False
        self._container_drag_threshold: int = 10
        self._container_drag_start_pos: QPoint = QPoint()
        # 拖拽浮动预览与插入线
        self._drag_float_container: Optional[QFrame] = None
        self._drag_float_label: Optional[QLabel] = None
        self._last_drop_index: Optional[int] = None
        self._drag_placeholder: Optional[QWidget] = None
        # 自动滚动
        self._auto_scroll_timer: QTimer = QTimer(self)
        self._auto_scroll_timer.setInterval(16)
        self._auto_scroll_timer.timeout.connect(self._on_auto_scroll_tick)
        self._auto_scroll_dir: int = 0
        self._auto_scroll_step: int = 0
        # 全局键盘过滤（ESC 取消）
        self._global_key_filter_installed: bool = False
        # 拖拽开始时的原始索引
        self._drag_original_index: Optional[int] = None
        # 回弹效果参数
        self._bounce_frames: int = 0
        self._bounce_amplitude: float = 0.0
        self._bounce_dir: int = 0

    def get_content_widget(self) -> QWidget:
        """
        子界面内的内容组件 由子类实现
        :return:
        """
        content_widget = QWidget()
        # 创建 QVBoxLayout 作为主布局
        main_layout = QVBoxLayout(content_widget)

        # 创建 QHBoxLayout 作为中间布局
        horizontal_layout = QHBoxLayout()

        # 将 QVBoxLayouts 加入 QHBoxLayout
        horizontal_layout.addLayout(self._get_left_layout(), stretch=1)
        horizontal_layout.addLayout(self._get_right_layout(), stretch=1)

        # 设置 QHBoxLayout 的间距和边框
        horizontal_layout.setSpacing(10)
        horizontal_layout.setContentsMargins(0, 0, 0, 0)

        # 设置伸缩因子，让 QHBoxLayout 占据空间
        main_layout.addLayout(horizontal_layout, stretch=1)

        self.app_runner = AppRunner(self.ctx)
        self.app_runner.state_changed.connect(self.on_context_state_changed)

        return content_widget

    def _get_left_layout(self) -> QVBoxLayout:
        """
        左边的布局
        :return:
        """
        layout = QVBoxLayout()

        scroll_area = SingleDirectionScrollArea()
        self._scroll_area = scroll_area
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 16, 0)

        self.app_card_group = SettingCardGroup(gt('任务列表'))
        scroll_layout.addWidget(self.app_card_group)
        scroll_layout.addStretch(1)

        scroll_area.setWidget(scroll_content)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)

        # 安装容器级事件过滤器（兜底）
        self._install_container_drag_filters()

        return layout

    def _get_right_layout(self) -> QVBoxLayout:
        """
        右边的布局
        :return:
        """
        layout = QVBoxLayout()
        layout.setSpacing(5)

        run_group = SettingCardGroup(gt('运行设置'))
        layout.addWidget(run_group)

        if self.help_url is not None:
            self.help_opt = HelpCard(url=self.help_url)
            run_group.addSettingCard(self.help_opt)

        self.notify_switch = SwitchSettingCard(icon=FluentIcon.INFO, title='单应用通知')
        self.notify_btn = PushButton(text=gt('设置'), icon=FluentIcon.SETTING)
        self.notify_btn.clicked.connect(self._on_notify_setting_clicked)
        self.notify_switch.hBoxLayout.addWidget(self.notify_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.notify_switch.hBoxLayout.addSpacing(16)
        run_group.addSettingCard(self.notify_switch)

        self.instance_run_opt = ComboBoxSettingCard(icon=FluentIcon.PEOPLE, title='运行实例',
                                                    options_enum=InstanceRun)
        self.instance_run_opt.value_changed.connect(self._on_instance_run_changed)
        run_group.addSettingCard(self.instance_run_opt)

        self.after_done_opt = ComboBoxSettingCard(icon=FluentIcon.CALENDAR, title='结束后',
                                                  options_enum=AfterDoneOpEnum)
        self.after_done_opt.value_changed.connect(self._on_after_done_changed)
        run_group.addSettingCard(self.after_done_opt)

        self.state_text = SubtitleLabel()
        self.state_text.setText('%s %s' % (gt('当前状态'), self.ctx.run_context.run_status_text))
        self.state_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.state_text)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(5)
        layout.addLayout(btn_row)

        self.start_btn = PrimaryPushButton(
            text='%s %s' % (gt('开始'), self.ctx.key_start_running.upper()),
            icon=FluentIcon.PLAY,
        )
        self.start_btn.clicked.connect(self._on_start_clicked)
        btn_row.addWidget(self.start_btn, stretch=1)

        self.stop_btn = PushButton(
            text='%s %s' % (gt('停止'), self.ctx.key_stop_running.upper()),
            icon=FluentIcon.CLOSE
        )
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        btn_row.addWidget(self.stop_btn, stretch=1)

        self.log_card = LogDisplayCard()
        layout.addWidget(self.log_card, stretch=1)

        return layout

    def _init_app_list(self) -> None:
        """
        初始化应用列表
        :return:
        """
        if len(self._app_run_cards) > 0:  # 之前已经添加了组件了 这次只是调整顺序
            for idx, app in enumerate(self.config.app_list):
                run_record = self.ctx.run_context.get_run_record(
                    app_id=app.app_id,
                    instance_idx=self.ctx.current_instance_idx
                )
                self._app_run_cards[idx].set_app(app, run_record)
                self._app_run_cards[idx].set_switch_on(app.enabled)
        else:
            for app in self.config.app_list:
                run_record = self.ctx.run_context.get_run_record(
                    app_id=app.app_id,
                    instance_idx=self.ctx.current_instance_idx
                )
                app_run_card = AppRunCard(
                    app,
                    run_record=run_record,
                    switch_on=app.enabled,
                )
                self._app_run_cards.append(app_run_card)
                self.app_card_group.addSettingCard(app_run_card)
                app_run_card.update_display()

                # app_run_card.move_up.connect(self.on_app_card_move_up)
                # app_run_card.move_down.connect(self.on_app_card_move_down)
                app_run_card.run.connect(self._on_app_card_run)
                app_run_card.switched.connect(self.on_app_switch_run)

                # 连接拖拽相关信号
                app_run_card.drag_started.connect(self._on_app_drag_started)
                app_run_card.drag_moved.connect(self._on_app_drag_moved)
                app_run_card.drag_finished.connect(self._on_app_drag_finished)

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.config = self.ctx.app_group_manager.get_one_dragon_group_config(
            instance_idx=self.ctx.current_instance_idx,
        )
        self._init_app_list()
        # 确保拖拽过滤器就绪
        self._install_container_drag_filters()
        self.notify_switch.init_with_adapter(self.ctx.notify_config.get_prop_adapter('enable_notify'))

        self.ctx.listen_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)
        self.ctx.listen_event(ApplicationEventId.APPLICATION_START.value, self._on_app_state_changed)
        self.ctx.listen_event(ApplicationEventId.APPLICATION_STOP.value, self._on_app_state_changed)
        self.ctx.listen_event(ContextInstanceEventEnum.instance_active.value, self._on_instance_event)

        self.instance_run_opt.blockSignals(True)
        self.instance_run_opt.setValue(self.ctx.one_dragon_config.instance_run)
        self.instance_run_opt.setVisible(self.need_multiple_instance)
        self.instance_run_opt.blockSignals(False)

        self.after_done_opt.setValue(self.ctx.one_dragon_config.after_done)
        self.after_done_opt.setVisible(self.need_after_done_opt)

        self._context_event_signal.instance_changed.connect(self._on_instance_changed)
        self.run_all_apps_signal.connect(self.run_all_apps)

        if self.ctx.signal.start_onedragon:
            self.ctx.signal.start_onedragon = False
            self.run_all_apps_signal.emit()

    def on_interface_hidden(self) -> None:
        VerticalScrollInterface.on_interface_hidden(self)
        self.ctx.unlisten_all_event(self)
        self._context_event_signal.instance_changed.disconnect(self._on_instance_changed)

    def _on_after_done_changed(self, idx: int, value: str) -> None:
        """
        结束后的操作
        :param value:
        :return:
        """
        self.ctx.one_dragon_config.after_done = value
        if value != AfterDoneOpEnum.SHUTDOWN.value.value:
            log.info('已取消关机计划')
            cmd_utils.cancel_shutdown_sys()

    def run_app(self, app: ApplicationGroupConfigItem) -> None:
        if self.app_runner.isRunning():
            log.error('已有应用在运行中')
            return
        self.app_runner.app_id = app.app_id
        self.app_runner.start()

    def run_all_apps(self) -> None:
        if self.app_runner.isRunning():
            log.error('已有应用在运行中')
            return
        self.app_runner.app_id = application_const.ONE_DRAGON_APP_ID
        self.app_runner.start()

    def _on_start_clicked(self) -> None:
        self.run_all_apps()

    def _on_stop_clicked(self) -> None:
        self.ctx.run_context.stop_running()

    def _on_key_press(self, event: ContextEventItem) -> None:
        """
        按键监听
        """
        key: str = event.data
        if key == self.ctx.key_start_running and self.ctx.run_context.is_context_stop:
            self.run_all_apps()

    def on_context_state_changed(self) -> None:
        """
        按运行状态更新显示
        :return:
        """
        if self.ctx.run_context.is_context_running:
            text = gt('暂停')
            icon = FluentIcon.PAUSE
            self.log_card.start()  # 开始日志更新
        elif self.ctx.run_context.is_context_pause:
            text = gt('继续')
            icon = FluentIcon.PLAY
            self.log_card.pause()  # 暂停日志更新
        else:
            text = gt('开始')
            icon = FluentIcon.PLAY
            self.log_card.stop()  # 停止日志更新

        self.start_btn.setText('%s %s' % (text, self.ctx.key_start_running.upper()))
        self.start_btn.setIcon(icon)
        self.state_text.setText('%s %s' % (gt('当前状态'), self.ctx.run_context.run_status_text))

        for app_card in self._app_run_cards:
            app_card.update_display()

        if self.ctx.run_context.is_context_stop and self.need_after_done_opt:
            if self.ctx.one_dragon_config.after_done == AfterDoneOpEnum.SHUTDOWN.value.value:
                cmd_utils.shutdown_sys(60)
            elif self.ctx.one_dragon_config.after_done == AfterDoneOpEnum.CLOSE_GAME.value.value:
                self.ctx.controller.close_game()

    def _on_app_state_changed(self, event) -> None:
        for app_card in self._app_run_cards:
            app_card.update_display()

    def _on_app_card_run(self, app_id: str) -> None:
        """
        运行某个特殊的应用
        :param app_id:
        :return:
        """
        for app in self.config.app_list:
            if app.app_id == app_id:
                self.run_app(app)

    def on_app_switch_run(self, app_id: str, value: bool) -> None:
        """
        应用运行状态切换
        :param app_id:
        :param value:
        :return:
        """
        self.config.set_app_enable(app_id, value)

    def _on_instance_event(self, event) -> None:
        """
        实例变更 这是context的事件 不能改UI
        :return:
        """
        self._context_event_signal.instance_changed.emit()

    def _on_instance_changed(self) -> None:
        """
        实例变更 这是signal 可以改ui
        :return:
        """
        self._init_app_list()

    def _on_instance_run_changed(self, idx: int, value: str) -> None:
        self.ctx.one_dragon_config.instance_run = value

    def _init_notify_switch(self) -> None:
        pass

    def _on_notify_setting_clicked(self) -> None:
        self.show_notify_dialog()

    def show_notify_dialog(self) -> None:
        """
        显示通知设置对话框。配置更新由对话框内部处理。
        """
        dialog = NotifyDialog(self, self.ctx)
        dialog.exec()

    def _on_app_drag_started(self, app_id: str) -> None:
        """
        开始拖拽应用卡片
        :param app_id: 应用ID
        :return:
        """
        self._dragging_app_id = app_id
        # 记录原始 index
        try:
            self._drag_original_index = next((i for i, c in enumerate(self._app_run_cards) if c.app.app_id == app_id), None)
        except Exception:
            self._drag_original_index = None
        # 构建浮动预览（容器+子控件：容器阴影，子控件透明度）
        card_widget = next((c for c in self._app_run_cards if c.app.app_id == app_id), None)
        if card_widget is not None and len(self._app_run_cards) > 0:
            pm: QPixmap = card_widget.grab()
            w = max(1, int(pm.width() * 0.7))
            h = max(1, int(pm.height() * 0.7))
            pm = pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            parent_widget = self._app_run_cards[0].parentWidget()
            if parent_widget is not None:
                if self._drag_float_container is None:
                    self._drag_float_container = QFrame(parent_widget)
                    self._drag_float_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    self._drag_float_container.setStyleSheet("QFrame { border: 1px solid rgba(0,120,212,0.35); border-radius: 6px; background: transparent; }")
                    # 阴影作用于容器
                    shadow = QGraphicsDropShadowEffect(self._drag_float_container)
                    shadow.setBlurRadius(18)
                    shadow.setOffset(0, 6)
                    shadow.setColor(Qt.black)
                    self._drag_float_container.setGraphicsEffect(shadow)
                    # 子标签承载图像并设置透明度
                    self._drag_float_label = QLabel(self._drag_float_container)
                    self._drag_float_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    opacity = QGraphicsOpacityEffect(self._drag_float_label)
                    opacity.setOpacity(0.75)
                    self._drag_float_label.setGraphicsEffect(opacity)
                self._drag_float_label.setPixmap(pm)
                self._drag_float_label.resize(pm.size())
                self._drag_float_container.resize(self._drag_float_label.size())
                self._drag_float_container.show()
                self._drag_float_container.raise_()
        # 启动自动滚动
        self._auto_scroll_dir = 0
        self._auto_scroll_timer.start()
        # 安装全局键盘过滤器
        if not self._global_key_filter_installed:
            QApplication.instance().installEventFilter(self)
            self._global_key_filter_installed = True

    def _on_app_drag_moved(self, app_id: str, x: int, y: int) -> None:
        """
        拖拽应用卡片移动过程中
        :param app_id: 应用ID
        :param x: 鼠标X坐标
        :param y: 鼠标Y坐标
        :return:
        """
        if self._dragging_app_id != app_id:
            return

        # 更新浮动预览位置（使其跟随光标，居中）
        if self._drag_float_container is not None and self._drag_float_container.isVisible():
            self._drag_float_container.move(int(x - self._drag_float_container.width() / 2),
                                            int(y - self._drag_float_container.height() / 2))
        # 显示插入位置指示器
        self._show_drop_indicator(y)
        # 边缘自动滚动
        self._update_auto_scroll(y)

    def _on_app_drag_finished(self, app_id: str, x: int, y: int) -> None:
        """
        拖拽应用卡片结束
        :param app_id: 应用ID
        :param x: 鼠标X坐标
        :param y: 鼠标Y坐标
        :return:
        """
        if self._dragging_app_id != app_id:
            return

        # 计算目标位置
        target_position = self._calculate_drop_position(y)
        log.debug(f"[Drag] compute target pos: y={y} -> target={target_position}")

        # 移动应用到目标位置
        if target_position is not None:
            log.debug(f"拖拽结束: {app_id} -> 位置 {target_position}")
            self.get_one_dragon_app_config().move_app_to_position(app_id, target_position)
            # 不受运行状态限制地刷新卡片显示顺序
            self._refresh_app_cards_order_display()

        # 清理拖拽状态
        self._dragging_app_id = None
        self._hide_drop_indicator()
        if self._drag_float_container is not None:
            self._drag_float_container.hide()
        self._auto_scroll_timer.stop()
        self._auto_scroll_dir = 0
        self._drag_original_index = None
        self._bounce_frames = 0
        # 卸载全局键盘过滤器
        if self._global_key_filter_installed:
            try:
                QApplication.instance().removeEventFilter(self)
            except Exception:
                pass
            self._global_key_filter_installed = False

    def _show_drop_indicator(self, y: int) -> None:
        """
        显示拖拽插入位置指示器
        :param y: Y坐标
        :return:
        """
        parent_widget = self._app_run_cards[0].parentWidget() if self._app_run_cards else None
        if parent_widget is None:
            return
        idx = self._calculate_drop_position(y)
        if idx is None:
            return
        if self._drag_insert_line is None:
            self._drag_insert_line = QFrame(parent_widget)
            self._drag_insert_line.setFrameShape(QFrame.Shape.HLine)
            self._drag_insert_line.setStyleSheet("QFrame { color: #0078d4; background-color: #0078d4; }")
            self._drag_insert_line.setFixedHeight(2)
        # 计算应放置的 Y 坐标：位于 idx 与前一项之间的缝隙
        if idx <= 0:
            line_y = self._app_run_cards[0].geometry().y() - 1
        else:
            prev_rect = self._app_run_cards[idx - 1].geometry()
            line_y = prev_rect.y() + prev_rect.height() + 1
        self._drag_insert_line.setGeometry(0, line_y, parent_widget.width(), 2)
        self._drag_insert_line.show()
        self._last_drop_index = idx
        # 占位虚框
        if self._drag_placeholder is None:
            self._drag_placeholder = QWidget(parent_widget)
            self._drag_placeholder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._drag_placeholder.setStyleSheet(
                "QWidget { border: 2px dashed #0078d4; background-color: rgba(0,120,212,0.06); border-radius: 6px; }"
            )
        # 以目标卡片高度作为占位高度
        target_rect = self._app_run_cards[idx].geometry() if 0 <= idx < len(self._app_run_cards) else self._app_run_cards[-1].geometry()
        card_h = target_rect.height()
        ph = max(24, card_h)
        py = max(0, line_y - ph // 2)
        self._drag_placeholder.setGeometry(6, py, parent_widget.width() - 12, ph)
        self._drag_placeholder.show()
        self._drag_placeholder.raise_()

    def _hide_drop_indicator(self) -> None:
        """
        隐藏拖拽插入位置指示器
        :return:
        """
        if self._drag_insert_line is not None:
            self._drag_insert_line.hide()
        if self._drag_placeholder is not None:
            self._drag_placeholder.hide()
        self._last_drop_index = None

    def _maybe_auto_scroll(self, y: int) -> None:
        """当拖拽点接近滚动区域边缘时，自动轻微滚动"""
        if not self._scroll_area:
            return
        # 基于 app_card_group 的父坐标判断接近顶部/底部
        top = self.app_card_group.y()
        bottom = top + self.app_card_group.height()
        margin = 30
        step = 15
        bar = self._scroll_area.verticalScrollBar()
        if y < top + margin:
            bar.setValue(bar.value() - step)
        elif y > bottom - margin:
            bar.setValue(bar.value() + step)

    def _update_auto_scroll(self, y: int) -> None:
        if not self._scroll_area:
            return
        top = self.app_card_group.y()
        bottom = top + self.app_card_group.height()
        margin = 64
        base = 8
        max_step = 28
        if y < top + margin:
            self._auto_scroll_dir = -1
            dist = max(1, (y - top))
            factor = max(0.0, min(1.0, 1.0 - dist / margin))
            self._auto_scroll_step = int(base + (max_step - base) * factor)
        elif y > bottom - margin:
            self._auto_scroll_dir = 1
            dist = max(1, (bottom - y))
            factor = max(0.0, min(1.0, 1.0 - dist / margin))
            self._auto_scroll_step = int(base + (max_step - base) * factor)
        else:
            self._auto_scroll_dir = 0
            self._auto_scroll_step = 0

    def _on_auto_scroll_tick(self) -> None:
        if not self._scroll_area or self._auto_scroll_dir == 0 or self._auto_scroll_step <= 0:
            return
        bar = self._scroll_area.verticalScrollBar()
        bar.setValue(bar.value() + self._auto_scroll_dir * self._auto_scroll_step)
        # 让浮动预览跟随鼠标（避免滚动时错位）
        if self._drag_float_container is not None and self._drag_float_container.isVisible() and len(self._app_run_cards) > 0:
            global_pos = QCursor.pos()
            parent_widget = self._app_run_cards[0].parentWidget()
            if parent_widget is not None:
                parent_pos = parent_widget.mapFromGlobal(global_pos)
                self._drag_float_container.move(int(parent_pos.x() - self._drag_float_container.width() / 2),
                                                int(parent_pos.y() - self._drag_float_container.height() / 2))

    def _calculate_drop_position(self, y: int) -> Optional[int]:
        """
        根据Y坐标计算拖拽的目标位置
        :param y: Y坐标
        :return: 目标位置索引，如果无效返回None
        """
        if not self._app_run_cards:
            return None

        # y 是父容器坐标系下的位置，这里以每张卡片真实位置来判定目标下标
        # 规则：落入某卡片上半区，则插入到该卡片之前；落入下半区，插入到该卡片之后
        parent_widget = self._app_run_cards[0].parentWidget()
        for idx, card in enumerate(self._app_run_cards):
            # 使用几何矩形（相对父级坐标系）判定
            rect = card.geometry()
            mid = rect.y() + rect.height() // 2
            if y < mid:
                return idx
        # 若超过最后一张卡片的下半区，则插到末尾
        return len(self._app_run_cards) - 1

    def _refresh_app_cards_order_display(self) -> None:
        """根据配置中的顺序刷新卡片的显示（不变更控件实例顺序，仅更新内容）"""
        self.app_list = self.get_one_dragon_app().get_one_dragon_apps_in_order()
        app_run_list = self.get_app_run_list()
        for idx, app in enumerate(self.app_list):
            if idx < len(self._app_run_cards):
                self._app_run_cards[idx].set_app(app)
                self._app_run_cards[idx].set_switch_on(app.app_id in app_run_list)

    def _install_container_drag_filters(self) -> None:
        if self._drag_filter_installed:
            return
        watchers: list[QWidget] = []
        if hasattr(self, 'app_card_group') and self.app_card_group is not None:
            watchers.append(self.app_card_group)
            if self.app_card_group.parentWidget() is not None:
                watchers.append(self.app_card_group.parentWidget())
        if self._scroll_area is not None and self._scroll_area.viewport() is not None:
            watchers.append(self._scroll_area.viewport())
        for w in watchers:
            try:
                w.installEventFilter(self)
            except Exception:
                pass
        self._container_drag_watchers = watchers
        self._drag_filter_installed = len(watchers) > 0
        log.debug(f"[Drag][container] install filters on {len(watchers)} widgets")

    def eventFilter(self, obj, event):
        # 容器级拖拽兜底：当卡片内部未能捕获事件时，从容器监听；捕获全局按键（ESC/中键）
        # 全局按键：ESC 取消本次拖拽
        if event.type() == QEvent.Type.KeyPress and self._dragging_app_id is not None:
            if getattr(event, 'key', lambda: None)() == Qt.Key_Escape:
                self._cancel_current_drag()
                return True
        if isinstance(obj, QWidget) and obj in getattr(self, '_container_drag_watchers', []):
            et = event.type()
            if et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                global_pos = obj.mapToGlobal(event.pos())
                if hasattr(self, 'app_card_group') and self.app_card_group is not None:
                    local_pos = self.app_card_group.mapFromGlobal(global_pos)
                    hit_idx = -1
                    for idx, card in enumerate(self._app_run_cards):
                        if card.geometry().contains(local_pos):
                            hit_idx = idx
                            break
                    if hit_idx != -1:
                        self._container_drag_active = True
                        self._container_drag_started = False
                        self._container_drag_start_pos = local_pos
                        self._dragging_app_id = self._app_run_cards[hit_idx].app.app_id
                        return False
            elif et == QEvent.Type.MouseMove and self._container_drag_active:
                global_pos = obj.mapToGlobal(event.pos())
                if hasattr(self, 'app_card_group') and self.app_card_group is not None:
                    local_pos = self.app_card_group.mapFromGlobal(global_pos)
                    if not self._container_drag_started:
                        if (local_pos - self._container_drag_start_pos).manhattanLength() > self._container_drag_threshold:
                            self._container_drag_started = True
                            if self._dragging_app_id:
                                self._on_app_drag_started(self._dragging_app_id)
                    if self._container_drag_started and self._dragging_app_id:
                        parent_widget = self._app_run_cards[0].parentWidget()
                        parent_pos = parent_widget.mapFromGlobal(global_pos)
                        self._on_app_drag_moved(self._dragging_app_id, parent_pos.x(), parent_pos.y())
                        return True
            elif et == QEvent.Type.MouseButtonRelease and self._container_drag_active:
                global_pos = obj.mapToGlobal(event.pos())
                if event.button() == Qt.MouseButton.MiddleButton and self._dragging_app_id is not None:
                    self._cancel_current_drag()
                    self._container_drag_active = False
                    self._container_drag_started = False
                    return True
                if self._container_drag_started and self._dragging_app_id:
                    parent_widget = self._app_run_cards[0].parentWidget()
                    parent_pos = parent_widget.mapFromGlobal(global_pos)
                    self._on_app_drag_finished(self._dragging_app_id, parent_pos.x(), parent_pos.y())
                    self._dragging_app_id = None
                self._container_drag_active = False
                self._container_drag_started = False
                return True
        return super().eventFilter(obj, event)

    def _cancel_current_drag(self) -> None:
        # 取消当前拖拽并清理视觉效果
        self._hide_drop_indicator()
        if self._drag_float_label is not None:
            self._drag_float_label.hide()
        self._auto_scroll_timer.stop()
        self._auto_scroll_dir = 0
        self._bounce_frames = 0
        self._dragging_app_id = None
        # 卸载全局键盘过滤器
        if self._global_key_filter_installed:
            try:
                QApplication.instance().removeEventFilter(self)
            except Exception:
                pass
            self._global_key_filter_installed = False
