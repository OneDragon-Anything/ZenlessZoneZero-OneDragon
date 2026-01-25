from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, Property, QEasingCurve
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame
from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.utils.log_utils import log
from one_dragon.utils import os_utils
import yaml
import os


class ScrollCreditsWidget(QWidget):
    """
    电影致谢名单滚动字幕组件
    保持电影字幕风格的滚动效果，但优化了性能和用户体验
    """

    def __init__(self, ctx: OneDragonEnvContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx

        # 初始化UI
        self._init_ui()

        # 初始化动画
        self._init_animation()

        # 加载贡献者数据
        self._load_commit_data()

        # 启动滚动，但初始位置更合理
        self._start_scroll()

    def _init_ui(self):
        """
        初始化UI布局，保持电影字幕风格
        """
        self.setMinimumHeight(400)
        self.setStyleSheet("""
            ScrollCreditsWidget {
                background-color: black;
                border-radius: 8px;
            }
        """)

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建滚动区域以避免滚动条显示
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        # 滚动容器
        self.scroll_container = QWidget()
        self.scroll_container.setStyleSheet("background-color: transparent;")
        self.scroll_area.setWidget(self.scroll_container)

        self.main_layout.addWidget(self.scroll_area)

        # 内容布局
        self.content_layout = QVBoxLayout(self.scroll_container)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.content_layout.setSpacing(30)

        # 标题
        self.title_label = QLabel("ONE DRAGON PROJECT")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 32px;
                font-weight: bold;
                margin-bottom: 30px;
                font-family: Arial, sans-serif;
            }
        """)
        self.content_layout.addWidget(self.title_label)

        # 子标题
        self.subtitle_label = QLabel("特别鸣谢")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 20px;
                font-family: Arial, sans-serif;
            }
        """)
        self.content_layout.addWidget(self.subtitle_label)

        # 占位符，用于动态添加贡献者信息
        self.credits_container = QWidget()
        self.credits_container.setStyleSheet("background-color: transparent;")
        self.credits_layout = QVBoxLayout(self.credits_container)
        self.credits_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.credits_layout.setSpacing(15)  # 减少贡献者之间的间距
        self.content_layout.addWidget(self.credits_container)

        # 结尾标语
        self.end_label = QLabel("感谢您的支持与陪伴")
        self.end_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.end_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                margin-top: 80px;
                margin-bottom: 40px;
                font-family: Arial, sans-serif;
            }
        """)
        self.content_layout.addWidget(self.end_label)

    def _init_animation(self):
        """
        初始化滚动动画
        """
        # 使用定时器控制滚动，而非QPropertyAnimation
        pass

    def _load_commit_data(self):
        """
        从本地contributors.yaml文件加载贡献者信息
        """
        try:
            # 清空现有内容
            for i in reversed(range(self.credits_layout.count())):
                widget = self.credits_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()

            # 读取本地contributors.yaml文件
            contributors_file = os.path.join(os_utils.get_work_dir(), 'contributors.yaml')

            if not os.path.exists(contributors_file):
                # 如果文件不存在，显示提示
                no_file_label = QLabel("contributors.yaml文件不存在")
                no_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                no_file_label.setStyleSheet("""
                    QLabel {
                        color: #ff6666;
                        font-size: 16px;
                        font-style: italic;
                    }
                """)
                self.credits_layout.addWidget(no_file_label)
                return

            # 读取并解析YAML文件
            with open(contributors_file, 'r', encoding='utf-8') as f:
                contributors_data = yaml.safe_load(f)

            # 整合所有贡献者信息 - 按类别显示，支持自定义分组
            all_contributors = []

            # 定义类别及其显示名称和类型
            # core_contributors 和 documentation_contributors 中的每个项目是独立的贡献者
            # community_maintainers, recent_contributors, other_contributors 可能包含分组
            categories_individual = [
                ('core_contributors', '核心贡献者', 'core'),
                ('documentation_contributors', '文档贡献者', 'documentation')
            ]

            # 为个体贡献者类别添加标题和内容
            for category_key, display_name, category_type in categories_individual:
                if category_key in contributors_data:
                    # 为该类别添加类别标题
                    all_contributors.append({
                        'name': display_name,
                        'category': category_type,
                        'is_category_header': True
                    })
                    
                    # 添加该类别的具体贡献者
                    for item in contributors_data[category_key]:
                        if isinstance(item, dict) and 'name' in item:
                            # 为贡献者添加类别信息
                            item_with_category = item.copy()
                            item_with_category['category'] = category_type
                            item_with_category['is_category_header'] = False
                            all_contributors.append(item_with_category)
                        else:
                            # 如果是字符串格式，转换为字典格式
                            all_contributors.append({
                                'name': str(item),
                                'contributions': '',
                                'category': category_type,
                                'is_category_header': False
                            })

            # 处理可能包含分组的类别
            categories_grouped = [
                ('community_maintainers', '社区维护者', 'community'),
                ('recent_contributors', '近期贡献者', 'recent'),
                ('other_contributors', '其他贡献者', 'other')
            ]

            for category_key, display_name, category_type in categories_grouped:
                if category_key in contributors_data:
                    # 为该类别添加类别标题
                    all_contributors.append({
                        'name': display_name,
                        'category': category_type,
                        'is_category_header': True
                    })
                    
                    # 添加该类别的内容
                    for item in contributors_data[category_key]:
                        if isinstance(item, dict) and 'name' in item:
                            # 检查是否包含members字段，这表明它是一个分组
                            if 'members' in item:
                                # 这是一个分组，保留原样
                                item_with_category = item.copy()
                                item_with_category['category'] = category_type
                                item_with_category['is_category_header'] = False
                                all_contributors.append(item_with_category)
                            else:
                                # 这是一个单独的贡献者
                                item_with_category = item.copy()
                                item_with_category['category'] = category_type
                                item_with_category['is_category_header'] = False
                                all_contributors.append(item_with_category)
                        else:
                            # 如果是字符串格式，转换为字典格式
                            all_contributors.append({
                                'name': str(item),
                                'contributions': '',
                                'category': category_type,
                                'is_category_header': False
                            })

            # 添加贡献者信息到布局
            for contributor in all_contributors:
                contributor_widget = self._create_contributor_widget(contributor)
                self.credits_layout.addWidget(contributor_widget)

            # 如果没有贡献者信息，显示提示
            if not all_contributors:
                no_data_label = QLabel("未获取到贡献者信息")
                no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                no_data_label.setStyleSheet("""
                    QLabel {
                        color: #999999;
                        font-size: 16px;
                        font-style: italic;
                    }
                """)
                self.credits_layout.addWidget(no_data_label)

        except Exception as e:
            log.error(f"加载贡献者数据失败: {e}")
            # 添加错误信息
            error_label = QLabel(f"加载贡献者信息失败: {str(e)}")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("""
                QLabel {
                    color: #ff6666;
                    font-size: 16px;
                    font-style: italic;
                }
            """)
            self.credits_layout.addWidget(error_label)

    def _create_contributor_widget(self, contributor):
        """
        创建单个贡献者信息的widget，采用电影字幕风格

        Args:
            contributor: 贡献者信息字典，包含name和contributions

        Returns:
            显示贡献者信息的widget
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent;")

        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(10, 5, 10, 5)  # 减少单个贡献者控件的内外边距
        layout.setSpacing(4)  # 减少单个贡献者内部元素的间距

        # 检查是否是类别标题
        if contributor.get('is_category_header', False):
            # 类别标题样式
            title_text = contributor.get('name', '')
            name_label = QLabel(f"【{title_text}】")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setStyleSheet("""
                QLabel {
                    color: #ffffff;  /* 白色文字 */
                    font-size: 20px;
                    font-weight: bold;
                    padding: 10px;
                    font-family: Arial, sans-serif;
                    border-bottom: 1px solid #444444;
                    margin-bottom: 10px;
                }
            """)
            layout.addWidget(name_label)
            return widget

        # 名称/标题
        title_text = contributor.get('name', '')
        name_label = QLabel(f"{title_text}")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 统一使用白色样式，不分颜色
        name_label.setStyleSheet("""
            QLabel {
                color: #ffffff;  /* 白色文字 */
                font-size: 18px;
                font-weight: bold;
                padding: 5px;
                font-family: Arial, sans-serif;
            }
        """)
        
        layout.addWidget(name_label)

        # 如果是多成员分组（成员列表），合并为单个元素显示
        if 'members' in contributor and isinstance(contributor['members'], (list, tuple)):
            members = contributor['members']
            # 使用换行而不是分隔符来显示成员，避免渲染问题
            members_text = '\n'.join(str(m) for m in members)
            members_label = QLabel(members_text)
            members_label.setWordWrap(True)
            members_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            members_label.setStyleSheet("""
                QLabel {
                    color: #cccccc;  /* 灰色文字 */
                    font-size: 16px;
                    padding: 10px 20px;  /* 增加内边距以适应多行文本 */
                    font-family: Arial, sans-serif;
                }
            """)
            layout.addWidget(members_label)
            return widget

        # 贡献者角色（可选）
        if 'role' in contributor:
            role_label = QLabel(f"{contributor['role']}")
            role_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            role_label.setStyleSheet("""
                QLabel {
                    color: #cccccc;  /* 灰色文字 */
                    font-size: 16px;
                    padding: 5px;
                    font-style: italic;
                    font-family: Arial, sans-serif;
                }
            """)
            layout.addWidget(role_label)

        # 贡献次数（如果存在）
        if 'contributions' in contributor:
            contributions_label = QLabel(f"{contributor.get('contributions')}")
            contributions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            contributions_label.setStyleSheet("""
                QLabel {
                    color: #aaaaaa;  /* 深灰色文字 */
                    font-size: 14px;
                    padding: 5px;
                    font-family: Arial, sans-serif;
                }
            """)
            layout.addWidget(contributions_label)

        return widget

    def _start_scroll(self):
        """
        启动滚动动画，调整初始位置使内容更快进入视图
        """
        # 让容器先移动到视图底部附近，这样内容会很快出现
        container_height = self.scroll_container.height()
        widget_height = self.height()

        # 设置初始位置，使内容从接近视图底部开始，而不是非常远的地方
        initial_y = widget_height - 100  # 从视图底部上方100像素开始
        self.scroll_container.move(0, initial_y)

        # 设置动画终点位置，滚动到完全离开视图
        end_y = -container_height - 100  # 滚动到视图上方很远的位置

        # 使用定时器来控制滚动，而不是QPropertyAnimation，这样更灵活
        self.scroll_timer = QTimer()
        self.scroll_timer.timeout.connect(self._scroll_step)
        self.scroll_timer.start(24)  # 每12毫秒更新一次，加快滚动速度

        # 滚动参数
        self.current_y = initial_y
        self.scroll_speed = 2  # 每次滚动2像素，加快滚动速度
        self.target_y = end_y

    def _scroll_step(self):
        """
        执行滚动步骤
        """
        self.current_y -= self.scroll_speed
        self.scroll_container.move(0, self.current_y)

        # 检查是否滚动完成，如果是则重置位置
        if self.current_y <= self.target_y:
            # 重置到初始位置
            widget_height = self.height()
            self.current_y = widget_height - 100
            self.scroll_container.move(0, self.current_y)

    def resizeEvent(self, event):
        """
        窗口大小变化时重新调整
        """
        super().resizeEvent(event)

        # 重启滚动动画以适应新的尺寸
        if hasattr(self, 'scroll_timer'):
            self.scroll_timer.stop()
            self.scroll_timer.deleteLater()
        self._start_scroll()


