from typing import Optional, List

from one_dragon.utils.log_utils import log
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiLineSettingCard
from zzz_od.application.drive_disk_enhance.drive_disk_enhance_const import APP_ID
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext

from PySide6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QLabel, QCheckBox
from qfluentwidgets import SimpleCardWidget, FluentIcon


class DriveDiskEnhanceInterface(AppRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        self.app: Optional[ZApplication] = None
        self.checkboxes: List[QCheckBox] = []
        self.character_combo: Optional[ComboBox] = None
        self.disk_combos: List[ComboBox] = []
        self.drive_disk_names: List[str] = []

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=APP_ID,
            object_name='drive_disk_enhance_interface',
            nav_text_cn='驱动盘强化',
            parent=parent,
        )

    def get_widget_at_top(self):
        """创建界面顶部的UI组件"""
        from PySide6.QtWidgets import QVBoxLayout, QWidget
        import subprocess
        import json
        import os
        import yaml

        content = Row()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        content.h_layout.addLayout(left_layout)
        content.h_layout.addLayout(right_layout)

        self.help_opt = HelpCard(
            title='使用说明',
            content='自动强化驱动盘功能\n从驱动盘详细页开始，自动进行强化操作\n注意：请确保游戏分辨率为 1920x1080'
        )
        self.help_opt.setFixedHeight(120)  # 设置使用说明卡片高度为120px
        left_layout.addWidget(self.help_opt)

        # 添加10px垂直间距
        left_layout.addSpacing(10)

        # 角色选择卡片
        character_card = SimpleCardWidget()
        character_card.setFixedHeight(50)  # 设置角色选择卡片高度为50px
        character_layout = QHBoxLayout(character_card)
        character_label = QLabel('选择角色:')
        character_layout.addWidget(character_label)
        
        self.character_combo = ComboBox()
        
        # 获取角色列表
        try:
            # 运行JavaScript脚本获取角色列表
            script_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'application', 'drive_disk_enhance', 'process_scanned_discs.js')
            result = subprocess.run(
                ['node', script_path, '--list-characters'],
                capture_output=True,
                text=True,
                encoding='utf-8',  # 指定编码为UTF-8
                timeout=5
            )
            if result.returncode == 0 and result.stdout:
                try:
                    characters = json.loads(result.stdout)
                    self.character_combo.addItems(characters)
                except json.JSONDecodeError as e:
                    print(f"解析角色列表失败: {e}")
                    # 默认角色列表
                    default_characters = ['露西亚', '安比', '安东', '本', '比利', '科琳', '艾伦', '格蕾丝', '莱卡恩', '露西', '猫又', '妮可', '派珀', 'rina', '士兵11', '朱雀', '朱元']
                    self.character_combo.addItems(default_characters)
            else:
                # 默认角色列表
                default_characters = ['露西亚', '安比', '安东', '本', '比利', '科琳', '艾伦', '格蕾丝', '莱卡恩', '露西', '猫又', '妮可', '派珀', 'rina', '士兵11', '朱雀', '朱元']
                self.character_combo.addItems(default_characters)
        except Exception as e:
            print(f"获取角色列表失败: {e}")
            # 默认角色列表
            default_characters = ['露西亚', '安比', '安东', '本', '比利', '科琳', '艾伦', '格蕾丝', '莱卡恩', '露西', '猫又', '妮可', '派珀', 'rina', '士兵11', '朱雀', '朱元']
            self.character_combo.addItems(default_characters)
        
        # 默认选择第一个角色
        if self.character_combo.count() > 0:
            self.character_combo.setCurrentIndex(0)
        
        character_layout.addWidget(self.character_combo)
        left_layout.addWidget(character_card)

        # 加载驱动盘名称
        self.drive_disk_names = []
        compendium_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'assets', 'game_data', 'compendium_data.yml')
        if os.path.exists(compendium_path):
            with open(compendium_path, 'r', encoding='utf-8') as f:
                compendium_data = yaml.safe_load(f)
            for tab in compendium_data:
                if 'category_list' in tab:
                    for category in tab['category_list']:
                        if category.get('category_name') == '区域巡防':
                            if 'mission_type_list' in category:
                                for mission_type in category['mission_type_list']:
                                    if 'mission_type_name_display' in mission_type:
                                        display_name = mission_type['mission_type_name_display']
                                        if display_name != '特训目标':  # 直接过滤
                                            # 直接拆分并添加
                                            for part in display_name.split(' ', 1):
                                                self.drive_disk_names.append(part)
        else:
            print(f"未找到 compendium_data.yml 文件: {compendium_path}")
        print(f"总共加载了 {len(self.drive_disk_names)} 个驱动盘名称")
        
        # 保存驱动盘名称到上下文
        setattr(self.ctx, '_drive_disk_names', self.drive_disk_names)
        print(f"已保存驱动盘名称到上下文: {len(self.drive_disk_names)} 个")

        # 创建6个卡片
        for i in range(1, 7):
            card = SimpleCardWidget()
            card_layout = QHBoxLayout(card)
            
            # 卡片名称
            label = QLabel(f'{i}号位')
            card_layout.addWidget(label)
            
            # 复选框
            checkbox = QCheckBox()
            checkbox.setChecked(False)  # 默认不勾选
            self.checkboxes.append(checkbox)
            card_layout.addWidget(checkbox)
            
            # 驱动盘选择下拉列表
            disk_combo = ComboBox()
            disk_combo.addItem('选择驱动盘')  # 默认选项
            disk_combo.addItems(self.drive_disk_names)
            disk_combo.setMinimumWidth(150)  # 设置最小宽度，解决下拉框显示省略号的问题
            self.disk_combos.append(disk_combo)
            card_layout.addWidget(disk_combo)
            
            right_layout.addWidget(card)

        return content
    
    def get_checkbox_states(self) -> List[bool]:
        """获取所有复选框的状态"""
        return [checkbox.isChecked() for checkbox in self.checkboxes]

    def on_interface_shown(self) -> None:
        """界面显示时的回调"""
        AppRunInterface.on_interface_shown(self)
        
        # 获取左侧布局的总高度
        if hasattr(self, 'help_opt'):
            # 等待布局完成
            import time
            time.sleep(0.1)
            
            # 获取使用说明卡片的高度
            help_height = self.help_opt.height()
            print(f"使用说明卡片高度: {help_height}px")
            
            # 获取角色选择卡片的高度
            if hasattr(self, 'character_combo') and self.character_combo.parent():
                character_card_height = self.character_combo.parent().height()
                print(f"角色选择卡片高度: {character_card_height}px")
                
                # 计算左侧分栏总高度
                left_total_height = help_height + character_card_height
                print(f"左侧分栏总高度: {left_total_height}px")

    def on_interface_hidden(self) -> None:
        """界面隐藏时的回调"""
        AppRunInterface.on_interface_hidden(self)

    def _on_start_clicked(self) -> None:
        """在启动应用前保存配置"""
        # 保存勾选状态到上下文
        if hasattr(self, 'checkboxes') and self.checkboxes:
            states = [checkbox.isChecked() for checkbox in self.checkboxes]
            setattr(self.ctx, '_drive_disk_enhance_states', states)
            print(f"驱动盘强化勾选状态: {states}")
        
        # 保存选择的角色名称到上下文
        if hasattr(self, 'character_combo') and self.character_combo:
            character_name = self.character_combo.currentText()
            setattr(self.ctx, '_drive_disk_enhance_character', character_name)
            print(f"驱动盘强化角色选择: {character_name}")
        
        # 保存选择的驱动盘名称到上下文
        if hasattr(self, 'disk_combos') and self.disk_combos:
            disk_selections = []
            for i, combo in enumerate(self.disk_combos):
                selected_disk = combo.currentText()
                if selected_disk != '选择驱动盘':
                    disk_selections.append(selected_disk)
                else:
                    disk_selections.append(None)
                print(f"{i+1}号位驱动盘选择: {selected_disk}")
            setattr(self.ctx, '_drive_disk_enhance_selections', disk_selections)
        
        print("启动驱动盘强化应用")
        AppRunInterface._on_start_clicked(self)
