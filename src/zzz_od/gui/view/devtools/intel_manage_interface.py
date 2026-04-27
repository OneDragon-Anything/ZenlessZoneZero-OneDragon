import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

# 全局缓存属性映射
_slot_mapping: dict[str, str] | None = None


def _get_slot_mapping() -> dict[str, str]:
    """获取属性映射字典（从 slot_Mapping.json 加载）"""
    global _slot_mapping
    if _slot_mapping is None:
        mapping_path = Path(get_resource_path('src', 'zzz_od', 'game_data', 'slot_Mapping.json'))
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                _slot_mapping = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            from one_dragon.utils.log_utils import log
            log.error(f'属性映射文件加载失败: {e}')
            _slot_mapping = {}
    return _slot_mapping


def _get_weight_order() -> list[str]:
    """从 slot_Mapping.json 获取权重项顺序（按照 slot_Mapping.json 的顺序）"""
    mapping = _get_slot_mapping()
    # 权重项的键顺序（按照 slot_Mapping.json 的顺序）
    weight_key_order = [
        'hp_', 'atk_', 'def_', 'pen_', 'impact',
        'crit_', 'crit_dmg_', 'physical_dmg_', 'ether_dmg_', 'fire_dmg_',
        'ice_dmg_', 'electric_dmg_', 'anomMas_', 'anomProf', 'energyRegen_',
        'atk', 'hp', 'def', 'pen'
    ]
    return [mapping.get(key, key) for key in weight_key_order]


# dmg_type 到元素伤害加成键的映射
_DMG_TYPE_TO_DMG_BONUS_KEY = {
    'ELECTRIC': 'electric_dmg_',
    'ICE': 'ice_dmg_',
    'FIRE': 'fire_dmg_',
    'PHYSICAL': 'physical_dmg_',
    'ETHER': 'ether_dmg_',
}


def _get_dmg_bonus_key(dmg_type: str) -> str:
    """根据 dmg_type 获取对应的元素伤害加成键"""
    return _DMG_TYPE_TO_DMG_BONUS_KEY.get(dmg_type, 'physical_dmg_')


def _get_weight_order_for_agent(dmg_type: str) -> list[str]:
    """根据 agent 的 dmg_type 获取权重项顺序（只包含对应元素的伤害加成）"""
    mapping = _get_slot_mapping()
    
    # 基础属性（不包含元素伤害加成）
    base_key_order = [
        'hp_', 'atk_', 'def_', 'pen_', 'impact',
        'crit_', 'crit_dmg_',
    ]
    
    # 获取对应元素的伤害加成键
    dmg_bonus_key = _get_dmg_bonus_key(dmg_type)
    
    # 其他属性
    other_key_order = [
        'anomMas_', 'anomProf', 'energyRegen_',
        'atk', 'hp', 'def', 'pen'
    ]
    
    # 组合：基础属性 + 对应元素伤害加成 + 其他属性
    weight_key_order = base_key_order + [dmg_bonus_key] + other_key_order
    
    return [mapping.get(key, key) for key in weight_key_order]

from one_dragon.utils.os_utils import get_resource_path
from one_dragon.utils import yaml_utils
from one_dragon.utils.log_utils import log
from PySide6.QtCore import Qt
from zzz_od.game_data.agent import AgentTypeEnum, DmgTypeEnum, RareTypeEnum
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon,
    InfoBarIcon,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SegmentedWidget,
    SimpleCardWidget,
    TableWidget,
    ToolButton,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.application.devtools.intel_manage.intel_manage_app import IntelManageApp


@dataclass
class ColumnMeta:
    """表格列元数据"""
    display_name: str
    attr_name: str | None = None
    parser: Callable[[str], Any] | None = None
    width: int | None = None
    formatter: Callable[[Any], str] | None = None


class WeightConfigDialog(QDialog):
    """权重配置对话框"""

    @classmethod
    def get_weight_options(cls) -> list[str]:
        """从 slot_Mapping.json 获取权重选项列表"""
        return _get_weight_order()

    @property
    def WEIGHT_OPTIONS(self) -> list[str]:
        """权重选项列表（动态从配置文件加载）"""
        return self.get_weight_options()

    def __init__(self, character_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'{character_name} - 权重配置')
        self.setMinimumWidth(400)
        self.setModal(True)

        self.character_name = character_name
        self.weight_values = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        scroll_area = ScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area, stretch=1)

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(8)

        self.weight_inputs = {}
        for option in self.WEIGHT_OPTIONS:
            input_box = QLineEdit()
            input_box.setPlaceholderText('0.0')
            input_box.setValidator(self._create_float_validator())
            self.weight_inputs[option] = input_box
            form_layout.addRow(option, input_box)

        scroll_area.setWidget(form_widget)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)

        cancel_btn = PushButton('取消')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = PushButton('保存')
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        self._load_existing_weights()

    def _create_float_validator(self):
        from PySide6.QtGui import QDoubleValidator
        validator = QDoubleValidator(0.0, 1.0, 2)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        return validator

    def _load_existing_weights(self):
        """加载已有的权重配置"""
        weight_file = Path(get_resource_path('config', 'character_weight.json'))
        if weight_file.exists():
            try:
                with open(weight_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if self.character_name in data:
                        weights = data[self.character_name]
                        for key, value in weights.items():
                            if key in self.weight_inputs:
                                self.weight_inputs[key].setText(str(value))
            except Exception:
                pass

    def _on_save(self):
        """保存权重配置"""
        for option, input_box in self.weight_inputs.items():
            try:
                self.weight_values[option] = float(input_box.text()) if input_box.text() else 0.0
            except ValueError:
                self.weight_values[option] = 0.0

        weight_file = Path(get_resource_path('config', 'character_weight.json'))
        data = {}
        if weight_file.exists():
            try:
                with open(weight_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass

        data[self.character_name] = self.weight_values

        try:
            weight_file.parent.mkdir(parents=True, exist_ok=True)
            with open(weight_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            from one_dragon.utils.log_utils import log
            log.error(f'保存权重配置失败: {e}')
            from qfluentwidgets import MessageBox
            MessageBox.warning(self, '保存失败', f'无法保存权重配置文件:\n{e}')
            return

        self.accept()


class IntelManageInterface(VerticalScrollInterface):
    """信息管理界面，包含三个子页面：代理人信息、驱动盘信息、音擎信息管理"""

    MODE_AGENT = '代理人信息管理'
    MODE_DRIVE_DISK = '驱动盘信息管理'
    MODE_SOUND_ENGINE = '音擎信息管理'

    def __init__(self, ctx: ZContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='intel_manage_interface',
            parent=parent,
            nav_text_cn='信息管理',
            nav_icon=FluentIcon.DOCUMENT,
        )

        self.ctx: ZContext = ctx
        self.mode_stacked: QStackedWidget | None = None
        self.mode_segment: SegmentedWidget | None = None
        self.agent_table_widget: TableWidget | None = None

        # 从 WeightConfigDialog 获取权重选项（动态从配置文件加载）
        self.WEIGHT_OPTIONS = WeightConfigDialog.get_weight_options()

    def get_content_widget(self) -> QWidget:
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        header_card = self._init_header_card()
        main_layout.addWidget(header_card)

        page_content = self._init_page_content()
        main_layout.addWidget(page_content, stretch=1)

        return main_widget

    def _init_header_card(self) -> QWidget:
        """初始化顶部操作栏"""
        card = SimpleCardWidget()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # 左侧：标题区域（图标 + 标题 + 描述）
        title_layout = QHBoxLayout()
        title_layout.setSpacing(12)

        # 图标
        icon_label = QLabel()
        icon_label.setPixmap(FluentIcon.DOCUMENT.icon().pixmap(20, 20))
        
        # 文字区域
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        
        title_label = QLabel('信息管理')
        title_label.setStyleSheet('font-weight: bold; font-size: 14px;')
        
        content_label = QLabel('管理和维护应用数据')
        content_label.setStyleSheet('font-size: 12px; color: #6b7280;')
        
        text_layout.addWidget(title_label)
        text_layout.addWidget(content_label)

        title_layout.addWidget(icon_label)
        title_layout.addLayout(text_layout)
        title_layout.addStretch(1)

        # 搜索框（替换按钮位置）
        self.search_combo = EditableComboBox()
        self.search_combo.setPlaceholderText('输入关键字进行搜索...')
        self.search_combo.setMinimumWidth(250)
        self.search_combo.currentTextChanged.connect(self._filter_table)
        title_layout.addWidget(self.search_combo)

        layout.addLayout(title_layout)
        layout.addStretch(1)

        btn_row = Row(spacing=6)

        self.add_btn = PushButton(text='新增', icon=FluentIcon.ADD)
        self.add_btn.clicked.connect(self._on_add_clicked)
        btn_row.add_widget(self.add_btn)

        # 保存按钮（参考 agent_template_generator_interface.py）
        self.save_btn = PrimaryPushButton(FluentIcon.SAVE, '保存')
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_row.add_widget(self.save_btn)

        layout.addWidget(btn_row)

        return card

    def _init_page_content(self) -> QWidget:
        """初始化页面内容区域"""
        card = SimpleCardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 模式切换 SegmentedWidget
        self.mode_segment = SegmentedWidget()
        self.mode_segment.addItem(
            routeKey=self.MODE_AGENT,
            text=self.MODE_AGENT,
            onClick=lambda: self._apply_mode(self.MODE_AGENT),
        )
        self.mode_segment.addItem(
            routeKey=self.MODE_DRIVE_DISK,
            text=self.MODE_DRIVE_DISK,
            onClick=lambda: self._apply_mode(self.MODE_DRIVE_DISK),
        )
        self.mode_segment.addItem(
            routeKey=self.MODE_SOUND_ENGINE,
            text=self.MODE_SOUND_ENGINE,
            onClick=lambda: self._apply_mode(self.MODE_SOUND_ENGINE),
        )
        layout.addWidget(self.mode_segment)

        # 内容区域 QStackedWidget
        self.mode_stacked = QStackedWidget()
        self.agent_page = self._build_agent_page()
        self.drive_disk_page = self._build_drive_disk_page()
        self.sound_engine_page = self._build_sound_engine_page()

        self.mode_stacked.addWidget(self.agent_page)
        self.mode_stacked.addWidget(self.drive_disk_page)
        self.mode_stacked.addWidget(self.sound_engine_page)
        self.mode_stacked.currentChanged.connect(self._on_stacked_page_changed)

        layout.addWidget(self.mode_stacked, stretch=1)

        # 默认选中第一个页面
        self.mode_segment.setCurrentItem(self.MODE_AGENT)

        # 初始化搜索选项（必须在页面创建和选择之后）
        self._update_search_options()

        return card

    def _build_agent_page(self) -> QWidget:
        """构建代理人信息管理页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 加载代理人数据
        self.agent_data = self._load_agent_data()

        # 代理人信息卡片
        self.agent_info_card = SimpleCardWidget()
        # 修改为水平布局，让两个表格同行放置
        self.agent_info_layout = QHBoxLayout(self.agent_info_card)
        self.agent_info_layout.setContentsMargins(8, 8, 8, 8)
        self.agent_info_layout.setSpacing(12)

        # 左侧列：比较公式配置 + 基础信息表格
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # 比较公式配置区域
        formula_card = SimpleCardWidget()
        formula_card.setStyleSheet('border: none;')  # 使用样式表隐藏卡片边框
        formula_layout = QVBoxLayout(formula_card)
        formula_layout.setContentsMargins(4, 4, 4, 4)  # 进一步减小内边距
        formula_layout.setSpacing(4)  # 进一步减小控件间距

        # 定义排除的小属性
        EXCLUDED_OPTIONS = {'穿透值', '小防御', '小生命', '小攻击'}
        # 可用的权重选项（排除小属性，添加'无'选项）
        self.available_weight_options = [
            '无'  # '无'选项不受联动筛选影响，可以重复使用
        ] + [opt for opt in self.WEIGHT_OPTIONS if opt not in EXCLUDED_OPTIONS]

        # 4行4列表格
        self.formula_table = TableWidget()
        self.formula_table.setBorderVisible(True)
        self.formula_table.setBorderRadius(8)
        self.formula_table.setColumnCount(4)
        self.formula_table.setRowCount(4)
        
        # 设置表头
        headers = ['优先级', '可选词条1', '可选词条2', '可选词条3']
        self.formula_table.setHorizontalHeaderLabels(headers)
        
        # 设置列宽
        self.formula_table.setColumnWidth(0, 70)  # 优先级列
        self.formula_table.setColumnWidth(1, 120)  # 可选词条1
        self.formula_table.setColumnWidth(2, 120)  # 可选词条2
        self.formula_table.setColumnWidth(3, 120)  # 可选词条3
        
        # 隐藏默认的行号列（垂直表头）
        self.formula_table.verticalHeader().setVisible(False)
        
        # 初始化表格内容（所有值初始化为'无'）
        self.formula_combos = []  # 存储所有下拉框，结构: [[row0_combo1, row0_combo2, row0_combo3], ...]
        default_values = [
            ['无', '无', '无'],
            ['无', '无', '无'],
            ['无', '无', '无'],
            ['无', '无', '无']
        ]
        
        for row in range(4):
            row_combos = []
            
            # 优先级标签
            priority_item = QTableWidgetItem(f'{row + 1}')
            priority_item.setFlags(priority_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            priority_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.formula_table.setItem(row, 0, priority_item)
            
            # 三个可选词条下拉框
            for col in range(3):
                combo = EditableComboBox()
                combo.addItems(self.available_weight_options)
                combo.setCurrentText(default_values[row][col])
                # 绑定去重信号（使用 functools.partial 确保正确捕获循环变量）
                combo.currentTextChanged.connect(partial(self._on_formula_combo_changed, row, col))
                self.formula_table.setCellWidget(row, col + 1, combo)
                row_combos.append(combo)
            
            self.formula_combos.append(row_combos)
    
        # 将表格添加到布局（关键步骤！之前缺失）
        formula_layout.addWidget(self.formula_table)
    
        # 一键生成按钮（使用 PrimaryPushButton，与 agent_template_generator_interface.py 保持一致）
        self.btn_generate_weight = PrimaryPushButton(FluentIcon.PLAY, '一键生成权重')
        self.btn_generate_weight.clicked.connect(self._on_generate_weight_clicked)
        formula_layout.addWidget(self.btn_generate_weight)

        left_layout.addWidget(formula_card)
        
        # 音擎设定表格（优化高度，减少留白）
        self.sound_engine_table = TableWidget()
        self.sound_engine_table.setBorderVisible(True)
        self.sound_engine_table.setBorderRadius(8)
        self.sound_engine_table.setColumnCount(3)
        self.sound_engine_table.setRowCount(1)
        
        # 设置表头
        headers = ['最优音擎设定', '次优音擎设定', '第三优音擎设定']
        self.sound_engine_table.setHorizontalHeaderLabels(headers)
        
        # 设置列宽，三列均匀分配
        for i in range(3):
            self.sound_engine_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        
        # 优化表格高度：设置紧凑布局，减少留白
        self.sound_engine_table.setRowHeight(0, 26)  # 紧凑行高
        self.sound_engine_table.verticalHeader().setVisible(False)  # 隐藏垂直表头
        self.sound_engine_table.horizontalHeader().setFixedHeight(24)  # 减小水平表头高度
        self.sound_engine_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # 高度固定
        self.sound_engine_table.setFixedHeight(56)  # 设置固定总高度（表头24 + 行26 + 边框等）
        
        left_layout.addWidget(self.sound_engine_table)

        # 基础信息表格
        self.basic_info_table = TableWidget()
        self.basic_info_table.setBorderVisible(True)
        self.basic_info_table.setBorderRadius(8)
        self.basic_info_table.setWordWrap(True)
        self.basic_info_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.basic_info_table.verticalHeader().setVisible(False)  # 隐藏垂直表头列
        self.basic_info_table.horizontalHeader().setVisible(False)  # 隐藏水平表头（列名行）
        left_layout.addWidget(self.basic_info_table)

        # 权重配置表格（右侧卡片）
        self.weight_table = TableWidget()
        self.weight_table.setBorderVisible(True)
        self.weight_table.setBorderRadius(8)
        self.weight_table.setWordWrap(True)
        self.weight_table.setMinimumWidth(400)  # 设置最小宽度，允许自适应扩展
        self.weight_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.agent_info_layout.addWidget(left_column)
        self.agent_info_layout.addWidget(self.weight_table)

        layout.addWidget(self.agent_info_card)

        return widget
    
    def _on_formula_combo_changed(self, row: int, col: int, text: str) -> None:
        """当公式下拉框内容改变时，更新其他下拉框的选项（去重机制）"""
        # 如果选择的是'无'，不需要进行去重处理
        if text == '无':
            return
        
        # 在整个表格范围内进行去重
        # 收集整个表格中除当前单元格外已选择的非'无'词条
        table_selected = set()
        for r in range(4):
            for c in range(3):
                if r == row and c == col:
                    continue  # 跳过当前正在修改的单元格
                item = self.formula_combos[r][c].currentText()
                if item != '无':
                    table_selected.add(item)
        
        # 如果新选择的词条与表格中其他单元格重复，需要将所有重复的单元格重置为'无'
        if text in table_selected:
            for r in range(4):
                for c in range(3):
                    if r == row and c == col:
                        continue  # 跳过当前正在修改的单元格
                    combo = self.formula_combos[r][c]
                    if combo.currentText() == text:
                        combo.blockSignals(True)
                        combo.setCurrentText('无')
                        combo.blockSignals(False)
        # 新选择的词条不重复时，不需要更新其他下拉框，保持原有选择不变

    def _set_enum_combo_value(self, combo_box, enum_class, enum_value: str, fallback_value: str) -> None:
        """设置下拉框的枚举值（安全处理，防止枚举转换异常）"""
        if enum_value:
            try:
                if hasattr(enum_class, 'from_name') and callable(getattr(enum_class, 'from_name')):
                    combo_box.setCurrentText(enum_class.from_name(enum_value).value)
                else:
                    combo_box.setCurrentText(fallback_value)
            except (AttributeError, ValueError):
                combo_box.setCurrentText(fallback_value)
        else:
            combo_box.setCurrentText(fallback_value)

    def _load_agent_data(self) -> dict[str, dict]:
        """加载所有代理人的yml数据（委托给App层）"""
        app = self._get_intel_manage_app()
        if app:
            return app.load_agent_data()
        return {}

    def _get_intel_manage_app(self) -> IntelManageApp | None:
        """获取信息管理应用实例（通过应用实例管理机制）"""
        from zzz_od.application.devtools.intel_manage import intel_manage_const
        try:
            return self.ctx.run_context.get_application(
                app_id=intel_manage_const.APP_ID,
                instance_idx=self.ctx.current_instance_idx,
                group_id=''
            )
        except Exception:
            from one_dragon.utils.log_utils import log
            log.error(f"获取信息管理应用实例失败")
            return None

    def _on_agent_selected(self, agent_name: str) -> None:
        """选择代理人时更新显示"""
        if not agent_name or agent_name not in self.agent_data:
            # 清空表格
            self._clear_table(self.basic_info_table)
            self._clear_table(self.weight_table)
            return

        agent_info = self.agent_data[agent_name]

        # 重置权重优先级表格（切换代理人时重置）
        self._reset_formula_table()

        # 显示基础信息
        self._show_basic_info(agent_info)

        # 显示权重配置
        self._show_weight_info(agent_info)

    def _reset_formula_table(self) -> None:
        """重置权重优先级表格的所有值为'无'"""
        for row in range(4):
            for col in range(3):
                combo = self.formula_combos[row][col]
                combo.blockSignals(True)
                combo.setCurrentText('无')
                combo.blockSignals(False)

    def _clear_table(self, table: TableWidget) -> None:
        """清空表格"""
        table.setRowCount(0)
        table.setColumnCount(0)

    def _show_basic_info(self, agent_info: dict) -> None:
        """显示代理人基础信息"""
        self.basic_info_table.clear()
        self.basic_info_table.setColumnCount(2)
        self.basic_info_table.setRowCount(5)

        headers = ['属性', '值']
        self.basic_info_table.setHorizontalHeaderLabels(headers)

        # 创建下拉框组件（使用 ComboBox，不可编辑）
        # 角色类型下拉框
        self.agent_type_combo = ComboBox()
        agent_type_items = [ConfigItem(enum.value, enum.name) for enum in AgentTypeEnum]
        self.agent_type_combo.set_items(agent_type_items)

        # 属性类型下拉框
        self.dmg_type_combo = ComboBox()
        dmg_type_items = [ConfigItem(enum.value, enum.name) for enum in DmgTypeEnum]
        self.dmg_type_combo.set_items(dmg_type_items)

        # 稀有度下拉框
        self.rare_type_combo = ComboBox()
        rare_type_items = [ConfigItem(enum.value, enum.name) for enum in RareTypeEnum]
        self.rare_type_combo.set_items(rare_type_items)

        # 设置当前值（优先使用英文标识，回退到中文显示值）
        self._set_enum_combo_value(self.agent_type_combo, AgentTypeEnum, 
                                   agent_info.get('agent_type', ''), 
                                   agent_info.get('agent_type_cn', ''))
        self._set_enum_combo_value(self.dmg_type_combo, DmgTypeEnum, 
                                   agent_info.get('dmg_type', ''), 
                                   agent_info.get('dmg_type_cn', ''))
        self._set_enum_combo_value(self.rare_type_combo, RareTypeEnum, 
                                   agent_info.get('rare_type', ''), 
                                   agent_info.get('rare_type', ''))

        # 设置表格内容
        # 代理人名称
        item_label = QTableWidgetItem('代理人名称')
        item_label.setFlags(item_label.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.basic_info_table.setItem(0, 0, item_label)
        item_value = QTableWidgetItem(agent_info.get('agent_name', ''))
        self.basic_info_table.setItem(0, 1, item_value)

        # 角色类型（下拉框）
        item_label = QTableWidgetItem('角色类型')
        item_label.setFlags(item_label.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.basic_info_table.setItem(1, 0, item_label)
        self.basic_info_table.setCellWidget(1, 1, self.agent_type_combo)

        # 属性类型（下拉框）
        item_label = QTableWidgetItem('属性类型')
        item_label.setFlags(item_label.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.basic_info_table.setItem(2, 0, item_label)
        self.basic_info_table.setCellWidget(2, 1, self.dmg_type_combo)

        # 稀有度（下拉框）
        item_label = QTableWidgetItem('稀有度')
        item_label.setFlags(item_label.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.basic_info_table.setItem(3, 0, item_label)
        self.basic_info_table.setCellWidget(3, 1, self.rare_type_combo)

        # code
        item_label = QTableWidgetItem('code')
        item_label.setFlags(item_label.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.basic_info_table.setItem(4, 0, item_label)
        item_value = QTableWidgetItem(agent_info.get('code', ''))
        self.basic_info_table.setItem(4, 1, item_value)

        # 设置列宽：第一列固定宽度，第二列拉伸填充剩余空间
        self.basic_info_table.setColumnWidth(0, 120)
        self.basic_info_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.basic_info_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    def _show_weight_info(self, agent_info: dict) -> None:
        """显示代理人权重配置（显示所有 slot_Mapping.json 中的选项）"""
        weight_data = agent_info.get('weight', {})
        
        # 获取所有 slot_Mapping.json 中的权重选项（不根据属性类型过滤）
        weight_order = _get_weight_order()
        
        self.weight_table.clear()
        self.weight_table.setColumnCount(2)
        self.weight_table.setRowCount(len(weight_order))
        
        # 显示表头
        headers = ['属性', '权重值']
        self.weight_table.setHorizontalHeaderLabels(headers)
        
        # 遍历所有权重项
        for row_idx, attr_name in enumerate(weight_order):
            # 属性列
            item_label = QTableWidgetItem(attr_name)
            item_label.setFlags(item_label.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.weight_table.setItem(row_idx, 0, item_label)
            
            # 权重值列（未配置的显示"未配置权重"）
            if attr_name in weight_data:
                value = str(weight_data[attr_name])
            else:
                value = '未配置权重'
            
            item_value = QTableWidgetItem(value)
            if attr_name in weight_data:
                item_value.setFlags(item_value.flags() | Qt.ItemFlag.ItemIsEditable)
            else:
                item_value.setFlags(item_value.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item_value.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.weight_table.setItem(row_idx, 1, item_value)
        
        # 设置列宽：第一列固定宽度，第二列拉伸填充剩余空间
        self.weight_table.setColumnWidth(0, 150)
        self.weight_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.weight_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    def _on_generate_weight_clicked(self) -> None:
        """一键生成权重按钮点击事件"""
        # 获取当前选中的代理人
        agent_name = self.search_combo.currentText()
        if not agent_name or agent_name not in self.agent_data:
            self.show_info_bar('提示', '请先选择一个代理人', icon=InfoBarIcon.WARNING)
            return

        # 获取表格中的所有词条配置
        # 优先级权重：1 -> 1.0, 2 -> 0.75, 3 -> 0.5, 4 -> 0.25
        def get_weight_by_priority(priority: int) -> float:
            return max(0.25, 1.0 - (priority - 1) * 0.25)
        
        # 收集所有配置的词条及其优先级
        attr_priority_map = {}
        formula_description = []
        
        for row in range(4):
            priority = row + 1
            row_weight = get_weight_by_priority(priority)
            
            for col in range(3):
                combo = self.formula_combos[row][col]
                attr = combo.currentText()
                
                if attr != '无':
                    # 同一优先级内的词条都获得该优先级的完整分数
                    attr_priority_map[attr] = row_weight
            
            # 收集当前行的非空词条用于描述
            row_items = [self.formula_combos[row][col].currentText() for col in range(3) 
                        if self.formula_combos[row][col].currentText() != '无']
            if row_items:
                formula_description.append(f"优先级{priority}: {', '.join(row_items)}")
        
        # 根据优先级分配权重
        generated_weight = {}
        for attr in self.WEIGHT_OPTIONS:
            generated_weight[attr] = attr_priority_map.get(attr, 0)
        
        # 小属性权重为对应大属性的1/3（保留两位小数）
        small_to_large_map = {
            '小攻击': '攻击力',
            '小生命': '生命值',
            '小防御': '防御力',
            '穿透值': '穿透率'
        }
        for small_attr, large_attr in small_to_large_map.items():
            if large_attr in generated_weight and generated_weight[large_attr] > 0:
                generated_weight[small_attr] = round(generated_weight[large_attr] / 3, 2)

        # 更新代理人数据
        self.agent_data[agent_name]['weight'] = generated_weight

        # 更新表格显示
        self._on_agent_selected(agent_name)

        # 显示成功提示
        formula_str = '; '.join(formula_description) if formula_description else '未配置任何词条'
        self.show_info_bar('成功', 
            f'权重已按优先级公式自动分配:\n{formula_str}', 
            icon=InfoBarIcon.SUCCESS)

    def _on_weight_config_clicked(self, character_name: str) -> None:
        """点击权重配置按钮"""
        dialog = WeightConfigDialog(character_name, self.window())
        dialog.exec()

    def _create_new_agent(self) -> None:
        """创建一个新的代理人信息"""
        # 生成唯一的代理人名称
        new_name = '新代理人'
        counter = 1
        while new_name in self.agent_data:
            new_name = f'新代理人{counter}'
            counter += 1

        # 从 slot_Mapping.json 获取所有权重项，并初始化为 0
        weight_order = _get_weight_order()
        default_weight = {key: 0 for key in weight_order}
        
        # 设置默认值
        default_weight['攻击力'] = 0.5
        default_weight['暴击率'] = 0.25
        default_weight['暴击伤害'] = 0.25
        default_weight['能量自动回复'] = 0.5
        default_weight['小攻击'] = 0.33

        # 创建新代理人数据
        new_agent = {
            'agent_name': new_name,
            'agent_type': 'ATTACK',
            'agent_type_cn': '强攻',
            'dmg_type': 'PHYSICAL',
            'dmg_type_cn': '物理',
            'rare_type': 'A',
            'weight': default_weight
        }

        # 添加到代理人数据
        self.agent_data[new_name] = new_agent

        # 更新搜索下拉框选项
        self._update_search_options()

        # 在搜索框中选中新创建的代理人
        self.search_combo.blockSignals(True)
        self.search_combo.setCurrentText(new_name)
        self.search_combo.blockSignals(False)

        # 显示新代理人信息
        self._on_agent_selected(new_name)

    def _build_drive_disk_page(self) -> QWidget:
        """构建驱动盘信息管理页面"""
        # 从 yml 文件中读取驱动盘数据
        drive_disk_data = self._load_drive_disk_data()
        
        return self._build_table_page(
            columns=[
                ColumnMeta('ID', 'id', lambda x: int(x) if x else 0),
                ColumnMeta('驱动盘名称', 'set_name', lambda x: x),
                ColumnMeta('任务类型', 'mission_type_name', lambda x: x),
                ColumnMeta('code', 'code', lambda x: x),
            ],
            data=drive_disk_data
        )
    
    def _load_drive_disk_data(self) -> list[dict]:
        """加载驱动盘数据"""
        import os
        
        def parse_disk_info(disk_info: dict) -> dict:
            return {
                'id': 0,
                'set_name': disk_info.get('set_name', ''),
                'mission_type_name': disk_info.get('mission_type_name', ''),
                'code': disk_info.get('code', ''),
            }
        
        data = self._load_yml_data(parse_disk_info, 'assets', 'game_data', 'drive_disk')
        for idx, item in enumerate(data):
            item['id'] = idx + 1
        return data

    def _build_sound_engine_page(self) -> QWidget:
        """构建音擎信息管理页面"""
        # 从 yml 文件中读取音擎数据
        engine_weapon_data = self._load_engine_weapon_data()
        
        return self._build_table_page(
            columns=[
                ColumnMeta('ID', 'id', lambda x: int(x) if x else 0),
                ColumnMeta('音擎名称', 'weapon_name', lambda x: x),
                ColumnMeta('稀有度', 'rarity', lambda x: x),
                ColumnMeta('code', 'code', lambda x: x),
            ],
            data=engine_weapon_data
        )
    
    def _load_engine_weapon_data(self) -> list[dict]:
        """加载音擎数据"""
        import os
        
        def parse_weapon_info(weapon_info: dict) -> dict:
            return {
                'id': 0,
                'weapon_name': weapon_info.get('weapon_name', ''),
                'rarity': weapon_info.get('rarity', ''),
                'code': weapon_info.get('code', ''),
            }
        
        data = self._load_yml_data(parse_weapon_info, 'assets', 'game_data', 'engine_weapon')
        for idx, item in enumerate(data):
            item['id'] = idx + 1
        return data
    
    def _load_yml_data(self, parser: callable, *path_parts: str) -> list[dict]:
        """
        通用的 YML 数据加载方法
        :param path_parts: 资源路径的各个部分
        :param parser: 数据解析函数，将 YML 数据转换为字典
        :return: 解析后的数据列表
        """
        import os
        
        data = []
        data_dir = get_resource_path(*path_parts)
        
        if not os.path.exists(data_dir):
            log.warning(f"Data directory not found: {data_dir}")
            return data
        
        for filename in sorted(os.listdir(data_dir)):
            if not filename.endswith('.yml'):
                continue
            
            file_path = os.path.join(data_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    yml_data = yaml_utils.safe_load(f)
                    if yml_data:
                        parsed = parser(yml_data)
                        data.append(parsed)
            except IOError as e:
                log.error(f"Failed to read file {file_path}: {e}")
            except Exception as e:
                log.error(f"Error parsing file {file_path}: {e}")
        
        log.info(f"Loaded {len(data)} items from {data_dir}")
        return data

    def _build_table_page(self, columns: list[ColumnMeta], data: list[dict]) -> QWidget:
        """构建通用表格页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        scroll_area = ScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        table_widget = TableWidget()
        table_widget.setBorderVisible(True)
        table_widget.setBorderRadius(8)
        table_widget.setWordWrap(True)
        table_widget.setColumnCount(len(columns))
        table_widget.verticalHeader().hide()

        headers = [col.display_name for col in columns]
        table_widget.setHorizontalHeaderLabels(headers)

        for idx, col in enumerate(columns):
            if col.width is not None:
                table_widget.setColumnWidth(idx, col.width)

        for row_idx, row_data in enumerate(data):
            table_widget.insertRow(row_idx)
            for col_idx, col in enumerate(columns):
                if col.display_name == '操作':
                    action_btn = ToolButton(FluentIcon.EDIT)
                    action_btn.setToolTip('编辑')
                    table_widget.setCellWidget(row_idx, col_idx, action_btn)
                else:
                    value = row_data.get(col.attr_name, '')
                    if col.formatter:
                        value = col.formatter(value)
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                    table_widget.setItem(row_idx, col_idx, item)

        # 自动调整列宽以适应内容
        table_widget.resizeColumnsToContents()
        
        scroll_area.setWidget(table_widget)
        layout.addWidget(scroll_area)

        return widget

    def _apply_mode(self, mode: str) -> None:
        """应用模式切换"""
        if mode == self.MODE_AGENT:
            self.mode_stacked.setCurrentWidget(self.agent_page)
        elif mode == self.MODE_DRIVE_DISK:
            self.mode_stacked.setCurrentWidget(self.drive_disk_page)
        elif mode == self.MODE_SOUND_ENGINE:
            self.mode_stacked.setCurrentWidget(self.sound_engine_page)

    def _on_stacked_page_changed(self, index: int) -> None:
        """切换页面时，调整 QStackedWidget 高度并更新搜索选项"""
        for i in range(self.mode_stacked.count()):
            w = self.mode_stacked.widget(i)
            if i == index:
                w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            else:
                w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.mode_stacked.adjustSize()

        # 页面切换时更新搜索选项
        self._update_search_options()
        # 清空搜索框内容但保留选项
        self.search_combo.blockSignals(True)
        self.search_combo.setCurrentIndex(-1)
        self.search_combo.blockSignals(False)

    def _on_add_clicked(self) -> None:
        """添加新代理人信息或新行"""
        current_page = self.mode_stacked.currentWidget()
        
        # 如果是代理人页面，创建一个新的代理人信息
        if current_page == self.agent_page:
            self._create_new_agent()
            return
        
        if current_page is not None:
            table_widget = current_page.findChild(TableWidget)
            if table_widget is not None:
                row_idx = table_widget.rowCount()
                table_widget.insertRow(row_idx)

                if self.mode_stacked.currentIndex() == 0:
                    columns = [
                        ColumnMeta('操作', width=80),
                        ColumnMeta('权重配置', width=100),
                        ColumnMeta('ID', 'id'),
                        ColumnMeta('代理人名称', 'name'),
                        ColumnMeta('属性', 'attribute'),
                        ColumnMeta('等级', 'level'),
                        ColumnMeta('好感度', 'affection'),
                        ColumnMeta('描述', 'description'),
                    ]
                    for col_idx, col in enumerate(columns):
                        if col.display_name == '操作':
                            action_btn = ToolButton(FluentIcon.EDIT)
                            action_btn.setToolTip('编辑')
                            table_widget.setCellWidget(row_idx, col_idx, action_btn)
                        elif col.display_name == '权重配置':
                            weight_btn = PushButton('配置')
                            weight_btn.setFixedWidth(80)
                            weight_btn.clicked.connect(
                                lambda _, idx=row_idx: self._on_new_agent_weight_config(idx)
                            )
                            table_widget.setCellWidget(row_idx, col_idx, weight_btn)
                        else:
                            item = QTableWidgetItem('')
                            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                            table_widget.setItem(row_idx, col_idx, item)
                elif self.mode_stacked.currentIndex() == 1:
                    # 驱动盘页面 - 与实际表格结构一致
                    columns = [
                        ColumnMeta('ID', 'id'),
                        ColumnMeta('驱动盘名称', 'set_name'),
                        ColumnMeta('任务类型', 'mission_type_name'),
                        ColumnMeta('code', 'code'),
                    ]
                    for col_idx, col in enumerate(columns):
                        item = QTableWidgetItem('')
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                        table_widget.setItem(row_idx, col_idx, item)
                else:
                    # 音擎页面 - 与实际表格结构一致
                    columns = [
                        ColumnMeta('ID', 'id'),
                        ColumnMeta('音擎名称', 'weapon_name'),
                        ColumnMeta('稀有度', 'rarity'),
                        ColumnMeta('code', 'code'),
                    ]
                    for col_idx, col in enumerate(columns):
                        item = QTableWidgetItem('')
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                        table_widget.setItem(row_idx, col_idx, item)

    def _on_new_agent_weight_config(self, row_idx: int) -> None:
        """新代理人的权重配置"""
        if self.agent_table_widget is not None:
            name_item = self.agent_table_widget.item(row_idx, 3)
            name = name_item.text() if name_item else '新代理人'
            dialog = WeightConfigDialog(name, self.window())
            dialog.exec()

    def _on_delete_clicked(self) -> None:
        """删除选中行"""
        current_page = self.mode_stacked.currentWidget()
        if current_page is not None:
            table_widget = current_page.findChild(TableWidget)
            if table_widget is not None:
                selected_rows = set()
                for item in table_widget.selectedItems():
                    selected_rows.add(item.row())

                for row_idx in sorted(selected_rows, reverse=True):
                    table_widget.removeRow(row_idx)

    def _on_refresh_clicked(self) -> None:
        """刷新表格数据"""
        current_index = self.mode_stacked.currentIndex()
        self.mode_stacked.removeWidget(self.mode_stacked.currentWidget())

        if current_index == 0:
            self.agent_page = self._build_agent_page()
            self.mode_stacked.insertWidget(0, self.agent_page)
        elif current_index == 1:
            self.drive_disk_page = self._build_drive_disk_page()
            self.mode_stacked.insertWidget(1, self.drive_disk_page)
        else:
            self.sound_engine_page = self._build_sound_engine_page()
            self.mode_stacked.insertWidget(2, self.sound_engine_page)

        self.mode_stacked.setCurrentIndex(current_index)

    def _update_search_options(self) -> None:
        """更新搜索下拉框的选项"""
        current_page = self.mode_stacked.currentWidget()
        if current_page is None:
            return

        # 如果是代理人页面，显示代理人列表
        if current_page == self.agent_page:
            if hasattr(self, 'agent_data'):
                items = [ConfigItem(name) for name in sorted(self.agent_data.keys())]
                self.search_combo.set_items(items)
            return
        
        # 如果是驱动盘页面，显示驱动盘名称列表
        if current_page == self.drive_disk_page:
            drive_disk_data = self._load_drive_disk_data()
            items = [ConfigItem(disk['set_name']) for disk in drive_disk_data]
            self.search_combo.set_items(items)
            return
        
        # 如果是音擎页面，显示音擎名称列表
        if current_page == self.sound_engine_page:
            engine_weapon_data = self._load_engine_weapon_data()
            items = [ConfigItem(weapon['weapon_name']) for weapon in engine_weapon_data]
            self.search_combo.set_items(items)
            return

        table_widget = current_page.findChild(TableWidget)
        if table_widget is None:
            return

        # 收集所有表格中的文本作为搜索选项（其他页面）
        options = []
        for row_idx in range(table_widget.rowCount()):
            row_texts = []
            for col_idx in range(table_widget.columnCount()):
                item = table_widget.item(row_idx, col_idx)
                if item is not None and item.text():
                    row_texts.append(item.text())
            if row_texts:
                # 使用第一列非操作列的文本作为选项显示
                display_text = next((t for t in row_texts if t != '配置'), row_texts[0])
                options.append(ConfigItem(display_text))

        self.search_combo.set_items(options)

    def _filter_table(self, text: str) -> None:
        """根据搜索关键字过滤表格内容或选择代理人"""
        current_page = self.mode_stacked.currentWidget()
        if current_page is None:
            return

        # 如果是代理人页面，显示选中的代理人信息
        if current_page == self.agent_page:
            if hasattr(self, '_on_agent_selected'):
                self._on_agent_selected(text)
            return

        table_widget = current_page.findChild(TableWidget)
        if table_widget is None:
            return

        for row_idx in range(table_widget.rowCount()):
            match = False
            for col_idx in range(table_widget.columnCount()):
                item = table_widget.item(row_idx, col_idx)
                if item is not None and text.lower() in item.text().lower():
                    match = True
                    break

                # 检查单元格内的按钮文本（如权重配置按钮）
                cell_widget = table_widget.cellWidget(row_idx, col_idx)
                if cell_widget is not None:
                    if hasattr(cell_widget, 'text'):
                        btn_text = cell_widget.text()
                        if btn_text and text.lower() in btn_text.lower():
                            match = True
                            break

            table_widget.showRow(row_idx) if match else table_widget.hideRow(row_idx)

    def on_interface_shown(self) -> None:
        """界面显示时触发"""
        VerticalScrollInterface.on_interface_shown(self)
        # 初始化搜索选项
        self._update_search_options()

    def _on_save_clicked(self) -> None:
        """保存代理人数据到yml文件"""
        current_page = self.mode_stacked.currentWidget()
        if current_page != self.agent_page:
            self.show_info_bar('提示', '请切换到代理人信息管理页面', icon=InfoBarIcon.WARNING)
            return

        agent_name = self.search_combo.currentText()
        if not agent_name or agent_name not in self.agent_data:
            self.show_info_bar('提示', '请先选择一个代理人', icon=InfoBarIcon.WARNING)
            return

        # 读取基础信息表格数据（UI层职责：数据收集）
        agent_data = {}
        
        # 从下拉框获取角色类型、属性类型和稀有度（使用 currentData() 获取英文标识）
        if hasattr(self, 'agent_type_combo'):
            agent_data['agent_type'] = self.agent_type_combo.currentData() or ''
        if hasattr(self, 'dmg_type_combo'):
            agent_data['dmg_type'] = self.dmg_type_combo.currentData() or ''
        if hasattr(self, 'rare_type_combo'):
            agent_data['rare_type'] = self.rare_type_combo.currentData() or ''
        
        # 从表格获取其他字段
        if self.basic_info_table.rowCount() > 0:
            for row_idx in range(self.basic_info_table.rowCount()):
                key_item = self.basic_info_table.item(row_idx, 0)
                value_item = self.basic_info_table.item(row_idx, 1)
                if key_item and value_item:
                    key = key_item.text()
                    value = value_item.text()
                    if key == '代理人名称':
                        agent_data['agent_name'] = value
                    elif key == 'code':
                        agent_data['code'] = value

        # 读取权重配置表格数据
        weight_data = {}
        if self.weight_table.rowCount() > 0:
            for row_idx in range(self.weight_table.rowCount()):
                attr_item = self.weight_table.item(row_idx, 0)
                value_item = self.weight_table.item(row_idx, 1)
                if attr_item and value_item:
                    attr_name = attr_item.text()
                    value = value_item.text()
                    if value and value != '未配置权重':
                        try:
                            weight_data[attr_name] = float(value)
                        except ValueError:
                            pass

        if weight_data:
            agent_data['weight'] = weight_data

        # 更新内存中的代理人数据（合并完整数据）
        merged_agent_data = dict(self.agent_data[agent_name])
        merged_agent_data.update(agent_data)
        self.agent_data[agent_name] = merged_agent_data

        # 调用 App 层保存数据（业务逻辑委托给 App 层）
        app = self._get_intel_manage_app()
        if app:
            success = app.save_agent_data(agent_name, merged_agent_data)
            if success:
                self.show_info_bar('成功', '代理人数据已保存', icon=InfoBarIcon.SUCCESS)
                
                # 如果修改了 dmg_type，更新 WEIGHT_OPTIONS 和比较公式下拉框
                if 'dmg_type' in agent_data:
                    self._on_agent_selected(agent_name)
            else:
                self.show_info_bar('失败', '保存失败', icon=InfoBarIcon.ERROR)
        else:
            self.show_info_bar('失败', '无法获取应用实例', icon=InfoBarIcon.ERROR)
