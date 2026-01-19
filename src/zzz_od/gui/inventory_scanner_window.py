"""
独立的仓库扫描器GUI
直接使用主项目的模块，无需复制代码
"""
import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
# 当前文件: src/zzz_od/gui/inventory_scanner_window.py
# 需要向上3级到项目根目录，然后添加 src 目录
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent
src_path = project_root / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import threading
from typing import Optional

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (
    PushButton, setTheme, Theme,
    InfoBar, InfoBarPosition, FluentIcon
)

from zzz_od.context.zzz_context import ZContext
from zzz_od.application.inventory_scan import inventory_scan_const
from one_dragon.base.operation.application import application_const
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.log_display_card import LogDisplayCard


class StatusSignal(QObject):
    """状态信号，用于线程安全的UI更新"""
    show_info = Signal(str, str)  # title, content
    show_success = Signal(str, str)
    show_warning = Signal(str, str)
    show_error = Signal(str, str)
    scan_finished = Signal()  # 扫描完成信号


class InventoryScannerWindow(QWidget):
    """仓库扫描器主窗口"""

    def __init__(self):
        super().__init__()
        self.ctx: Optional[ZContext] = None
        self.scan_thread: Optional[threading.Thread] = None
        self.status_signal = StatusSignal()

        self._init_window()
        self._init_ui()
        self._connect_signals()

    def _init_window(self):
        """初始化窗口"""
        self.setWindowTitle("绝区零 - 仓库扫描器")
        self.resize(800, 600)

        # 居中显示
        screen = QApplication.primaryScreen()
        geometry = screen.availableGeometry()
        w, h = geometry.width(), geometry.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 标题栏区域 (可选，如果以后想加自定义标题栏)
        
        # 2. 内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(16)
        
        # 3. 顶部操作栏 (按钮 + 说明)
        action_bar = QWidget()
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(12)

        # 开始扫描按钮
        self.start_btn = PushButton("开始扫描", self)
        self.start_btn.setIcon(FluentIcon.PLAY)
        self.start_btn.setFixedHeight(40)
        self.start_btn.setMinimumWidth(120)
        action_layout.addWidget(self.start_btn)

        # 停止扫描按钮
        self.stop_btn = PushButton("停止扫描", self)
        self.stop_btn.setIcon(FluentIcon.PAUSE)
        self.stop_btn.setFixedHeight(40)
        self.stop_btn.setMinimumWidth(120)
        self.stop_btn.setEnabled(False)
        action_layout.addWidget(self.stop_btn)

        action_layout.addStretch()
        content_layout.addWidget(action_bar)

        # 4. 日志显示区域 - 使用 LogDisplayCard
        # 给日志卡片加个标题或容器效果会更好，但 LogDisplayCard 本身已经封装好了
        self.log_card = LogDisplayCard(self)
        content_layout.addWidget(self.log_card)

        main_layout.addWidget(content_widget)

        # 设置背景色（可选，匹配 Fluent 主题）
        self.setStyleSheet("InventoryScannerWindow { background-color: rgb(243, 243, 243); }")

    def _connect_signals(self):
        """连接信号"""
        self.start_btn.clicked.connect(self._on_start_clicked)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.status_signal.show_info.connect(self._show_info_bar)
        self.status_signal.show_success.connect(self._show_success_bar)
        self.status_signal.show_warning.connect(self._show_warning_bar)
        self.status_signal.show_error.connect(self._show_error_bar)
        self.status_signal.scan_finished.connect(self._on_scan_finished)

    def _on_start_clicked(self):
        """开始扫描按钮点击"""
        try:
            # 禁用开始按钮，启用停止按钮
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)

            # 启动日志显示
            self.log_card.start(clear_log=True)

            # 显示提示
            log.info("正在初始化上下文...")
            self.status_signal.show_info.emit("开始扫描", "请确保游戏窗口已打开")

            # 在新线程中初始化和运行
            self.scan_thread = threading.Thread(target=self._run_scan, daemon=True)
            self.scan_thread.start()

        except Exception as e:
            log.error(f"启动失败: {str(e)}")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.log_card.stop()
            self.status_signal.show_error.emit("启动失败", str(e))

    def _on_stop_clicked(self):
        """停止扫描按钮点击"""
        if self.ctx:
            log.info("正在停止扫描...")
            self.ctx.run_context.stop_running()
            self.stop_btn.setEnabled(False)

    def _run_scan(self):
        """运行扫描（在子线程中）"""
        try:
            # 初始化上下文
            log.info("初始化上下文...")
            self.ctx = ZContext()
            self.ctx.init()

            log.info("上下文初始化完成")
            log.info("开始扫描...")
            log.info("应用会自动导航到各个仓库界面")
            log.info("-" * 50)

            # 使用 run_context 运行应用
            self.ctx.run_context.run_application(
                app_id=inventory_scan_const.APP_ID,
                instance_idx=self.ctx.current_instance_idx,
                group_id=application_const.DEFAULT_GROUP_ID,
            )

            # 显示结果
            log.info("-" * 50)
            if self.ctx.run_context.is_context_stop:
                log.info("扫描完成！")
                # 显示成功提示
                self.status_signal.show_success.emit("扫描完成", "仓库扫描已完成，数据已保存")
            else:
                log.warning("扫描未完成")
                # 显示警告提示
                self.status_signal.show_warning.emit("扫描未完成", "扫描被中断")

        except Exception as e:
            error_msg = f"扫描失败: {str(e)}"
            log.error(error_msg, exc_info=True)

            # 显示错误提示
            self.status_signal.show_error.emit("扫描失败", str(e))

        finally:
            # 发送扫描完成信号
            self.status_signal.scan_finished.emit()

    def _on_scan_finished(self):
        """扫描完成后的处理"""
        # 停止日志显示
        self.log_card.stop()
        # 恢复按钮状态
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _show_info_bar(self, title: str, content: str):
        """显示信息提示"""
        InfoBar.info(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def _show_success_bar(self, title: str, content: str):
        """显示成功提示"""
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )

    def _show_warning_bar(self, title: str, content: str):
        """显示警告提示"""
        InfoBar.warning(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )

    def _show_error_bar(self, title: str, content: str):
        """显示错误提示"""
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )


def main():
    """主函数"""
    # 设置高DPI缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # 创建应用
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

    # 设置主题（可以从配置读取，这里默认使用LIGHT）
    setTheme(Theme.LIGHT)

    # 创建并显示窗口
    window = InventoryScannerWindow()
    window.show()
    window.activateWindow()

    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
