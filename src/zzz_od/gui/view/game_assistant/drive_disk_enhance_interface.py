from typing import Optional, List

from one_dragon.utils.log_utils import log
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.application.drive_disk_enhance.drive_disk_enhance_const import APP_ID
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext

from PySide6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QLabel, QCheckBox, QComboBox
from qfluentwidgets import SimpleCardWidget, ComboBox


class DriveDiskEnhanceInterface(AppRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        self.app: Optional[ZApplication] = None
        self.checkboxes: List[QCheckBox] = []
        self.character_combo: Optional[QComboBox] = None

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

        content = Row()
        left_layout = QVBoxLayout()
        content.h_layout.addLayout(left_layout)

        self.help_opt = HelpCard(
            title='使用说明',
            content='自动强化驱动盘功能\n从驱动盘详细页开始，自动进行强化操作\n注意：请确保游戏分辨率为 1920x1080'
        )
        left_layout.addWidget(self.help_opt)

        # 角色选择卡片
        character_card = SimpleCardWidget()
        character_layout = QHBoxLayout(character_card)
        character_label = QLabel('选择角色:')
        character_layout.addWidget(character_label)
        
        self.character_combo = QComboBox()
        
        # 获取角色列表
        try:
            # 运行JavaScript脚本获取角色列表
            import os
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

        # 右侧布局：6个卡片和复选框
        right_layout = QVBoxLayout()
        content.h_layout.addLayout(right_layout)

        # 创建6个卡片
        for i in range(1, 7):
            card = SimpleCardWidget()
            card_layout = QHBoxLayout(card)
            
            # 卡片名称
            label = QLabel(f'{i}号位')
            card_layout.addWidget(label)
            
            # 复选框
            checkbox = QCheckBox()
            checkbox.setChecked(True)  # 默认勾选
            self.checkboxes.append(checkbox)
            card_layout.addWidget(checkbox)
            
            right_layout.addWidget(card)

        return content
    
    def get_checkbox_states(self) -> List[bool]:
        """获取所有复选框的状态"""
        return [checkbox.isChecked() for checkbox in self.checkboxes]

    def on_interface_shown(self) -> None:
        """界面显示时的回调"""
        AppRunInterface.on_interface_shown(self)

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
        
        print("启动驱动盘强化应用")
        AppRunInterface._on_start_clicked(self)
