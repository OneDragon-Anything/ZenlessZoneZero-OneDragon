from typing import Optional

from PySide6.QtCore import Signal, QPoint, Qt
from PySide6.QtGui import QMouseEvent, QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    FluentIcon,
    FluentThemeColor,
    SwitchButton,
    TransparentToolButton,
)

from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfigItem,
)
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)


class AppRunCard(MultiPushSettingCard):

    # move_up = Signal(str)
    # move_down = Signal(str)
    run = Signal(str)
    switched = Signal(str, bool)
    drag_started = Signal(str)
    drag_moved = Signal(str, int, int)
    drag_finished = Signal(str, int, int)

    def __init__(
        self,
        app: ApplicationGroupConfigItem,
        run_record: Optional[AppRunRecord] = None,
        switch_on: bool = False,
        parent: Optional[QWidget] = None
    ):
        self.app: ApplicationGroupConfigItem = app
        self.run_record: Optional[AppRunRecord] = run_record

        # 拖拽相关属性
        self._is_dragging: bool = False
        self._drag_start_pos: QPoint = QPoint()
        self._drag_threshold: int = 10
        self._original_style: str = ""  # 保存原始样式

        # 添加拖拽按钮（汉堡按钮）
        self.drag_btn = TransparentToolButton(FluentIcon.MENU, None)
        self.drag_btn.setToolTip('按住拖拽以调整顺序')
        # 设置鼠标悬停时的光标样式为抓手
        self.drag_btn.setCursor(Qt.CursorShape.OpenHandCursor)

        # self.move_up_btn = TransparentToolButton(FluentIcon.UP, None)
        # self.move_up_btn.clicked.connect(self._on_move_up_clicked)
        # self.move_up_btn.setToolTip('向上移动一位')
        #
        # self.move_down_btn = TransparentToolButton(FluentIcon.DOWN, None)
        # self.move_down_btn.clicked.connect(self._on_move_down_clicked)
        # self.move_down_btn.setToolTip('向下移动一位')

        self.run_btn = TransparentToolButton(FluentIcon.PLAY, None)
        self.run_btn.clicked.connect(self._on_run_clicked)

        self.switch_btn = SwitchButton()
        self.switch_btn.setOnText('')
        self.switch_btn.setOffText('')
        self.switch_btn.setChecked(switch_on)
        self.switch_btn.checkedChanged.connect(self._on_switch_changed)

        MultiPushSettingCard.__init__(
            self,
            btn_list=[self.drag_btn, self.run_btn, self.switch_btn],
            icon=FluentIcon.GAME,
            title=self.app.app_name,
            parent=parent,
        )

        # 保存初始样式
        self._original_style = self.styleSheet()
        
        # 为拖拽按钮安装事件过滤器
        self.drag_btn.installEventFilter(self)

    def _set_dragging_style(self, is_dragging: bool) -> None:
        """设置拖拽状态的样式"""
        if is_dragging:
            # 添加拖拽样式，保留原有样式
            drag_style = """
                QFrame {
                    background-color: rgba(0, 120, 212, 0.1);
                    border: 2px dashed #0078d4;
                    border-radius: 6px;
                }
            """
            self.setStyleSheet(self._original_style + drag_style)
        else:
            # 恢复原有样式
            self.setStyleSheet(self._original_style)
            # 强制刷新显示
            self.update_display()

    def eventFilter(self, obj, event):
        """处理拖拽按钮的鼠标事件"""
        if obj == self.drag_btn:
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_start_pos = event.pos()
                    return True
            elif event.type() == event.Type.MouseMove:
                if (event.buttons() & Qt.MouseButton.LeftButton and 
                    not self._is_dragging):
                    # 检查是否超过拖拽阈值
                    if ((event.pos() - self._drag_start_pos).manhattanLength() > 
                        self._drag_threshold):
                        self._is_dragging = True
                        self.drag_btn.setCursor(Qt.CursorShape.ClosedHandCursor)
                        self.drag_started.emit(self.app.app_id)
                        # 设置拖拽样式
                        self._set_dragging_style(True)
                
                if self._is_dragging:
                    # 转换为全局坐标
                    global_pos = self.drag_btn.mapToGlobal(event.pos())
                    parent_pos = self.parent().mapFromGlobal(global_pos)
                    self.drag_moved.emit(self.app.app_id, parent_pos.x(), parent_pos.y())
                    return True
            elif event.type() == event.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
                    # 转换为全局坐标
                    global_pos = self.drag_btn.mapToGlobal(event.pos())
                    parent_pos = self.parent().mapFromGlobal(global_pos)
                    self.drag_finished.emit(self.app.app_id, parent_pos.x(), parent_pos.y())
                    self._is_dragging = False
                    self.drag_btn.setCursor(Qt.CursorShape.OpenHandCursor)
                    # 恢复原有样式
                    self._set_dragging_style(False)
                    return True
        
        return super().eventFilter(obj, event)

    def update_display(self) -> None:
        """
        更新显示的状态
        :return:
        """
        self.setTitle(self.app.app_name)
        if self.run_record is None:
            self.setContent('')
        else:
            self.setContent(
                '%s %s' % (
                    gt('上次运行'),
                    self.run_record.run_time
                )
            )

            status = self.run_record.run_status_under_now
            if status == AppRunRecord.STATUS_SUCCESS:
                icon = FluentIcon.COMPLETED.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
            elif status == AppRunRecord.STATUS_RUNNING:
                icon = FluentIcon.COMPLETED.STOP_WATCH
            elif status == AppRunRecord.STATUS_FAIL:
                icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
            else:
                icon = FluentIcon.INFO
            self.iconLabel.setIcon(icon)

    # def _on_move_up_clicked(self) -> None:
    #     """
    #     向上移动运行顺序
    #     :return:
    #     """
    #     self.move_up.emit(self.app.app_id)
    #
    # def _on_move_down_clicked(self) -> None:
    #     """
    #     向下移动运行顺序
    #     :return:
    #     """
    #     self.move_down.emit(self.app.app_id)

    def _on_run_clicked(self) -> None:
        """
        运行应用
        :return:
        """
        self.run.emit(self.app.app_id)

    def _on_switch_changed(self, value: bool) -> None:
        """
        切换开关状态
        :return:
        """
        self.switched.emit(self.app.app_id, value)

    def set_app(
        self,
        app: ApplicationGroupConfigItem,
        run_record: Optional[AppRunRecord] = None,
    ):
        """
        更新对应的app
        :param app:
        :return:
        """
        self.app = app
        self.run_record = run_record
        self.update_display()

    def setDisabled(self, arg__1: bool) -> None:
        MultiPushSettingCard.setDisabled(self, arg__1)
        self.drag_btn.setDisabled(arg__1)
        # self.move_up_btn.setDisabled(arg__1)
        # self.move_down_btn.setDisabled(arg__1)
        self.run_btn.setDisabled(arg__1)
        self.switch_btn.setDisabled(arg__1)

    def set_switch_on(self, on: bool) -> None:
        self.switch_btn.setChecked(on)

    def is_dragging(self) -> bool:
        """返回当前是否正在拖拽"""
        return self._is_dragging
