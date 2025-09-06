import os
import locale
import webbrowser
from PySide6.QtCore import Qt, QEventLoop, QSize
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QFileDialog, QApplication, QWidget
from PySide6.QtGui import QPixmap
from qfluentwidgets import (FluentIcon, PrimaryPushButton, ToolButton, LineEdit, MessageBox,
                            SplitTitleBar, SubtitleLabel, PixmapLabel, PushButton, SettingCardGroup)
from one_dragon_qt.windows.window import PhosWindow
from one_dragon_qt.services.styles_manager import OdQtStyleSheet


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
                'select_other': '选择其他目录'
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
                'select_other': 'Select Other'
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
        except:
            return 'zh'


class DirectoryPickerInterface(QWidget):
    """路径选择器界面"""

    def __init__(self, parent=None, icon_path=None):
        QWidget.__init__(self, parent=parent)
        self.setObjectName("directory_picker_interface")
        self.selected_path = ""
        self.icon_path = icon_path
        self.translator = DirectoryPickerTranslator(DirectoryPickerTranslator.detect_language())
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
                pixel_ratio = self.devicePixelRatio()
                target_size = QSize(96, 96)
                scaled_pixmap = pixmap.scaled(
                    target_size * pixel_ratio,
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                scaled_pixmap.setDevicePixelRatio(pixel_ratio)
                icon_label.setPixmap(scaled_pixmap)
                icon_label.setFixedSize(target_size)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                main_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 标题
        self.title_label = SubtitleLabel(self.translator.get_text('title'))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_label)

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

        main_layout.addLayout(path_layout)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.confirm_btn = PrimaryPushButton(self.translator.get_text('confirm'))
        self.confirm_btn.setIcon(FluentIcon.ACCEPT)
        self.confirm_btn.setMinimumSize(120, 36)  # 设置最小尺寸使按钮变大
        self.confirm_btn.clicked.connect(self._on_confirm_clicked)
        self.confirm_btn.setEnabled(False)
        button_layout.addWidget(self.confirm_btn)
        button_layout.addStretch(1)

        main_layout.addLayout(button_layout)

        # 添加间距
        main_layout.addSpacing(20)
        
        # 底部链接按钮组
        links_group = SettingCardGroup('相关链接')
        main_layout.addWidget(links_group)
        
        # 创建链接按钮容器
        links_widget = QWidget()
        links_layout = QHBoxLayout(links_widget)
        links_layout.setContentsMargins(20, 10, 20, 10)
        links_layout.setSpacing(15)
        
        # 帮助文档按钮
        self.help_btn = PushButton('📚 帮助文档')
        self.help_btn.clicked.connect(self._on_help_clicked)
        self.help_btn.setMinimumWidth(120)
        links_layout.addWidget(self.help_btn)
        
        # QQ频道按钮
        self.qq_channel_btn = PushButton('💬 QQ频道')
        self.qq_channel_btn.clicked.connect(self._on_qq_channel_clicked)
        self.qq_channel_btn.setMinimumWidth(120)
        links_layout.addWidget(self.qq_channel_btn)
        
        # 官网按钮
        self.website_btn = PushButton('🌐 官网')
        self.website_btn.clicked.connect(self._on_website_clicked)
        self.website_btn.setMinimumWidth(120)
        links_layout.addWidget(self.website_btn)
        
        # GitHub仓库按钮
        self.github_btn = PushButton('⭐ GitHub')
        self.github_btn.clicked.connect(self._on_github_clicked)
        self.github_btn.setMinimumWidth(120)
        links_layout.addWidget(self.github_btn)
        
        main_layout.addWidget(links_widget)

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
        if self.selected_path:
            # 获取顶层窗口
            window = self.window()
            if isinstance(window, DirectoryPickerWindow):
                window.selected_directory = self.selected_path
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

    def _on_help_clicked(self):
        """点击帮助按钮时打开排障文档"""
        try:
            webbrowser.open("https://docs.qq.com/doc/p/7add96a4600d363b75d2df83bb2635a7c6a969b5")
        except Exception as e:
            print(f"无法打开浏览器: {e}")

    def _on_qq_channel_clicked(self):
        """点击QQ频道按钮时打开QQ频道"""
        try:
            webbrowser.open("https://pd.qq.com/g/onedrag00n")
        except Exception as e:
            print(f"无法打开QQ频道: {e}")

    def _on_website_clicked(self):
        """点击官网按钮时打开官网"""
        try:
            webbrowser.open("https://one-dragon.com/zzz/zh/home.html")
        except Exception as e:
            print(f"无法打开官网: {e}")

    def _on_github_clicked(self):
        """点击GitHub按钮时打开GitHub仓库"""
        try:
            webbrowser.open("https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon")
        except Exception as e:
            print(f"无法打开GitHub仓库: {e}")


class DirectoryPickerWindow(PhosWindow):

    def __init__(self,
                 parent=None,
                 icon_path=None):
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
        return True if self.selected_directory else False

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
        # 创建路径选择器界面，传入图标路径
        self.picker_interface = DirectoryPickerInterface(self, self.icon_path)
        self.addSubInterface(self.picker_interface, FluentIcon.FOLDER_ADD, "")

    def init_window(self):
        self.resize(600, 360)  # 再次增加高度以容纳SettingCardGroup的标题
        self.move(100, 100)

        # 布局样式调整
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.stackedWidget.setContentsMargins(0, 0, 0, 0)
        self.navigationInterface.setContentsMargins(0, 0, 0, 0)

        # 配置样式
        OdQtStyleSheet.APP_WINDOW.apply(self)
        OdQtStyleSheet.NAVIGATION_INTERFACE.apply(self.navigationInterface)
        OdQtStyleSheet.STACKED_WIDGET.apply(self.stackedWidget)
        OdQtStyleSheet.TITLE_BAR.apply(self.titleBar)

        self.navigationInterface.setVisible(False)
