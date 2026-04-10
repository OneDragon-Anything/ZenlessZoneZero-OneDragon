import json
import os
from dataclasses import dataclass
from typing import Callable, Any
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from qfluentwidgets import TableWidget, ScrollArea
from PySide6.QtCore import Qt, Signal, QSize, QThread
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QGridLayout,
    QWidget,
    QDialog,
    QScrollArea,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtGui import QPixmap, QCursor
from qfluentwidgets import FluentIcon, PushButton, SegmentedWidget
from dataclasses import dataclass
from typing import Callable, Any
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from qfluentwidgets import TableWidget, ScrollArea
from PySide6.QtCore import Qt, Signal, QSize, QThread
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QGridLayout,
    QWidget,
    QDialog,
    QScrollArea,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtGui import QPixmap, QCursor
from qfluentwidgets import FluentIcon, PushButton, SegmentedWidget
from one_dragon.utils import os_utils
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.base_interface import BaseInterface
from zzz_od.application.inventory_scan import inventory_scan_const
from zzz_od.application.inventory_scan.inventory_scan_config import AgentScanOptionEnum
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from one_dragon.base.config.config_item import ConfigItem
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QHeaderView
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    InfoBarIcon,
    PrimaryPushButton,
    PushButton,
    SimpleCardWidget,
    SubtitleLabel,
    SwitchButton,
    ComboBox
)
from one_dragon_qt.utils.layout_utils import Margins
from one_dragon_qt.widgets.column import Column


class ReportLoader(QThread):
    """报告加载子线程"""
    finished = Signal(dict, dict)  # 传递报告文件和翻译字典
    error = Signal(str)

    def __init__(self, data_file_path, wiki_file_path):
        super().__init__()
        self.data_file_path = data_file_path
        self.wiki_file_path = wiki_file_path

    def run(self):
        try:
            # 加载报告文件
            report_files = {}
            for file_name in os.listdir(self.data_file_path):
                if '_data' in file_name and file_name.endswith('.json'):
                    agent_name = file_name.split('_data')[0]
                    report_files[agent_name] = os.path.join(self.data_file_path, file_name)
            
            # 加载翻译文件
            translation_dict = {}
            translation_file_path = os.path.join(self.wiki_file_path, 'zzz_translation.json')
            if os.path.exists(translation_file_path):
                with open(translation_file_path, 'r', encoding='utf-8') as f:
                    translation_data = json.load(f)
                    translation_dict = translation_data.get('character', {})
            
            self.finished.emit(report_files, translation_dict)
        except Exception as e:
            self.error.emit(str(e))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QHeaderView
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    InfoBarIcon,
    PrimaryPushButton,
    PushButton,
    SimpleCardWidget,
    SubtitleLabel,
    SwitchButton,
    ComboBox
)
from one_dragon_qt.utils.layout_utils import Margins
from one_dragon_qt.widgets.column import Column


class ReportLoader(QThread):
    """报告加载子线程"""
    finished = Signal(dict, dict)  # 传递报告文件和翻译字典
    error = Signal(str)

    def __init__(self, data_file_path, wiki_file_path):
        super().__init__()
        self.data_file_path = data_file_path
        self.wiki_file_path = wiki_file_path

    def run(self):
        try:
            # 加载报告文件
            report_files = {}
            for file_name in os.listdir(self.data_file_path):
                if '_data' in file_name and file_name.endswith('.json'):
                    agent_name = file_name.split('_data')[0]
                    report_files[agent_name] = os.path.join(self.data_file_path, file_name)
            
            # 加载翻译文件
            translation_dict = {}
            translation_file_path = os.path.join(self.wiki_file_path, 'zzz_translation.json')
            if os.path.exists(translation_file_path):
                with open(translation_file_path, 'r', encoding='utf-8') as f:
                    translation_data = json.load(f)
                    translation_dict = translation_data.get('character', {})
            
            self.finished.emit(report_files, translation_dict)
        except Exception as e:
            self.error.emit(str(e))


class InventoryScanInterface(AppRunInterface):
    """仓库扫描界面，支持预扫描和特定扫描两种模式"""

    MODE_PRE_SCAN = '预扫描'
    MODE_SPECIAL_SCAN = '特定扫描'
    """仓库扫描界面，支持预扫描和特定扫描两种模式"""

    MODE_PRE_SCAN = '预扫描'
    MODE_SPECIAL_SCAN = '特定扫描'

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.app: ZApplication | None = None
        # 初始化数据文件路径
        # 初始化数据文件路径
        self.data_file_path = os_utils.get_path_under_work_dir('.debug', 'inventory_data')
        # 初始化角色权重数据路径
        self.character_weight_file_path = os_utils.get_path_under_work_dir('assets', 'character_weight')
        #初始化wiki数据路径
        self.wiki_file_path = os_utils.get_path_under_work_dir('assets', 'wiki_data')

        self._init = False
        # 初始化权重数据
        self.agent_weights = {}
        self._load_weights_data()
        # 初始化角色权重数据路径
        self.character_weight_file_path = os_utils.get_path_under_work_dir('assets', 'character_weight')
        #初始化wiki数据路径
        self.wiki_file_path = os_utils.get_path_under_work_dir('assets', 'wiki_data')

        self._init = False
        # 初始化权重数据
        self.agent_weights = {}
        self._load_weights_data()

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=inventory_scan_const.APP_ID,
            object_name='inventory_scan_interface',
            nav_text_cn='仓库扫描',
            nav_icon=FluentIcon.SEARCH,
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        """构建顶部内容区域，包含模式切换和配置"""
        top = Column()

        # SegmentedWidget 模式切换
        self.mode_segment = SegmentedWidget()
        self.mode_segment.addItem(
            routeKey=self.MODE_PRE_SCAN, text=self.MODE_PRE_SCAN,
            onClick=lambda: self._apply_mode(self.MODE_PRE_SCAN),
        )
        self.mode_segment.addItem(
            routeKey=self.MODE_SPECIAL_SCAN, text=self.MODE_SPECIAL_SCAN,
            onClick=lambda: self._apply_mode(self.MODE_SPECIAL_SCAN),
        )
        top.add_widget(self.mode_segment)

        # 配置区域 QStackedWidget（高度跟随当前页面）
        self.mode_stacked = QStackedWidget()
        self.pre_scan_page = self._build_pre_scan_page()
        self.special_scan_page = self._build_special_scan_page()
        self.mode_stacked.addWidget(self.pre_scan_page)
        self.mode_stacked.addWidget(self.special_scan_page)
        self.mode_stacked.currentChanged.connect(self._on_stacked_page_changed)
        top.add_widget(self.mode_stacked)

        # 默认选择预扫描模式
        self.mode_segment.setCurrentItem(self.MODE_PRE_SCAN)
        # 初始化时触发一次页面切换事件，确保QStackedWidget高度正确设置
        self._on_stacked_page_changed(0)

        return top

    def _update_agent_options(self) -> None:
        """更新特定扫描的代理人选项"""
    def get_widget_at_top(self) -> QWidget:
        """构建顶部内容区域，包含模式切换和配置"""
        top = Column()

        # SegmentedWidget 模式切换
        self.mode_segment = SegmentedWidget()
        self.mode_segment.addItem(
            routeKey=self.MODE_PRE_SCAN, text=self.MODE_PRE_SCAN,
            onClick=lambda: self._apply_mode(self.MODE_PRE_SCAN),
        )
        self.mode_segment.addItem(
            routeKey=self.MODE_SPECIAL_SCAN, text=self.MODE_SPECIAL_SCAN,
            onClick=lambda: self._apply_mode(self.MODE_SPECIAL_SCAN),
        )
        top.add_widget(self.mode_segment)

        # 配置区域 QStackedWidget（高度跟随当前页面）
        self.mode_stacked = QStackedWidget()
        self.pre_scan_page = self._build_pre_scan_page()
        self.special_scan_page = self._build_special_scan_page()
        self.mode_stacked.addWidget(self.pre_scan_page)
        self.mode_stacked.addWidget(self.special_scan_page)
        self.mode_stacked.currentChanged.connect(self._on_stacked_page_changed)
        top.add_widget(self.mode_stacked)

        # 默认选择预扫描模式
        self.mode_segment.setCurrentItem(self.MODE_PRE_SCAN)
        # 初始化时触发一次页面切换事件，确保QStackedWidget高度正确设置
        self._on_stacked_page_changed(0)

        return top

    def _update_agent_options(self) -> None:
        """更新特定扫描的代理人选项"""
        agent_names_file_path = os.path.join(self.data_file_path, 'agent_names.json')
        # 特定扫描只读取代理人名称，不包含默认选项
        options = []
        try:
            # 读取翻译文件
            translation_file_path = os.path.join(self.wiki_file_path, 'zzz_translation.json')
            translation_dict = {}
            if os.path.exists(translation_file_path):
                with open(translation_file_path, 'r', encoding='utf-8') as f:
                    translation_data = json.load(f)
                    translation_dict = translation_data.get('character', {})
            
            # 读取权重配置文件列表
            weight_dir = self.character_weight_file_path
            weight_files = set()
            if os.path.exists(weight_dir):
                for file_name in os.listdir(weight_dir):
                    if file_name.endswith('.json') and not file_name.startswith('_'):
                        weight_files.add(file_name.replace('.json', ''))
            
            # 读取文件并添加代理人选项
            with open(agent_names_file_path, 'r', encoding='utf-8') as f:
                agent_names = json.load(f)
                for code in agent_names:
                    # 检查是否存在于权重配置文件中
                    if code in weight_files:
                        # 映射为中文名
                        if code in translation_dict:
                            chs_name = translation_dict[code].get('CHS', code)
                        else:
                            chs_name = code
                    else:
                        # 检查是否存在于翻译文件中
                        if code in translation_dict:
                            chs_name = f"{translation_dict[code].get('CHS', code)} (权重配置缺失)"
                        else:
                            chs_name = f"{code} (未定义)"
                    options.append(ConfigItem(chs_name, code))
        except FileNotFoundError:
            log.info(f"文件 {agent_names_file_path} 不存在，请先执行预扫描生成代理人列表")
        except json.JSONDecodeError:
            log.error(f"文件 {agent_names_file_path} 或翻译文件格式错误")
        except Exception as e:
            log.error(f"更新代理人选项失败: {e}")
        # 更新下拉框选项
        if hasattr(self, 'scan_agent_opt'):
            self.scan_agent_opt.set_options_by_list(options)

    def on_interface_shown(self) -> None:
        """在界面显示时调用"""
        super().on_interface_shown()
        # 更新特定扫描的代理人选项
        self._update_agent_options()  

    def _build_pre_scan_page(self) -> QWidget:
        """构建预扫描页面"""
        page = Column()

        # 使用说明
        self.help_opt = HelpCard(
            title='使用说明',
            content='预扫描将扫描所有代理人信息并生成代理人列表，供后续特定扫描使用。'
        )
        page.add_widget(self.help_opt)

        return page

    def _build_special_scan_page(self) -> QWidget:
        """构建特定扫描页面"""
        page = Column()

        # 使用说明
        self.special_help_opt = HelpCard(
            title='使用说明',
            content='特定扫描将扫描指定代理人的详细装备信息（驱动盘和音擎）。'
        )
        page.add_widget(self.special_help_opt)

        # 查看代理人检查报告
        self.check_report_btn = PushButton(
            icon=FluentIcon.VIEW,
            text=f"{gt('查看代理人检查报告')}", 
        )
        self.check_report_btn.clicked.connect(self._on_check_report_clicked)
        page.add_widget(self.check_report_btn)

        # 特定代理人选择
        self.scan_agent_opt = ComboBoxSettingCard(
            icon=FluentIcon.SEARCH,
            title='选择代理人',
            content='选择要扫描的特定代理人'
        )
        page.add_widget(self.scan_agent_opt)

        return page

    def _on_stacked_page_changed(self, index: int) -> None:
        """切换页面时，让 QStackedWidget 高度跟随当前页面"""
        for i in range(self.mode_stacked.count()):
            w = self.mode_stacked.widget(i)
            if i == index:
                w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            else:
                w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.mode_stacked.adjustSize()

    def _apply_mode(self, mode: str) -> None:
        """应用模式切换"""
        is_pre_scan = mode == self.MODE_PRE_SCAN

        # 如果切换到特定扫描模式，更新代理人选项
        if not is_pre_scan:
            self._update_agent_options()

        # 切换页面
        self.mode_stacked.setCurrentWidget(
            self.pre_scan_page if is_pre_scan else self.special_scan_page
        )

    def _on_start_clicked(self) -> None:
        """在启动应用前保存用户选择的配置"""
        # 获取当前模式
        current_mode = self.MODE_PRE_SCAN
        if hasattr(self, 'mode_segment'):
            current_mode = self.mode_segment.currentRouteKey()

        # 根据模式设置 scan_agent_option
        if current_mode == self.MODE_PRE_SCAN:
            # 预扫描模式：设置为更新代理人列表
            setattr(self.ctx, '_inventory_scan_agent_option', AgentScanOptionEnum.UPDATE_AGENTS.value.value)
            log.info(f"预扫描模式：更新代理人列表")
        else:
            # 特定扫描模式：保存选择的代理人
            if hasattr(self, 'scan_agent_opt') and self.scan_agent_opt:
                selected_value = self.scan_agent_opt.getValue()
                setattr(self.ctx, '_inventory_scan_agent_option', selected_value)
                log.info(f"特定扫描模式：选择的代理人: {selected_value}")

        #print(f"当前扫描模式: {current_mode}")

        # 调用父类方法启动应用
        AppRunInterface._on_start_clicked(self)

    def _on_check_report_clicked(self) -> None:
        """查看代理人检查报告"""
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        
        # 显示加载弹窗
        self.loading_dialog = QProgressDialog("加载报告中...", None, 0, 0, self)
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.show()

        # 启动子线程
        self.loader = ReportLoader(self.data_file_path, self.wiki_file_path)
        self.loader.finished.connect(self.on_report_loaded)
        self.loader.error.connect(self.on_report_load_error)
        self.loader.start()

    def on_report_load_error(self, error_message):
        """报告加载失败"""
        self.loading_dialog.close()
        log.error(f"报告加载失败: {error_message}")
        from qfluentwidgets import MessageBox
        msg_box = MessageBox('加载失败', f'报告加载失败: {error_message}', self)
        msg_box.exec()

    def on_report_loaded(self, report_files, translation_dict):
        """报告加载完成"""
        self.loading_dialog.close()
        
        if not report_files:
            log.info("未找到报告文件")
            return
        
        from one_dragon_qt.windows.app_window_base import AppWindowBase
        from one_dragon_qt.widgets.column import Column
        from one_dragon_qt.widgets.row import Row as HRow
        from one_dragon_qt.widgets.base_interface import BaseInterface
        from qfluentwidgets import (SimpleCardWidget, SubtitleLabel, BodyLabel, 
                                  PrimaryPushButton, PushButton, FluentIcon, ScrollArea)
        from one_dragon_qt.utils.layout_utils import Margins
        
        # 创建报告窗口
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QWidget
        from PySide6.QtCore import Qt
        
        # 导入InventoryDataProcessor类和os_utils模块
        from zzz_od.application.inventory_scan.InventoryDataProcessor import InventoryDataProcessor
        from one_dragon.utils import os_utils
        
        dialog = QDialog(self, Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        dialog.setWindowTitle(gt('代理人检查报告'))
        dialog.resize(900, 650)
        
        # 主布局
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # 顶部导航栏 - 使用项目自定义布局
        nav_card = SimpleCardWidget()
        nav_layout = QVBoxLayout(nav_card)
        nav_layout.setContentsMargins(16, 4, 16, 4)  # 进一步减小上下边距
        
        # 滚动区域 - 用于代理人选择
        scroll_area = ScrollArea()
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedHeight(70)  # 进一步减小高度
        
        # 滚动内容
        scroll_content = QWidget()
        scroll_layout = QHBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # 驱动盘详细信息 - 使用卡片
        disk_card = SimpleCardWidget()
        disk_layout = QVBoxLayout(disk_card)
        disk_layout.setContentsMargins(16, 16, 16, 16)
        
        # 详情页面容器
        from PySide6.QtWidgets import QStackedWidget
        self.detail_stacked = QStackedWidget()
        
        # 代理人详细页面
        agent_detail_page = QWidget()
        agent_detail_layout = QHBoxLayout(agent_detail_page)
        agent_detail_layout.setContentsMargins(0, 0, 0, 0)
        agent_detail_layout.setSpacing(16)
        
        # 左侧：完整的一个卡片
        left_card = SimpleCardWidget()
        left_card.setFixedWidth(300)
        self.left_card_layout = QVBoxLayout(left_card)
        self.left_card_layout.setContentsMargins(16, 16, 16, 16)
        self.left_card_layout.setSpacing(8)
        self.left_card_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # 左侧卡片标题
        self.agent_info_title = SubtitleLabel()
        self.agent_info_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.left_card_layout.addWidget(self.agent_info_title)
        
        # 左侧卡片内容
        self.agent_info_label = BodyLabel()
        self.agent_info_label.setWordWrap(True)
        self.left_card_layout.addWidget(self.agent_info_label)
        
        agent_detail_layout.addWidget(left_card)
        
        # 右侧：3个相同大小的卡片，垂直排列
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)
        
        # 创建三个卡片
        self.agent_cards = []
        for i in range(3):
            card = SimpleCardWidget()
            card.setFixedHeight(150)
            card_content_layout = QVBoxLayout(card)
            card_content_layout.setContentsMargins(16, 16, 16, 16)
            card_content_layout.setSpacing(8)
            card_content_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            
            # 卡片标题
            card_title = SubtitleLabel()
            card_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
            card_content_layout.addWidget(card_title)
            
            # 卡片内容
            card_content = BodyLabel()
            card_content.setWordWrap(True)
            card_content_layout.addWidget(card_content)
            
            right_layout.addWidget(card)
            self.agent_cards.append((card_title, card_content))
        
        agent_detail_layout.addWidget(right_container)
        
        self.detail_stacked.addWidget(agent_detail_page)
        
        # 驱动盘详细页面
        disk_detail_page = QWidget()
        disk_detail_layout = QVBoxLayout(disk_detail_page)
        
        # 卡片网格布局
        from PySide6.QtWidgets import QGridLayout
        card_grid = QGridLayout()
        card_grid.setSpacing(3)  # 减小卡片之间的间距
        
        # 卡片列表，用于更新内容
        disk_cards = []
        
        # 预创建所有驱动盘卡片和控件
        from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
        from qfluentwidgets import FluentIcon
        
        for i in range(2):
            for j in range(3):
                card = SimpleCardWidget()
                card.setFixedHeight(290)  # 增加卡片高度以容纳详细信息按钮
                
                # 使用网格布局实现两列布局：左侧词条名，右侧得分
                card_layout = QGridLayout(card)
                card_layout.setContentsMargins(16, 16, 16, 16)  # 调整内边距
                card_layout.setSpacing(3)  # 设置间距
                card_layout.setColumnStretch(0, 1)  # 左侧列可伸缩
                card_layout.setColumnStretch(1, 0)  # 右侧列固定宽度
                
                # 驱动盘名称(等级|品级)
                name_text_label = BodyLabel()
                name_text_label.setStyleSheet("font-weight: bold; font-size: 20px;")  # 最大字体
                
                # 总得分
                total_score_label = BodyLabel()
                total_score_label.setStyleSheet("font-weight: bold; font-size: 20px;")  # 最大字体
                
                # 主词条名称
                main_label = BodyLabel()
                main_label.setStyleSheet("font-size: 15px;")  # 中等字体
                
                # 主词条权重得分
                main_score_label = BodyLabel()
                main_score_label.setStyleSheet("font-size: 15px;")  # 中等字体
                
                # 副词条1
                sub1_label = BodyLabel()
                sub1_label.setStyleSheet("font-size: 12px;")  # 最小字体
                sub1_score_label = BodyLabel()
                sub1_score_label.setStyleSheet("font-size: 12px;")  # 最小字体
                
                # 副词条2
                sub2_label = BodyLabel()
                sub2_label.setStyleSheet("font-size: 12px;")  # 最小字体
                sub2_score_label = BodyLabel()
                sub2_score_label.setStyleSheet("font-size: 12px;")  # 最小字体
                
                # 副词条3
                sub3_label = BodyLabel()
                sub3_label.setStyleSheet("font-size: 12px;")  # 最小字体
                sub3_score_label = BodyLabel()
                sub3_score_label.setStyleSheet("font-size: 12px;")  # 最小字体
                
                # 副词条4
                sub4_label = BodyLabel()
                sub4_label.setStyleSheet("font-size: 12px;")  # 最小字体
                sub4_score_label = BodyLabel()
                sub4_score_label.setStyleSheet("font-size: 12px;")  # 最小字体
                
                # 添加到网格布局
                card_layout.addWidget(name_text_label, 0, 0, Qt.AlignmentFlag.AlignLeft)
                card_layout.addWidget(total_score_label, 0, 1, Qt.AlignmentFlag.AlignRight)
                card_layout.addWidget(main_label, 1, 0, Qt.AlignmentFlag.AlignLeft)
                card_layout.addWidget(main_score_label, 1, 1, Qt.AlignmentFlag.AlignRight)
                card_layout.addWidget(sub1_label, 2, 0, Qt.AlignmentFlag.AlignLeft)
                card_layout.addWidget(sub1_score_label, 2, 1, Qt.AlignmentFlag.AlignRight)
                card_layout.addWidget(sub2_label, 3, 0, Qt.AlignmentFlag.AlignLeft)
                card_layout.addWidget(sub2_score_label, 3, 1, Qt.AlignmentFlag.AlignRight)
                card_layout.addWidget(sub3_label, 4, 0, Qt.AlignmentFlag.AlignLeft)
                card_layout.addWidget(sub3_score_label, 4, 1, Qt.AlignmentFlag.AlignRight)
                card_layout.addWidget(sub4_label, 5, 0, Qt.AlignmentFlag.AlignLeft)
                card_layout.addWidget(sub4_score_label, 5, 1, Qt.AlignmentFlag.AlignRight)
                
                # 添加详细信息按钮
                detail_button = PushButton()
                detail_button.setText("计算详细")
                detail_button.setFixedSize(120, 32)
                # 设置按钮样式，确保文本可见
                detail_button.setStyleSheet(""" 
                    QPushButton {
                        color: black;
                        font-size: 12px;
                        font-weight: normal;
                        background-color: #f0f0f0;
                        border: 1px solid #d0d0d0;
                        border-radius: 4px;
                        text-align: center;
                    }
                    QPushButton:hover {
                        background-color: #e0e0e0;
                    }
                    QPushButton:pressed {
                        background-color: #d0d0d0;
                    }
                """)
                card_layout.addWidget(detail_button, 6, 0, 1, 2, Qt.AlignmentFlag.AlignCenter)
                # 确保按钮可见
                detail_button.setVisible(True)
                detail_button.update()
                
                card_grid.addWidget(card, i, j)
                disk_cards.append((name_text_label, total_score_label, main_label, main_score_label, sub1_label, sub1_score_label, sub2_label, sub2_score_label, sub3_label, sub3_score_label, sub4_label, sub4_score_label, detail_button))
        
        disk_detail_layout.addLayout(card_grid)
        self.detail_stacked.addWidget(disk_detail_page)
        
        # 音擎详细页面
        engine_detail_page = QWidget()
        engine_detail_layout = QHBoxLayout(engine_detail_page)
        engine_detail_layout.setContentsMargins(0, 0, 0, 0)
        engine_detail_layout.setSpacing(16)
        
        # 左侧卡片：音擎信息
        from qfluentwidgets import SimpleCardWidget
        left_card = SimpleCardWidget()
        left_card_layout = QVBoxLayout(left_card)
        left_card_layout.setContentsMargins(16, 16, 16, 16)
        left_card_layout.setSpacing(8)
        left_card_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # 左侧卡片标题
        from qfluentwidgets import SubtitleLabel
        left_title = SubtitleLabel(text=gt('音擎信息'))
        left_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        left_card_layout.addWidget(left_title)
        
        # 音擎信息显示
        self.engine_info_label = BodyLabel()
        self.engine_info_label.setWordWrap(True)
        left_card_layout.addWidget(self.engine_info_label)
        
        # 设置左侧卡片固定宽度
        left_card.setFixedWidth(350)
        engine_detail_layout.addWidget(left_card)
        
        # 右侧布局：两个卡片
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)
        
        # 右侧卡片1：音擎推荐1
        right_card1 = SimpleCardWidget()
        right_card1_layout = QVBoxLayout(right_card1)
        right_card1_layout.setContentsMargins(16, 16, 16, 16)
        right_card1_layout.setSpacing(8)
        right_card1_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # 右侧卡片1标题
        right_title1 = SubtitleLabel(text=gt('音擎推荐1'))
        right_title1.setAlignment(Qt.AlignmentFlag.AlignLeft)
        right_card1_layout.addWidget(right_title1)
        
        # 音擎推荐1显示
        self.engine_recommend1_label = BodyLabel()
        self.engine_recommend1_label.setWordWrap(True)
        self.engine_recommend1_label.setText(gt('推荐音擎信息将在此显示'))
        right_card1_layout.addWidget(self.engine_recommend1_label)
        
        right_layout.addWidget(right_card1)
        
        # 右侧卡片2：音擎推荐2
        right_card2 = SimpleCardWidget()
        right_card2_layout = QVBoxLayout(right_card2)
        right_card2_layout.setContentsMargins(16, 16, 16, 16)
        right_card2_layout.setSpacing(8)
        right_card2_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # 右侧卡片2标题
        right_title2 = SubtitleLabel(text=gt('音擎推荐2'))
        right_title2.setAlignment(Qt.AlignmentFlag.AlignLeft)
        right_card2_layout.addWidget(right_title2)
        
        # 音擎推荐2显示
        self.engine_recommend2_label = BodyLabel()
        self.engine_recommend2_label.setWordWrap(True)
        self.engine_recommend2_label.setText(gt('推荐音擎信息将在此显示'))
        right_card2_layout.addWidget(self.engine_recommend2_label)
        
        right_layout.addWidget(right_card2)
        
        engine_detail_layout.addLayout(right_layout)
        
        self.detail_stacked.addWidget(engine_detail_page)
        
        # 页面切换函数
        def _switch_detail_page(page_key):
            """切换详情页面"""
            if page_key == 'agent_detail':
                self.detail_stacked.setCurrentIndex(0)
                # 重新加载当前代理人的详细信息
                if selected_agent:
                    load_report(selected_agent)
            elif page_key == 'disk_detail':
                self.detail_stacked.setCurrentIndex(1)
                # 重新加载当前代理人的驱动盘信息
                if selected_agent:
                    load_report(selected_agent)
            elif page_key == 'engine_detail':
                self.detail_stacked.setCurrentIndex(2)
                # 重新加载当前代理人的音擎信息
                if selected_agent:
                    load_report(selected_agent)
        
        # 添加导航栏
        from qfluentwidgets import SegmentedWidget
        self.detail_segment = SegmentedWidget()
        # 调整顺序，将代理人详细放在第一位
        self.detail_segment.addItem(
            routeKey='agent_detail', text=gt('代理人详细'),
            onClick=lambda: _switch_detail_page('agent_detail'),
        )
        self.detail_segment.addItem(
            routeKey='disk_detail', text=gt('驱动盘详细'),
            onClick=lambda: _switch_detail_page('disk_detail'),
        )
        self.detail_segment.addItem(
            routeKey='engine_detail', text=gt('音擎详细'),
            onClick=lambda: _switch_detail_page('engine_detail'),
        )
        disk_layout.addWidget(self.detail_segment)
        
        disk_layout.addWidget(self.detail_stacked)
        
        # 初始化当前页面为代理人详细
        self.current_detail_page = 'agent_detail'
        self.detail_segment.setCurrentItem('agent_detail')
        self.detail_stacked.setCurrentIndex(0)
        

        
        # 添加角色按钮
        selected_agent = None
        agent_buttons = []
        
        # 创建InventoryDataProcessor实例
        processor = InventoryDataProcessor()
        # 加载槽位映射
        slot_mapping_file = os_utils.get_path_under_work_dir('assets', 'character_weight', '_tool', 'slot_Mapping.json')
        slot_mapping = processor.load_slot_mapping(slot_mapping_file)
        
        # 使用子线程加载的翻译字典
        
        # 先定义load_report和on_agent_clicked函数的框架
        def load_report(agent_name):
            """加载并显示指定代理人的报告"""
            pass
        
        def on_agent_clicked(agent_name):
            """处理代理人点击事件"""
            pass
        
        # 创建角色按钮
        from qfluentwidgets import PushButton
        for agent_name in report_files:
            # 映射为中文名称
            chs_name = agent_name
            if agent_name in translation_dict:
                chs_name = translation_dict[agent_name].get('CHS', agent_name)
            btn = PushButton(text=chs_name)
            btn.setFixedSize(100, 60)
            btn.clicked.connect(lambda checked, name=agent_name: on_agent_clicked(name))
            scroll_layout.addWidget(btn)
            agent_buttons.append((btn, agent_name))
        
        scroll_area.setWidget(scroll_content)
        nav_layout.addWidget(scroll_area)
        
        # 布局更新
        scroll_content.adjustSize()
        
        # 添加到主布局
        main_layout.addWidget(nav_card)
        main_layout.addSpacing(16)
        main_layout.addWidget(disk_card)
        
        # 移除关闭按钮，使用窗口默认关闭按钮
        
        # 定义完整的update_disk_cards函数
        def update_disk_cards(equipped_discs, agent_name=None):
            """根据驱动盘数据更新卡片内容"""
            # 清空所有卡片（跳过按钮）
            for card_labels in disk_cards:
                # 前12个是标签，最后一个是按钮
                for i, label in enumerate(card_labels):
                    if i < 12:  # 只清空标签的文本，跳过按钮
                        label.setText('')
            
            # 转换驱动盘数据为中文
            converted_discs = processor.convert_drive_disc_stats_to_chinese(equipped_discs, slot_mapping)
            
            # 加载角色权重配置
            character_weight = None
            if agent_name:
                weight_file_path = os.path.join(self.character_weight_file_path, f"{agent_name}.json")
                if os.path.exists(weight_file_path):
                    try:
                        with open(weight_file_path, 'r', encoding='utf-8') as f:
                            character_weight = json.load(f)
                    except Exception as e:
                        log.error(f"加载权重文件失败: {e}")
            
            # 为所有6个驱动盘位置处理
            for i in range(6):
                if i >= len(disk_cards):
                    break
                
                # 获取当前位置的驱动盘数据
                disc_key = str(i + 1)
                disc = converted_discs.get(disc_key, {})
                
                name_text_label, total_score_label, main_label, main_score_label, sub1_label, sub1_score_label, sub2_label, sub2_score_label, sub3_label, sub3_score_label, sub4_label, sub4_score_label, detail_button = disk_cards[i]
                
                # 为详细信息按钮添加点击事件 - 使用工厂函数避免闭包变量问题
                def create_detail_clicked_handler(disc_data, position, main_stat_key, main_scr, sub_stats, total_scr, relative_score, score_ceiling, char_weight, agent_name):
                    def handler():
                        """显示驱动盘详细计算信息"""
                        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
                        from PySide6.QtCore import Qt
                        
                        dialog = QDialog(self, Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
                        dialog.setWindowTitle(f"驱动盘计算详细 - {position}号位")
                        dialog.resize(500, 450)
                        
                        layout = QVBoxLayout(dialog)
                        
                        # 创建文本编辑框显示详细信息
                        text_edit = QTextEdit()
                        text_edit.setReadOnly(True)
                        
                        # 构建详细信息文本
                        if not disc_data:
                            # 未装备驱动盘
                            detail_text = f"驱动盘: 未装备\n"
                            detail_text += f"位置: {position}号位\n"
                            detail_text += f"等级: 0\n"
                            detail_text += f"品质: 未知\n\n"
                            
                            detail_text += f"主词条: 未知\n"
                            # 1-3号位主词条不参与计算
                            if 1 <= position <= 3:
                                detail_text += f"主词条得分: 0.0 (不参与计算)\n\n"
                            else:
                                detail_text += f"主词条得分: 0.0\n\n"
                            
                            detail_text += "副词条:\n"
                            detail_text += "  无\n"
                            detail_text += f"\n总得分: 0.0\n"
                            detail_text += f"得分上限: 0.0\n"
                            detail_text += f"相对得分: 0.0\n"
                            if char_weight:
                                detail_text += f"\n代理人有效权重 ({agent_name}):\n"
                                # 显示所有权重项
                                weight_items = list(char_weight.items())
                                for key, value in weight_items:
                                    if value > 0:
                                        detail_text += f"  {key}: {value:.1f}\n"
                            else:
                                detail_text += "\n角色权重参考: 未加载\n"
                        else:
                            # 已装备驱动盘
                            detail_text = f"驱动盘: {disc_data.get('setKey', '未知')}\n"
                            detail_text += f"位置: {position}号位\n"
                            detail_text += f"等级: {disc_data.get('level', 0)}\n"
                            detail_text += f"品质: {disc_data.get('rarity', '未知')}\n\n"
                            
                            # 主词条信息
                            main_stat_key_display = disc_data.get('mainStatKeyChinese', disc_data.get('mainStatKey', '未知'))
                            detail_text += f"主词条: {main_stat_key_display}\n"
                            # 1-3号位主词条不参与计算
                            if 1 <= position <= 3:
                                detail_text += f"主词条得分: {main_scr:.1f} (不参与计算)\n\n"
                            else:
                                detail_text += f"主词条得分: {main_scr:.1f}\n\n"
                            
                            # 副词条信息
                            detail_text += "副词条:\n"
                            substats = disc_data.get('substats', [])
                            if substats:
                                for substat in substats[:4]:
                                    substat_key = substat.get('keyChinese', substat.get('key', '未知'))
                                    substat_upgrades = substat.get('upgrades', 0)
                                    # 计算该副词条的得分
                                    substat_weight = char_weight.get(substat_key, 0) if char_weight else 0
                                    sub_score = substat_weight * substat_upgrades
                                    detail_text += f"  {substat_key}+{substat_upgrades}: {sub_score:.1f}\n"
                            else:
                                detail_text += "  无\n"
                            
                            # 总得分
                            detail_text += f"\n总得分: {total_scr:.1f}\n"
                            detail_text += f"得分上限: {score_ceiling:.1f}\n"
                            detail_text += f"相对得分: {relative_score:.1f}\n"
                            
                            # 角色权重信息
                            if char_weight:
                                detail_text += f"\n角色有效权重参考 ({agent_name}):\n"
                                # 显示所有权重项
                                weight_items = list(char_weight.items())
                                for key, value in weight_items:
                                    if value > 0:
                                        detail_text += f"  {key}: {value:.1f}\n"
                            else:
                                detail_text += "\n角色权重参考: 未加载\n"
                        
                        text_edit.setPlainText(detail_text)
                        layout.addWidget(text_edit)
                        
                        # 添加关闭按钮
                        close_button = QPushButton("关闭")
                        close_button.clicked.connect(dialog.close)
                        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignCenter)
                        
                        dialog.exec()
                    return handler
                
                # 断开之前的所有连接，避免重复触发
                import warnings
                # 忽略 RuntimeWarning 警告
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        detail_button.clicked.disconnect()
                    except Exception:
                        # 忽略任何可能的异常
                        pass
                
                if disc:
                    # 已装备驱动盘
                    set_key = disc.get('setKey', '未知')
                    rarity = disc.get('rarity', '未知')
                    level = disc.get('level', 0)
                    
                    # 驱动盘名称(等级|品级)
                    name_text_label.setText(f"{set_key}({level}|{rarity})")
                    
                    # 计算得分
                    main_score = 0
                    sub_scores = [0, 0, 0, 0]
                    total_score = 0
                    
                    if character_weight:
                        # 添加position字段用于评分
                        disc_with_position = disc.copy()
                        disc_with_position['position'] = int(disc_key)
                        # 计算实际得分
                        score_data = processor.calculate_actual_disc_score(disc_with_position, character_weight, slot_mapping)
                        main_score = score_data['mainStatScore']
                        total_score = score_data['totalScore']
                        relative_score = score_data.get('relativeScore', 0)
                        score_ceiling = score_data.get('score_ceiling', 0)
                        # 为每个原始副词条计算得分
                        substats = disc.get('substats', [])
                        for j, substat in enumerate(substats[:4]):
                            substat_key = substat.get('keyChinese', substat.get('key', '未知'))
                            substat_upgrades = substat.get('upgrades', 0)
                            substat_weight = character_weight.get(substat_key, 0)
                            sub_scores[j] = substat_weight * substat_upgrades
                    
                    # 创建并连接点击事件处理函数
                    main_stat_key = disc.get('mainStatKeyChinese', disc.get('mainStatKey', '未知'))
                    detail_button.clicked.connect(create_detail_clicked_handler(disc, int(disc_key), main_stat_key, main_score, sub_scores, total_score, relative_score, score_ceiling, character_weight, agent_name))
                    
                    # 显示总得分（使用相对得分）
                    total_score_label.setText(f"{relative_score:.1f}")
                    
                    # 主词条名称和权重得分
                    main_stat_key = disc.get('mainStatKeyChinese', disc.get('mainStatKey', '未知'))
                    main_label.setText(f"{main_stat_key}")
                    main_score_label.setText(f"{main_score:.1f}")
                    
                    # 副词条和权重得分
                    substats = disc.get('substats', [])
                    for j, substat in enumerate(substats[:4]):
                        substat_key = substat.get('keyChinese', substat.get('key', '未知'))
                        substat_upgrades = substat.get('upgrades', 0)
                        sub_score = sub_scores[j]
                        if j == 0:
                            sub1_label.setText(f"{substat_key}+{substat_upgrades}")
                            sub1_score_label.setText(f"{sub_score:.1f}")
                        elif j == 1:
                            sub2_label.setText(f"{substat_key}+{substat_upgrades}")
                            sub2_score_label.setText(f"{sub_score:.1f}")
                        elif j == 2:
                            sub3_label.setText(f"{substat_key}+{substat_upgrades}")
                            sub3_score_label.setText(f"{sub_score:.1f}")
                        elif j == 3:
                            sub4_label.setText(f"{substat_key}+{substat_upgrades}")
                            sub4_score_label.setText(f"{sub_score:.1f}")
                else:
                    # 未装备驱动盘
                    # 创建并连接点击事件处理函数
                    detail_button.clicked.connect(create_detail_clicked_handler({}, i + 1, '未知', 0, [0, 0, 0, 0], 0, 0, 0, character_weight, agent_name))
        

        
        # 定义完整的load_report函数
        def load_report(agent_name):
            """加载并显示指定代理人的报告"""
            if agent_name not in report_files:
                update_disk_cards({})
                self.agent_info_label.setText(gt('未找到该代理人的报告文件'))
                self.engine_info_label.setText(gt('未找到该代理人的报告文件'))
                # 隐藏扫描时间标签
                if hasattr(self, 'scan_time_label'):
                    self.scan_time_label.setVisible(False)
                return
            
            # 获取中文名称
            chs_name = agent_name
            if agent_name in translation_dict:
                chs_name = translation_dict[agent_name].get('CHS', agent_name)
            
            report_file_path = report_files[agent_name]
            try:
                with open(report_file_path, 'r', encoding='utf-8') as f:
                    report = json.load(f)
                # 更新驱动盘卡片
                equipped_discs = report.get('equippedDiscs', {})
                update_disk_cards(equipped_discs, agent_name)
                
                # 获取扫描时间
                scan_time = report.get('scanTime', '未知')
                
                # 更新代理人详细信息
                self.agent_info_title.setText(f"{chs_name}的详细信息")
                agent_info = []
                agent_info.append(f"- {gt('等级')}: {report.get('level', '未知')}")
                agent_info.append(f"- {gt('影画')}: {report.get('mindscape', '未知')}")
                agent_info.append(f"- {gt('突破等级')}: {report.get('promotion', '未知')}")
                
                self.agent_info_label.setText('\n'.join(agent_info))
                
                # 显示扫描时间
                try:
                    # 先从布局中移除旧的扫描时间标签
                    if hasattr(self, 'scan_time_label') and self.scan_time_label is not None:
                        try:
                            # 从布局中移除旧控件
                            self.left_card_layout.removeWidget(self.scan_time_label)
                            # 清除旧控件
                            self.scan_time_label.deleteLater()
                        except:
                            pass
                    
                    # 创建新的扫描时间标签
                    from qfluentwidgets import CaptionLabel
                    from PySide6.QtCore import Qt
                    self.scan_time_label = CaptionLabel()
                    self.scan_time_label.setText(f"扫描时间: {scan_time}")
                    self.scan_time_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
                    self.scan_time_label.setStyleSheet("font-size: 10px; color: #666666;")
                    # 添加到标题下方
                    self.left_card_layout.insertWidget(1, self.scan_time_label)
                except Exception as e:
                    log.error(f"更新扫描时间标签失败: {str(e)}")
                
                # 更新代理人详细信息
                try:
                    if self.agent_cards:
                        # 卡片1：提升建议
                        card1_title, card1_content = self.agent_cards[0]
                        try:
                            card1_title.setText(f"{chs_name}的提升建议")
                            card1_content.setText(
                                "当前功能正在开发"
                            )
                        except Exception as e:
                            log.error(f"更新卡片1失败: {str(e)}")
                        
                        # 卡片2：技能信息
                        card2_title, card2_content = self.agent_cards[1]
                        try:
                            card2_title.setText(f"{chs_name}的技能信息")
                            skills_info = []
                            skills_info.append(f"- {gt('普通攻击等级')}: {report.get('basic', '未知')}")
                            skills_info.append(f"- {gt('连携技等级')}: {report.get('chain', '未知')}")
                            skills_info.append(f"- {gt('特殊技等级')}: {report.get('special', '未知')}")
                            skills_info.append(f"- {gt('支援技等级')}: {report.get('assist', '未知')}")
                            card2_content.setText('\n'.join(skills_info))
                        except Exception as e:
                            log.error(f"更新卡片2失败: {str(e)}")
                        
                        # 卡片3：装备信息
                        card3_title, card3_content = self.agent_cards[2]
                        try:
                            card3_title.setText(f"{chs_name}的装备信息")
                            equipment_info = []
                            if 'equippedWengine' in report and report['equippedWengine']:
                                engine = report['equippedWengine']
                                engine_name = engine.get('key', '未知')
                                engine_level = engine.get('level', 0)
                                equipment_info.append(f"- 音擎: {engine_name} (等级: {engine_level})")
                            else:
                                equipment_info.append("- 音擎: 无")
                            
                            equipped_discs = report.get('equippedDiscs', {})
                            if equipped_discs:
                                equipment_info.append("- 驱动盘: 已装备")
                            else:
                                equipment_info.append("- 驱动盘: 未装备")
                            
                            card3_content.setText('\n'.join(equipment_info))
                        except Exception as e:
                            log.error(f"更新卡片3失败: {str(e)}")
                except Exception as e:
                    log.error(f"更新代理人卡片信息失败: {str(e)}")
                
                # 更新音擎详细信息
                try:
                    engine_info = []
                    if 'equippedWengine' in report:
                        engine = report['equippedWengine']
                        engine_name = engine.get('key', '未知')
                        engine_level = engine.get('level', 0)
                        engine_modification = engine.get('modification', 0)
                        engine_promotion = engine.get('promotion', 0)
                        engine_info.append(f"\n{gt('音擎名称')}: {engine_name}")
                        engine_info.append(f"{gt('等级')}: {engine_level}")
                        #engine_info.append(f"{gt('改造')}: {engine_modification}")
                        engine_info.append(f"{gt('突破等级')}: {engine_promotion}")
                    else:
                        engine_info.append(f"\n{gt('未装备音擎')}")
                    
                    # 检查控件是否有效
                    if hasattr(self, 'engine_info_label') and self.engine_info_label is not None:
                        if hasattr(self.engine_info_label, 'isValid') and self.engine_info_label.isValid():
                            self.engine_info_label.setText('\n'.join(engine_info))
                        else:
                            # 直接尝试更新，不依赖 isValid 方法
                            try:
                                self.engine_info_label.setText('\n'.join(engine_info))
                            except:
                                pass
                    
                    # 更新音擎推荐信息
                    # 这里可以根据实际情况获取推荐音擎数据
                    recommend1_info = [
                        f"{gt('推荐音擎1')}: 示例音擎A",
                        f"{gt('推荐理由')}: 适合当前角色的输出定位",
                        f"{gt('核心属性')}: 攻击力 + 异常精通"
                    ]
                    if hasattr(self, 'engine_recommend1_label') and self.engine_recommend1_label is not None:
                        if hasattr(self.engine_recommend1_label, 'isValid') and self.engine_recommend1_label.isValid():
                            self.engine_recommend1_label.setText('\n'.join(recommend1_info))
                        else:
                            # 直接尝试更新，不依赖 isValid 方法
                            try:
                                self.engine_recommend1_label.setText('\n'.join(recommend1_info))
                            except:
                                pass
                    
                    recommend2_info = [
                        f"{gt('推荐音擎2')}: 示例音擎B",
                        f"{gt('推荐理由')}: 提供更多生存能力",
                        f"{gt('核心属性')}: 生命值 + 防御力"
                    ]
                    if hasattr(self, 'engine_recommend2_label') and self.engine_recommend2_label is not None:
                        if hasattr(self.engine_recommend2_label, 'isValid') and self.engine_recommend2_label.isValid():
                            self.engine_recommend2_label.setText('\n'.join(recommend2_info))
                        else:
                            # 直接尝试更新，不依赖 isValid 方法
                            try:
                                self.engine_recommend2_label.setText('\n'.join(recommend2_info))
                            except:
                                pass
                except Exception as e:
                    log.error(f"更新音擎信息失败: {str(e)}")
            except Exception as e:
                update_disk_cards({})
                # 检查控件是否有效并尝试更新
                error_msg = f"{gt('读取报告失败')}: {str(e)}"
                
                # 更新 agent_info_label
                if hasattr(self, 'agent_info_label') and self.agent_info_label is not None:
                    try:
                        self.agent_info_label.setText(error_msg)
                    except:
                        pass
                
                # 更新 engine_info_label
                if hasattr(self, 'engine_info_label') and self.engine_info_label is not None:
                    try:
                        self.engine_info_label.setText(error_msg)
                    except:
                        pass
                
                # 更新 engine_recommend1_label
                if hasattr(self, 'engine_recommend1_label') and self.engine_recommend1_label is not None:
                    try:
                        self.engine_recommend1_label.setText(error_msg)
                    except:
                        pass
                
                # 更新 engine_recommend2_label
                if hasattr(self, 'engine_recommend2_label') and self.engine_recommend2_label is not None:
                    try:
                        self.engine_recommend2_label.setText(error_msg)
                    except:
                        pass
                
                log.error(f"加载报告失败: {str(e)}")
        
        # 定义完整的on_agent_clicked函数
        def on_agent_clicked(agent_name):
            nonlocal selected_agent
            selected_agent = agent_name
            # 更新按钮状态
            for btn, name in agent_buttons:
                if name == agent_name:
                    btn.setStyleSheet("border: 2px solid #0078d4; border-radius: 4px;")
                else:
                    btn.setStyleSheet("")
            # 加载并显示报告
            load_report(agent_name)
        
        # 如果有角色，默认选中第一个
        if agent_buttons:
            on_agent_clicked(agent_buttons[0][1])
        
        # 显示窗口
        dialog.exec()
    
    def _on_agent_weight_clicked(self) -> None:
        """打开代理人权重管理界面"""
        # 定义权重表格列结构
        @dataclass
        class WeightColumnMeta:
            """权重表格列元数据"""
            display_name: str
            attr_name: str | None = None
            parser: Callable[[str], Any] | None = None
            width: int | None = None  # None = 自动宽度
            formatter: Callable[[Any], str] | None = None  # 属性值 → 显示文本，None = str()
        
        WEIGHT_COLUMNS: list[WeightColumnMeta] = [
            WeightColumnMeta('权重类型', 'weight_type', lambda x: x, 200),
            WeightColumnMeta('权重值', 'weight', lambda x: float(x) if x else 0.5, 100),
        ]
        
        WEIGHT_FIELD_2_COLUMN: dict[str, int] = {col.display_name: idx for idx, col in enumerate(WEIGHT_COLUMNS)}
        
        # 创建权重管理窗口
        dialog = QDialog(self, Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        dialog.setWindowTitle(gt('代理人权重管理'))
        dialog.resize(1000, 600)
        
        # 主布局
        main_layout = QHBoxLayout(dialog)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # 左侧列：说明和操作
        left_column = Column(spacing=16, margins=Margins(0, 0, 0, 0))
        left_column.setFixedWidth(300)
        main_layout.addWidget(left_column, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        # 标题区域
        title_card = SimpleCardWidget()
        title_layout = Column(spacing=8, margins=Margins(16, 16, 16, 16))
        title_card_layout = QVBoxLayout(title_card)
        title_card_layout.setContentsMargins(0, 0, 0, 0)
        title_card_layout.addWidget(title_layout)
        
        title_label = SubtitleLabel(text=gt('代理人权重管理'))
        title_layout.add_widget(title_label)
        
        hint_label = CaptionLabel(text=gt('管理各个代理人的权重值，用于优先级排序'))
        hint_label.setWordWrap(True)
        title_layout.add_widget(hint_label)
        
        left_column.add_widget(title_card)
        
        # 角色选择区域
        agent_card = SimpleCardWidget()
        agent_layout = Column(spacing=12, margins=Margins(16, 16, 16, 16))
        agent_card_layout = QVBoxLayout(agent_card)
        agent_card_layout.setContentsMargins(0, 0, 0, 0)
        agent_card_layout.addWidget(agent_layout)
        
        agent_title = BodyLabel(text=gt('选择代理人'))
        agent_layout.add_widget(agent_title)
        
        agent_combo = ComboBox()
        agent_layout.add_widget(agent_combo)
        
        # 更新角色选择下拉框
        self._update_agent_combo(agent_combo)
        
        # 默认选择第一个角色
        if agent_combo.count() > 0:
            agent_combo.setCurrentIndex(0)
        
        left_column.add_widget(agent_card)
        
        # 操作按钮区域
        action_card = SimpleCardWidget()
        action_layout = Column(spacing=12, margins=Margins(16, 16, 16, 16))
        action_card_layout = QVBoxLayout(action_card)
        action_card_layout.setContentsMargins(0, 0, 0, 0)
        action_card_layout.addWidget(action_layout)
        
        btn_load = PrimaryPushButton(text=gt('加载权重数据'), icon=FluentIcon.DOWNLOAD)
        action_layout.add_widget(btn_load)
        
        btn_save = PrimaryPushButton(text=gt('保存权重数据'), icon=FluentIcon.SAVE)
        action_layout.add_widget(btn_save)
        
        btn_reset = PushButton(text=gt('重置为默认值'), icon=FluentIcon.SYNC)
        action_layout.add_widget(btn_reset)
        
        left_column.add_widget(action_card)
        
        # 说明卡片
        info_card = SimpleCardWidget()
        info_layout = Column(spacing=8, margins=Margins(16, 16, 16, 16))
        info_card_layout = QVBoxLayout(info_card)
        info_card_layout.setContentsMargins(0, 0, 0, 0)
        info_card_layout.addWidget(info_layout)
        
        info_title = BodyLabel(text=gt('使用说明'))
        info_layout.add_widget(info_title)
        
        info_items = [
            gt('权重值范围：0-1'),
            gt('权重越高，优先级越高'),
            gt('默认权重：0.5'),
            gt('加载：从文件加载权重数据'),
            gt('保存：将权重数据保存到文件'),
            gt('重置：将所有权重重置为默认值'),
        ]
        
        for item in info_items:
            item_label = CaptionLabel(text=item)
            info_layout.add_widget(item_label)
        
        left_column.add_widget(info_card)
        left_column.add_stretch(1)
        
        # 右侧列：权重表格
        right_column = Column(spacing=16, margins=Margins(0, 0, 0, 16))
        right_column.setFixedWidth(650)
        main_layout.addWidget(right_column, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        # 表格卡片
        table_card = SimpleCardWidget()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(16, 16, 16, 16)
        
        table_title = SubtitleLabel(text=gt('代理人权重列表'))
        table_layout.addWidget(table_title)
        
        # 创建表格
        weight_table = TableWidget()
        
        # 初始化表格数据
        def update_weight_table():
            weight_table.blockSignals(True)
            weight_table.setRowCount(0)
            current_agent = agent_combo.currentText()
            if not current_agent or current_agent not in self.agent_weights:
                weight_table.blockSignals(False)
                return
            
            for weight_type, data in self.agent_weights[current_agent].items():
                row = weight_table.rowCount()
                weight_table.insertRow(row)
                
                # 权重类型
                type_item = QTableWidgetItem(weight_type)
                type_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                weight_table.setItem(row, 0, type_item)
                
                # 权重值 - 添加类型检查
                if isinstance(data, dict) and 'weight' in data:
                    weight_item = QTableWidgetItem(str(data['weight']))
                else:
                    # 如果数据格式不正确，使用默认值
                    weight_item = QTableWidgetItem('0.5')
                weight_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                weight_table.setItem(row, 1, weight_item)
            weight_table.blockSignals(False)
            # 同步表格大小
            sync_table_size()
        
        # 表格单元格变化事件处理
        def on_weight_table_cell_changed(row: int, column: int) -> None:
            current_agent = agent_combo.currentText()
            if not current_agent or current_agent not in self.agent_weights:
                return
            if row < 0 or row >= weight_table.rowCount():
                return
            
            weight_type = weight_table.item(row, 0).text()
            if weight_type not in self.agent_weights[current_agent]:
                return
            
            # 处理权重值变化
            if column == 1:  # 权重值列
                weight_item = weight_table.item(row, 1)
                if not weight_item:
                    return
                
                text = weight_item.text().strip()
                try:
                    weight = float(text)
                    # 确保权重值在0-1范围内
                    weight = max(0, min(1, weight))
                    # 更新数据
                    if not isinstance(self.agent_weights[current_agent][weight_type], dict):
                        self.agent_weights[current_agent][weight_type] = {'weight': 0.5, 'enabled': True}
                    self.agent_weights[current_agent][weight_type]['weight'] = weight
                    # 更新显示
                    weight_item.setText(str(weight))
                except ValueError:
                    # 恢复原来的值
                    if isinstance(self.agent_weights[current_agent][weight_type], dict) and 'weight' in self.agent_weights[current_agent][weight_type]:
                        weight_item.setText(str(self.agent_weights[current_agent][weight_type]['weight']))
                    else:
                        weight_item.setText('0.5')
        
        weight_table.cellChanged.connect(on_weight_table_cell_changed)
        weight_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        weight_table.setBorderVisible(True)
        weight_table.setBorderRadius(8)
        weight_table.setWordWrap(True)
        weight_table.setColumnCount(len(WEIGHT_COLUMNS))
        weight_table.verticalHeader().hide()
        weight_table.setHorizontalHeaderLabels([gt(col.display_name) for col in WEIGHT_COLUMNS])
        for idx, col in enumerate(WEIGHT_COLUMNS):
            if col.width is not None:
                weight_table.setColumnWidth(idx, col.width)
            else:
                weight_table.horizontalHeader().setSectionResizeMode(idx, QHeaderView.ResizeMode.Stretch)
        
        # 让表格宽度和高度根据内容自动调整
        def sync_table_size():
            # 同步宽度
            total_width = sum(weight_table.columnWidth(c) for c in range(weight_table.columnCount()))
            weight_table.setFixedWidth(total_width + 2)
            # 同步高度
            total_height = weight_table.horizontalHeader().height()
            for row in range(weight_table.rowCount()):
                total_height += weight_table.rowHeight(row)
            weight_table.setFixedHeight(total_height + 2)
        
        sync_table_size()
        weight_table.horizontalHeader().sectionResized.connect(lambda _, __, ___: sync_table_size())
        weight_table.verticalHeader().sectionResized.connect(lambda _, __, ___: sync_table_size())
        
        # 表格行被选中时触发
        weight_table_row_selected: int = -1
        def on_weight_table_cell_clicked(row: int, column: int):
            nonlocal weight_table_row_selected
            if weight_table_row_selected == row:
                weight_table_row_selected = -1
            else:
                weight_table_row_selected = row
        
        weight_table.cellClicked.connect(on_weight_table_cell_clicked)
        
        # 直接将表格添加到布局中
        table_layout.addWidget(weight_table, stretch=1)
        
        # 弹出表格按钮
        popup_table_btn = PushButton(text=gt('弹出表格'))
        table_layout.addWidget(popup_table_btn)
        
        popup_win: QDialog | None = None
        
        def on_popup_table():
            nonlocal popup_win
            if popup_win is not None:
                popup_win.activateWindow()
                return
            
            popup_win = QDialog(dialog)
            popup_win.setWindowTitle(gt('权重表格编辑'))
            popup_win.setWindowFlags(
                popup_win.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint
            )
            popup_win.setMinimumSize(800, 600)
            popup_win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            
            popup_layout = QVBoxLayout(popup_win)
            popup_layout.setContentsMargins(4, 4, 4, 4)
            
            # 创建新的表格卡片
            popup_table_card = SimpleCardWidget()
            popup_table_layout = QVBoxLayout(popup_table_card)
            popup_table_layout.setContentsMargins(16, 16, 16, 16)
            
            popup_table_title = SubtitleLabel(text=gt('代理人权重列表'))
            popup_table_layout.addWidget(popup_table_title)
            
            # 创建弹出窗口的表格
            popup_weight_table = TableWidget()
            popup_weight_table.setBorderVisible(True)
            popup_weight_table.setBorderRadius(8)
            popup_weight_table.setWordWrap(True)
            popup_weight_table.setColumnCount(len(WEIGHT_COLUMNS))
            popup_weight_table.verticalHeader().hide()
            popup_weight_table.setHorizontalHeaderLabels([gt(col.display_name) for col in WEIGHT_COLUMNS])
            for idx, col in enumerate(WEIGHT_COLUMNS):
                if col.width is not None:
                    popup_weight_table.setColumnWidth(idx, col.width)
                else:
                    popup_weight_table.horizontalHeader().setSectionResizeMode(idx, QHeaderView.ResizeMode.Stretch)
            
            # 同步弹出窗口表格宽度和高度
            def popup_sync_table_size():
                # 同步宽度
                total_width = sum(popup_weight_table.columnWidth(c) for c in range(popup_weight_table.columnCount()))
                popup_weight_table.setFixedWidth(total_width + 2)
                # 同步高度
                total_height = popup_weight_table.horizontalHeader().height()
                for row in range(popup_weight_table.rowCount()):
                    total_height += popup_weight_table.rowHeight(row)
                popup_weight_table.setFixedHeight(total_height + 2)
            
            popup_sync_table_size()
            popup_weight_table.horizontalHeader().sectionResized.connect(lambda _, __, ___: popup_sync_table_size())
            popup_weight_table.verticalHeader().sectionResized.connect(lambda _, __, ___: popup_sync_table_size())
            
            # 复制当前表格数据到弹出窗口表格
            def update_popup_table():
                popup_weight_table.blockSignals(True)
                popup_weight_table.setRowCount(0)
                current_agent = agent_combo.currentText()
                if not current_agent or current_agent not in self.agent_weights:
                    popup_weight_table.blockSignals(False)
                    return
                
                for weight_type, data in self.agent_weights[current_agent].items():
                    row = popup_weight_table.rowCount()
                    popup_weight_table.insertRow(row)
                    
                    # 权重类型
                    type_item = QTableWidgetItem(weight_type)
                    type_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    popup_weight_table.setItem(row, 0, type_item)
                    
                    # 权重值
                    if isinstance(data, dict) and 'weight' in data:
                        weight_item = QTableWidgetItem(str(data['weight']))
                    else:
                        weight_item = QTableWidgetItem('0.5')
                    weight_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    popup_weight_table.setItem(row, 1, weight_item)
                popup_weight_table.blockSignals(False)
                # 同步表格大小
                popup_sync_table_size()
            
            # 绑定弹出窗口表格的单元格变化事件
            def on_popup_weight_table_cell_changed(row: int, column: int):
                current_agent = agent_combo.currentText()
                if not current_agent or current_agent not in self.agent_weights:
                    return
                if row < 0 or row >= popup_weight_table.rowCount():
                    return
                
                weight_type = popup_weight_table.item(row, 0).text()
                if weight_type not in self.agent_weights[current_agent]:
                    return
                
                # 处理权重值变化
                if column == 1:  # 权重值列
                    weight_item = popup_weight_table.item(row, 1)
                    if not weight_item:
                        return
                    
                    text = weight_item.text().strip()
                    try:
                        weight = float(text)
                        # 确保权重值在0-1范围内
                        weight = max(0, min(1, weight))
                        # 更新数据
                        if not isinstance(self.agent_weights[current_agent][weight_type], dict):
                            self.agent_weights[current_agent][weight_type] = {'weight': 0.5, 'enabled': True}
                        self.agent_weights[current_agent][weight_type]['weight'] = weight
                        # 更新显示
                        weight_item.setText(str(weight))
                        # 同步到主表格
                        update_weight_table()
                    except ValueError:
                        # 恢复原来的值
                        if isinstance(self.agent_weights[current_agent][weight_type], dict) and 'weight' in self.agent_weights[current_agent][weight_type]:
                            weight_item.setText(str(self.agent_weights[current_agent][weight_type]['weight']))
                        else:
                            weight_item.setText('0.5')
            
            popup_weight_table.cellChanged.connect(on_popup_weight_table_cell_changed)
            
            # 初始化弹出窗口表格
            update_popup_table()
            
            # 绑定代理选择变化事件
            agent_combo.currentTextChanged.connect(update_popup_table)
            
            popup_table_layout.addWidget(popup_weight_table, stretch=1)
            popup_layout.addWidget(popup_table_card)
            
            def on_popup_closed():
                nonlocal popup_win
                popup_win = None
            
            popup_win.destroyed.connect(on_popup_closed)
            popup_win.show()
        
        popup_table_btn.clicked.connect(on_popup_table)
        
        right_column.add_widget(table_card)
        
        # 绑定事件
        agent_combo.currentTextChanged.connect(lambda: update_weight_table())
        weight_table.cellChanged.connect(on_weight_table_cell_changed)
        
        # 初始化表格
        update_weight_table()
        
        def on_load_weights():
            self._load_weights_data()
            self._update_agent_combo(agent_combo)
            if agent_combo.count() > 0:
                agent_combo.setCurrentIndex(0)
            update_weight_table()
            self.show_info_bar(gt('成功'), gt('权重数据加载完成'), icon=InfoBarIcon.SUCCESS)
        
        def on_save_weights():
            current_agent = agent_combo.currentText()
            if current_agent and current_agent in self.agent_weights:
                # 确保数据格式正确
                for weight_type, data in self.agent_weights[current_agent].items():
                    if not isinstance(data, dict):
                        self.agent_weights[current_agent][weight_type] = {'weight': 0.5}
                    else:
                        if 'weight' not in data:
                            data['weight'] = 0.5
            
            weight_file = os.path.join(self.data_file_path, 'agent_weights.json')
            try:
                os.makedirs(os.path.dirname(weight_file), exist_ok=True)
                with open(weight_file, 'w', encoding='utf-8') as f:
                    json.dump(self.agent_weights, f, ensure_ascii=False, indent=2)
                self.show_info_bar(gt('成功'), gt('权重数据保存完成'), icon=InfoBarIcon.SUCCESS)
            except Exception as e:
                self.show_info_bar(gt('失败'), f"{gt('保存失败')}: {str(e)}", icon=InfoBarIcon.ERROR)
        
        def on_reset_weights():
            current_agent = agent_combo.currentText()
            if current_agent and current_agent in self.agent_weights:
                for weight_type in self.agent_weights[current_agent]:
                    self.agent_weights[current_agent][weight_type] = {
                        'weight': 0.5
                    }
                update_weight_table()
                self.show_info_bar(gt('成功'), gt('权重已重置为默认值'), icon=InfoBarIcon.SUCCESS)
        
        btn_load.clicked.connect(on_load_weights)
        btn_save.clicked.connect(on_save_weights)
        btn_reset.clicked.connect(on_reset_weights)
        
        # 显示窗口
        dialog.exec()
    
    def _load_weights_data(self) -> None:
        """加载权重数据"""
        # 定义权重类型
        weight_types = ['生命值', '攻击力', '防御力', '冲击力', '暴击率', '暴击伤害', '属性伤害加成', '异常掌控', '异常精通', '穿透值', '穿透率', '能量自动回复', '小攻击', '小生命', '小防御']
        
        self.agent_weights = {}
        
        # 从agent_names.json加载代理人列表
        agent_names_file = os.path.join(self.data_file_path, 'agent_names.json')
        if os.path.exists(agent_names_file):
            try:
                with open(agent_names_file, 'r', encoding='utf-8') as f:
                    agent_names = json.load(f)
                    
                    # 遍历代理人列表，检查是否在character_weight目录中有对应json文件
                    for agent_name in agent_names:
                        # 查找对应角色的json文件
                        found = False
                        for file_name in os.listdir(self.character_weight_file_path):
                            if file_name.endswith('.json') and not file_name.startswith('_'):
                                # 从文件名中提取角色code
                                file_code = file_name.replace('.json', '')
                                if file_code == agent_name:
                                    # 找到对应角色的json文件
                                    found = True
                                    file_path = os.path.join(self.character_weight_file_path, file_name)
                                    try:
                                        with open(file_path, 'r', encoding='utf-8') as f:
                                            char_data = json.load(f)
                                            # 初始化权重数据
                                            self.agent_weights[agent_name] = {}
                                            # 从json文件中读取权重数据
                                            weight_data = char_data
                                            for weight_type in weight_types:
                                                # 处理不同的属性名称
                                                weight_key = weight_type
                                                if weight_type == '属性伤害加成':
                                                    # 尝试不同的属性伤害加成名称
                                                    for key in weight_data:
                                                        if '伤害加成' in key:
                                                            weight_key = key
                                                            break
                                                
                                                if weight_key in weight_data:
                                                    # 使用文件中的权重值
                                                    weight_value = weight_data[weight_key]
                                                    # 确保在0-1范围内
                                                    if isinstance(weight_value, (int, float)):
                                                        weight_value = float(weight_value)
                                                        # 如果值大于1，可能是旧的0-100范围，需要转换为0-1
                                                        if weight_value > 1:
                                                            weight_value = weight_value / 100
                                                        weight_value = max(0, min(1, weight_value))
                                                    else:
                                                        weight_value = 0.5
                                                else:
                                                    # 使用默认值
                                                    weight_value = 0.5
                                                self.agent_weights[agent_name][weight_type] = {
                                                    'weight': weight_value
                                                }
                                    except Exception as e:
                                        log.error(f"读取角色文件失败 {file_name}: {e}")
                                    break
                        
                        if not found:
                            log.warning(f"未找到角色 {agent_name} 的权重文件，跳过")
            except Exception as e:
                log.error(f"加载代理人列表失败: {e}")
    
    def _update_agent_combo(self, combo) -> None:
        """更新角色选择下拉框"""
        combo.clear()
        for agent_name in self.agent_weights:
            combo.addItem(agent_name)
    
    def _on_enabled_changed(self, agent_name: str, weight_type: str, checked: bool) -> None:
        """启用状态改变"""
        if agent_name in self.agent_weights and weight_type in self.agent_weights[agent_name]:
            self.agent_weights[agent_name][weight_type]['enabled'] = checked

