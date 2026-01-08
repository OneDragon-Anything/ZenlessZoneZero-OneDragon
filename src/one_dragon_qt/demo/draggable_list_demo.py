"""
可拖动列表组件演示

演示 DraggableList 组件的使用方法。
展示如何创建可拖动交换位置的列表，支持自定义列表行内容。
采用 Fluent Design 风格设计。
支持主题切换功能。
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
    Theme,
    qconfig,
    setTheme,
)

from one_dragon_qt.widgets.draggable_list import DraggableList


class TaskItem:
    """任务项数据类"""

    def __init__(self, id: str, title: str, priority: str):
        self.id = id
        self.title = title
        self.priority = priority

    def __repr__(self):
        return f"TaskItem(id={self.id}, title={self.title}, priority={self.priority})"


class TaskItemWidget(CardWidget):
    """任务项的自定义显示组件"""

    def __init__(self, task: TaskItem, parent=None):
        super().__init__(parent=parent)

        # 设置固定高度
        self.setFixedHeight(60)

        # 创建布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # 优先级标签
        self.priority_label = QLabel()
        self._set_priority_style(task.priority)
        self.priority_label.setFixedWidth(60)
        layout.addWidget(self.priority_label)

        # 标题标签
        self.title_label = StrongBodyLabel(task.title)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label, 1)

        # 拖拽提示
        self.drag_hint = CaptionLabel("☰ 拖拽调整顺序")
        self.drag_hint.setStyleSheet("color: gray;")
        layout.addWidget(self.drag_hint)

    def _set_priority_style(self, priority: str):
        """设置优先级标签的样式"""
        priority_map = {
            "高": ("🔴 高", "#d13438"),
            "中": ("🟡 中", "#ff8c00"),
            "低": ("🟢 低", "#107c10"),
        }

        if priority in priority_map:
            text, color = priority_map[priority]
            self.priority_label.setText(text)
            self.priority_label.setStyleSheet(
                f"QLabel {{ "
                f"background-color: {color}; "
                f"color: white; "
                f"padding: 4px 8px; "
                f"border-radius: 4px; "
                f"font-weight: bold; "
                f" }}"
            )
            self.priority_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def update_task(self, task: TaskItem):
        """更新显示的任务信息"""
        self.title_label.setText(task.title)
        self._set_priority_style(task.priority)


class DraggableListDemo(FluentWindow):
    """可拖动列表演示窗口"""

    def __init__(self) -> None:
        """初始化演示窗口"""
        super().__init__()
        self.setWindowTitle("DraggableList - 可拖动列表演示")
        self.resize(700, 600)

        # 创建子界面
        self.demo_interface = QWidget()
        self.demo_interface.setObjectName("demoInterface")
        self.addSubInterface(
            self.demo_interface,
            FluentIcon.MOVE,
            "组件演示"
        )

        # 创建布局
        layout = QVBoxLayout(self.demo_interface)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # 创建主题切换按钮
        self.theme_btn = PushButton("🌙 切换到暗色主题")
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        # 创建组件演示区域
        self._create_demo_section(layout)

        layout.addStretch()

        # 根据当前主题更新按钮文本
        self._update_theme_btn()

    def _create_demo_section(self, layout: QVBoxLayout) -> None:
        """创建组件演示区域"""
        # 标题
        title_label = SubtitleLabel("DraggableList 组件演示")
        layout.addWidget(title_label)

        # 说明
        info_label = BodyLabel(
            "下方展示了可拖动列表组件的使用方法。\n\n"
            "✨ 功能特点：\n"
            "  • 支持拖拽交换列表项位置\n"
            "  • 支持自定义列表行内容\n"
            "  • 实时显示当前顺序\n"
            "  • 提供顺序变化信号\n\n"
            "📝 使用方法：\n"
            "  鼠标左键按住列表项，拖动到目标位置松开即可交换位置。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 创建可拖动列表
        list_title = StrongBodyLabel("任务列表（可拖拽调整顺序）")
        layout.addWidget(list_title)

        # 创建列表组件
        self.drag_list = DraggableList()
        self.drag_list.order_changed.connect(self._on_order_changed)
        layout.addWidget(self.drag_list)

        # 添加示例任务
        self._add_sample_tasks()

        # 显示当前顺序的标签
        self.result_label = CaptionLabel("当前顺序: 已加载 5 个任务")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        # 添加操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.add_btn = PushButton("➕ 添加新任务")
        self.add_btn.clicked.connect(self._add_new_task)
        btn_layout.addWidget(self.add_btn)

        self.reset_btn = PushButton("🔄 重置列表")
        self.reset_btn.clicked.connect(self._reset_list)
        btn_layout.addWidget(self.reset_btn)

        layout.addLayout(btn_layout)

    def _add_sample_tasks(self) -> None:
        """添加示例任务"""
        sample_tasks = [
            TaskItem("1", "完成需求分析文档", "高"),
            TaskItem("2", "设计系统架构", "高"),
            TaskItem("3", "实现核心功能模块", "中"),
            TaskItem("4", "编写单元测试", "中"),
            TaskItem("5", "准备用户手册", "低"),
        ]

        for task in sample_tasks:
            widget = TaskItemWidget(task)
            self.drag_list.add_item(task, widget)

    def _on_order_changed(self, data_list: list) -> None:
        """当顺序改变时更新显示"""
        task_count = len(data_list)
        order_text = " → ".join([f"{task.title[:4]}..." for task in data_list[:5]])
        if task_count > 5:
            order_text += f" → ... (共{task_count}项)"

        self.result_label.setText(f"✅ 当前顺序 ({task_count}项):\n{order_text}")

        # 显示成功提示
        InfoBar.success(
            title="顺序已更新",
            content=f"列表项位置已交换",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def _add_new_task(self) -> None:
        """添加新任务"""
        task_count = self.drag_list.get_item_count()
        new_task = TaskItem(
            str(task_count + 1),
            f"新任务 {task_count + 1}",
            "中"
        )
        widget = TaskItemWidget(new_task)
        self.drag_list.add_item(new_task, widget)

        # 更新显示
        self._on_order_changed(self.drag_list.get_data_list())

    def _reset_list(self) -> None:
        """重置列表"""
        self.drag_list.clear()
        self._add_sample_tasks()

        # 更新显示
        self._on_order_changed(self.drag_list.get_data_list())

        InfoBar.info(
            title="列表已重置",
            content="已恢复为初始任务列表",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def _toggle_theme(self) -> None:
        """切换主题"""
        current_theme = qconfig.theme
        new_theme = Theme.DARK if current_theme == Theme.LIGHT else Theme.LIGHT
        setTheme(new_theme)
        self._update_theme_btn()

    def _update_theme_btn(self) -> None:
        """更新主题按钮文本"""
        if qconfig.theme == Theme.LIGHT:
            self.theme_btn.setText("🌙 切换到暗色主题")
        else:
            self.theme_btn.setText("☀️ 切换到亮色主题")


def main() -> None:
    """主函数"""
    app = QApplication(sys.argv)
    window = DraggableListDemo()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
