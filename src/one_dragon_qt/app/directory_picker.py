import locale
import os

from PySide6.QtCore import QEventLoop, QSize, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    IndeterminateProgressBar,
    LineEdit,
    MessageBox,
    PixmapLabel,
    PrimaryPushButton,
    ProgressBar,
    SplitTitleBar,
    SubtitleLabel,
    ToolButton,
)

from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.services.unpack_runner import UnpackResourceRunner
from one_dragon_qt.utils.image_utils import scale_pixmap_for_high_dpi
from one_dragon_qt.windows.window import PhosWindow


class DirectoryPickerTranslator:
    """简单的翻译器类"""

    def __init__(self, language='zh'):
        self.language = language
        self.translations = {
            'zh': {
                'title': '请选择安装路径',
                'placeholder': '选择安装路径...',
                'browse': '浏览',
                'confirm': '确认',
                'select_directory': '选择目录',
                'warning': '警告',
                'root_directory_warning': '所选目录为根目录，请选择其他目录。',
                'path_character_warning': '所选目录的路径包含非法字符，请确保路径全为英文字符且不包含空格。',
                'directory_not_empty_warning': '所选目录不为空，里面的内容将被覆盖：\n{path}\n\n是否继续使用此目录？',
                'i_know': '我知道了',
                'continue_use': '继续使用',
                'select_other': '选择其他目录',
                'preparing': '正在准备安装文件...',
                'copying': '正在复制 {current}/{total}',
                'cleaning': '正在清理源目录...',
                'unpack_failed_title': '搬运失败',
                'unpack_failed_body': '安装文件搬运失败，请重新运行安装器。\n\n{detail}',
            },
            'en': {
                'title': 'Please Select Installation Path',
                'placeholder': 'Select installation path...',
                'browse': 'Browse',
                'confirm': 'Confirm',
                'select_directory': 'Select Directory',
                'warning': 'Warning',
                'root_directory_warning': 'The selected directory is a root directory, please select another directory.',
                'path_character_warning': 'The selected directory path contains invalid characters, please ensure the path contains only English characters and no spaces.',
                'directory_not_empty_warning': 'The selected directory is not empty, its contents will be overwritten:\n{path}\n\nDo you want to continue using this directory?',
                'i_know': 'I Know',
                'continue_use': 'Continue',
                'select_other': 'Select Other',
                'preparing': 'Preparing installation files...',
                'copying': 'Copying {current}/{total}',
                'cleaning': 'Cleaning source directory...',
                'unpack_failed_title': 'Migration Failed',
                'unpack_failed_body': 'Installation file migration failed. Please re-run the installer.\n\n{detail}',
            }
        }

    def get_text(self, key, **kwargs):
        """获取翻译文本"""
        text = self.translations.get(self.language, self.translations['zh']).get(key, key)
        if kwargs:
            text = text.format(**kwargs)
        return text

    @staticmethod
    def detect_language():
        """自动检测系统语言"""
        try:
            system_locale = locale.getdefaultlocale()[0]
            if system_locale and system_locale.startswith('zh'):
                return 'zh'
            else:
                return 'en'
        except Exception:
            return 'zh'


class DirectoryPickerInterface(QWidget):
    """路径选择器界面"""

    def __init__(self, parent=None, icon_path=None, installer_dir: str = ""):
        QWidget.__init__(self, parent=parent)
        self.setObjectName("directory_picker_interface")
        self.selected_path = ""
        self.icon_path = icon_path
        self.installer_dir = installer_dir

        self.translator = DirectoryPickerTranslator(DirectoryPickerTranslator.detect_language())
        self._runner: UnpackResourceRunner | None = None
        self._last_log: str = ""
        self._pending_log: str = ""

        # 节流计时器：最多每 250 ms 刷新一次文件名，避免闪烁
        self._log_timer = QTimer(self)
        self._log_timer.setSingleShot(True)
        self._log_timer.setInterval(250)
        self._log_timer.timeout.connect(self._flush_log)

        self._init_ui()

    def _init_ui(self):
        """初始化用户界面"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 10, 40, 40)
        main_layout.setSpacing(20)

        # 语言切换按钮
        self.language_btn = ToolButton(FluentIcon.LANGUAGE)
        self.language_btn.clicked.connect(self._on_language_switch)
        main_layout.addWidget(self.language_btn)

        # 图标区域
        if self.icon_path:
            icon_label = PixmapLabel()
            pixmap = QPixmap(self.icon_path)
            if not pixmap.isNull():
                target_size = QSize(96, 96)
                scaled_pixmap = scale_pixmap_for_high_dpi(
                    pixmap,
                    target_size,
                    self.devicePixelRatio()
                )
                icon_label.setPixmap(scaled_pixmap)
                icon_label.setFixedSize(target_size)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                main_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 标题
        self.title_label = SubtitleLabel(self.translator.get_text('title'))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 路径显示区域
        path_layout = QHBoxLayout()
        path_layout.setSpacing(10)

        self.path_input = LineEdit()
        self.path_input.setPlaceholderText(self.translator.get_text('placeholder'))
        self.path_input.setReadOnly(True)
        path_layout.addWidget(self.path_input)
        self.browse_btn = PrimaryPushButton(self.translator.get_text('browse'))
        self.browse_btn.setIcon(FluentIcon.FOLDER_ADD)
        self.browse_btn.clicked.connect(self._on_browse_clicked)
        path_layout.addWidget(self.browse_btn)

        # 确认按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.confirm_btn = PrimaryPushButton(self.translator.get_text('confirm'))
        self.confirm_btn.setIcon(FluentIcon.ACCEPT)
        self.confirm_btn.setMinimumSize(120, 36)
        self.confirm_btn.clicked.connect(self._on_confirm_clicked)
        self.confirm_btn.setEnabled(False)
        button_layout.addWidget(self.confirm_btn)
        button_layout.addStretch(1)

        # 选路页（page 0）：标题 + 路径输入 + 确认
        pick_page = QWidget()
        pick_layout = QVBoxLayout(pick_page)
        pick_layout.setContentsMargins(0, 0, 0, 0)
        pick_layout.setSpacing(20)
        pick_layout.addWidget(self.title_label)
        pick_layout.addLayout(path_layout)
        pick_layout.addLayout(button_layout)
        pick_layout.addStretch(1)

        # 进度页（page 1）：count → bar → status + stretch
        progress_page = QWidget()
        pg_layout = QVBoxLayout(progress_page)
        pg_layout.setContentsMargins(0, 0, 0, 0)
        pg_layout.setSpacing(0)
        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.indet_progress_bar = IndeterminateProgressBar()
        # 用内层 stack 切换两种进度条，保证布局高度稳定
        self.bar_stack = QStackedWidget()
        self.bar_stack.addWidget(self.progress_bar)       # index 0: 复制阶段（确定进度）
        self.bar_stack.addWidget(self.indet_progress_bar) # index 1: 清理阶段（不确定进度）
        self.bar_stack.setCurrentIndex(0)
        # 第一行：正在复制 xx/xx（BodyLabel，字号稍大）
        self.count_label = BodyLabel(self.translator.get_text('preparing'))
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 第二行：具体文件路径（CaptionLabel，省略过长路径）
        self.status_label = CaptionLabel('')
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setWordWrap(False)
        # 禁止 status_label 撑宽窗口；文本过长时 _on_unpack_log 会做 ElideMiddle
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status_label.setMinimumWidth(0)
        pg_layout.addWidget(self.count_label)
        pg_layout.addSpacing(12)
        pg_layout.addWidget(self.bar_stack)
        pg_layout.addSpacing(8)
        pg_layout.addWidget(self.status_label)
        pg_layout.addStretch(1)

        # 展示切换器
        self.picker_stack = QStackedWidget()
        self.picker_stack.addWidget(pick_page)
        self.picker_stack.addWidget(progress_page)
        main_layout.addWidget(self.picker_stack)

        # 添加弹性空间
        main_layout.addStretch(1)

    def _on_browse_clicked(self):
        """浏览按钮点击事件"""
        selected_dir_path = QFileDialog.getExistingDirectory(
            self,
            self.translator.get_text('select_directory'),
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if selected_dir_path:
            # 检查路径是否为根目录
            if len(selected_dir_path) <= 3:
                w = MessageBox(
                    self.translator.get_text('warning'),
                    self.translator.get_text('root_directory_warning'),
                    parent=self.window(),
                )
                w.yesButton.setText(self.translator.get_text('i_know'))
                w.cancelButton.setVisible(False)
                w.exec()
                self.selected_path = ""
                self.path_input.clear()
                self.confirm_btn.setEnabled(False)
                return self._on_browse_clicked()

            # 检查路径是否为全英文或者包含空格
            if not all(c.isascii() for c in selected_dir_path) or ' ' in selected_dir_path:
                w = MessageBox(
                    self.translator.get_text('warning'),
                    self.translator.get_text('path_character_warning'),
                    parent=self.window(),
                )
                w.yesButton.setText(self.translator.get_text('i_know'))
                w.cancelButton.setVisible(False)
                w.exec()
                self.selected_path = ""
                self.path_input.clear()
                self.confirm_btn.setEnabled(False)
                return self._on_browse_clicked()

            # 检查目录是否为空
            if os.listdir(selected_dir_path):
                w = MessageBox(
                    title=self.translator.get_text('warning'),
                    content=self.translator.get_text('directory_not_empty_warning', path=selected_dir_path),
                    parent=self.window(),
                )
                w.yesButton.setText(self.translator.get_text('continue_use'))
                w.cancelButton.setText(self.translator.get_text('select_other'))
                if w.exec():
                    self.selected_path = selected_dir_path
                    self.path_input.setText(selected_dir_path)
                    self.confirm_btn.setEnabled(True)
                else:
                    return self._on_browse_clicked()
            else:
                # 目录为空，直接使用
                self.selected_path = selected_dir_path
                self.path_input.setText(selected_dir_path)
                self.confirm_btn.setEnabled(True)

    def _on_confirm_clicked(self):
        """确认按钮点击事件"""
        if not self.selected_path:
            return

        window = self.window()
        if not isinstance(window, DirectoryPickerWindow):
            return

        # 启动解包，切换到进度页
        self.picker_stack.setCurrentIndex(1)

        self._runner = UnpackResourceRunner(self.installer_dir, self.selected_path)
        self._runner.log_message.connect(self._on_unpack_log)
        self._runner.progress_changed.connect(self._on_unpack_progress)
        self._runner.unpack_done.connect(self._on_unpack_finished)
        self._runner.start()

    def _on_unpack_log(self, message: str) -> None:
        """缓存最后一条日志；由节流计时器决定何时真正刷新 status_label。"""
        self._last_log = message
        self._pending_log = message
        if not self._log_timer.isActive():
            self._log_timer.start()

    def _flush_log(self) -> None:
        """节流计时器触发时，将最新日志写入 status_label（ElideMiddle截断）。"""
        message = self._pending_log
        avail = self.status_label.width()
        if avail > 0:
            elided = self.status_label.fontMetrics().elidedText(
                message, Qt.TextElideMode.ElideMiddle, avail
            )
        else:
            elided = message
        self.status_label.setText(elided)

    def _on_unpack_progress(self, current: int, total: int) -> None:
        """更新进度条与计数行。current=-1 表示进入清理阶段。"""
        if current == -1:
            # 清理阶段：切换到动画进度条，计数行提示清理，文件行置空
            self.bar_stack.setCurrentIndex(1)
            self.indet_progress_bar.start()
            self.count_label.setText(self.translator.get_text('cleaning'))
            self.status_label.setText("")
        else:
            self.bar_stack.setCurrentIndex(0)
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
            self.count_label.setText(self.translator.get_text('copying', current=current, total=total))

    def _on_unpack_finished(self, success: bool) -> None:
        """解包完毕：成功时设定目标目录并关窗；失败时弹错误提示。"""
        window = self.window()
        if not isinstance(window, DirectoryPickerWindow):
            return
        if success:
            window.selected_directory = self.selected_path
            window.close()
        else:
            detail = self._last_log or "-"
            w = MessageBox(
                self.translator.get_text('unpack_failed_title'),
                self.translator.get_text('unpack_failed_body', detail=detail),
                parent=window,
            )
            w.yesButton.setText(self.translator.get_text('i_know'))
            w.cancelButton.setVisible(False)
            w.exec()
            window.close()

    def _on_language_switch(self):
        """语言切换按钮点击事件"""
        current_lang = self.translator.language
        new_lang = 'en' if current_lang == 'zh' else 'zh'
        self.translator = DirectoryPickerTranslator(new_lang)
        self._update_ui_texts()

    def _update_ui_texts(self):
        """更新所有UI文本"""
        self.title_label.setText(self.translator.get_text('title'))
        self.path_input.setPlaceholderText(self.translator.get_text('placeholder'))
        self.browse_btn.setText(self.translator.get_text('browse'))
        self.confirm_btn.setText(self.translator.get_text('confirm'))


class DirectoryPickerWindow(PhosWindow):

    def __init__(self,
                 parent=None,
                 icon_path=None,
                 installer_dir: str = ""):
        self.installer_dir = installer_dir
        PhosWindow.__init__(self, parent=parent)
        self.setTitleBar(SplitTitleBar(self))
        self._last_stack_idx: int = 0
        self.selected_directory: str = ""
        self.icon_path = icon_path

        # 设置为模态窗口
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        # 初始化窗口
        self.init_window()

        # 在创建其他子页面前先显示主界面
        self.show()

        self.create_sub_interface()

    def exec(self):
        """模态执行窗口，等待窗口关闭"""
        self._event_loop = QEventLoop()
        self._event_loop.exec()
        return bool(self.selected_directory)

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 如果没有选择目录，退出程序
        if not self.selected_directory:
            QApplication.quit()

        # 退出事件循环
        if hasattr(self, '_event_loop') and self._event_loop.isRunning():
            self._event_loop.quit()

        event.accept()

    def create_sub_interface(self) -> None:
        """
        创建子页面
        :return:
        """
        # 创建路径选择器界面，传入图标路径和安装器目录
        self.picker_interface = DirectoryPickerInterface(self, self.icon_path, self.installer_dir)
        self.addSubInterface(self.picker_interface, FluentIcon.FOLDER_ADD, "")

    def init_window(self):
        self.resize(600, 240)
        self.move(100, 100)

        # 布局样式调整
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.stackedWidget.setContentsMargins(0, 0, 0, 0)
        self.navigationInterface.setContentsMargins(0, 0, 0, 0)

        # 配置样式
        OdQtStyleSheet.NAVIGATION_INTERFACE.apply(self.navigationInterface)
        OdQtStyleSheet.STACKED_WIDGET.apply(self.stackedWidget)
        OdQtStyleSheet.TITLE_BAR.apply(self.titleBar)

        self.navigationInterface.setVisible(False)
