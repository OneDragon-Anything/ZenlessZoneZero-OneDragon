import os
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QFileDialog
from qfluentwidgets import FluentIcon, LineEdit, PushButton, \
    ToolButton, PrimaryPushButton, HyperlinkCard, SettingCardGroup

from one_dragon.base.config.emulator_config import GameClient
from one_dragon.base.config.game_account_config import GameRegionEnum, GamePlatformEnum
from one_dragon.base.config.one_dragon_config import OneDragonInstance, RunInOneDragonApp
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox


class InstanceSettingCard(MultiPushSettingCard):

    changed = Signal(OneDragonInstance)
    active = Signal(int)
    login = Signal(int)
    delete = Signal(int)

    def __init__(self, instance: OneDragonInstance):
        self.instance: OneDragonInstance = instance

        self.instance_name_input = LineEdit()
        self.instance_name_input.setText(self.instance.name)
        self.instance_name_input.textChanged.connect(self._on_name_changed)

        self.run_opt = ComboBox()
        run_idx = 0
        target_idx = 0
        for opt_enum in RunInOneDragonApp:
            opt = opt_enum.value
            self.run_opt.addItem(text=opt.label, userData=opt.value)
            if opt.value == self.instance.active_in_od:
                target_idx = run_idx

            run_idx += 1
        self.run_opt.setCurrentIndex(target_idx)
        self.run_opt.currentIndexChanged.connect(self._on_run_changed)

        self.active_btn = PushButton(text='启用')
        self.active_btn.clicked.connect(self._on_active_clicked)
        self.active_btn.setDisabled(self.instance.active)
        self.login_btn = PushButton(text='登录')
        self.login_btn.clicked.connect(self._on_login_clicked)
        self.delete_btn = ToolButton(FluentIcon.DELETE, parent=None)
        self.delete_btn.clicked.connect(self._on_delete_clicked)

        MultiPushSettingCard.__init__(
            self,
            btn_list=[self.instance_name_input, self.run_opt, self.active_btn, self.login_btn, self.delete_btn],
            title='%02d' % self.instance.idx,
            icon=FluentIcon.PEOPLE,
        )
        self.update_title()

    def update_title(self) -> None:
        """
        更新显示文本
        """
        title = '%02d' % self.instance.idx
        if self.instance.active:
            title += ' ' + gt('当前', 'ui')
        self.setTitle(title)

    def _on_name_changed(self, text: str) -> None:
        self.instance.name = text
        self.changed.emit(self.instance)

    def _on_run_changed(self, idx: int) -> None:
        self.instance.active_in_od = self.run_opt.itemData(idx)
        self.changed.emit(self.instance)

    def _on_active_clicked(self) -> None:
        self.active.emit(self.instance.idx)

    def _on_login_clicked(self) -> None:
        self.login.emit(self.instance.idx)

    def _on_delete_clicked(self) -> None:
        self.delete.emit(self.instance.idx)

    def check_active(self, active_idx: int) -> None:
        """
        检查是否现在启用的 更新显示
        :return:
        """
        active = active_idx == self.instance.idx
        self.instance.active = active
        self.update_title()
        self.active_btn.setDisabled(active)


class SettingInstanceInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonContext, show_login_btn: bool = False, parent=None):
        VerticalScrollInterface.__init__(
            self,
            object_name='setting_instance_interface',
            content_widget=self.get_content_widget(),
            parent=parent,
            nav_text_cn='多账户管理'
        )
        self.ctx: OneDragonContext = ctx
        self.show_login_btn: bool = show_login_btn

    def get_content_widget(self) -> QWidget:
        """
        子界面内的内容组件 由子类实现
        :return:
        """
        self.content_widget = Column()
        self._init_content_widget()  # 调用 _init_content_widget 方法初始化内容组件

        return self.content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self._init_content_widget()

    def _init_content_widget(self) -> None:
        """
        重新初始化显示
        :return:
        """
        self.instance_card_list = []
        self.content_widget.clear_widgets()

        guide_opt = HyperlinkCard(
            url='http://onedragon-anything.github.io/zzz/zh/docs/feat_one_dragon.html#_4-%E5%A4%9A%E8%B4%A6%E5%8F%B7',
            text='说明',
            icon=FluentIcon.INFO,
            title='注意',
            content='点击启用后到各模块进行设置，各账户之间的设置是独立的。'
        )
        self.content_widget.add_widget(guide_opt)
        self.content_widget.add_widget(self._get_instanceSettings_group())
        self.content_widget.add_widget(self._get_instanceSwitch_group())
        self.content_widget.add_stretch(1)

        self.init_game_account_config()

        current_platform = self.ctx.game_account_config.platform
        # self.game_platform_opt.setCurrentText(current_platform)
        self._on_game_platform_changed(current_platform)  # 初始化可见性

    def init_game_account_config(self) -> None:
        # 初始化账号和密码
        self.game_platform_opt.init_with_adapter(self.ctx.game_account_config.get_prop_adapter('platform'))
        self.game_platform_opt.value_changed.connect(self._on_game_platform_changed)

        self.game_client_opt.init_with_adapter(self.ctx.emulator_config.get_prop_adapter('Alas.Emulator.GameClient'))
        self.emulator_path_opt.setContent(self.ctx.emulator_config.emulator_path)
        self.emulator_serial_opt.init_with_adapter(self.ctx.emulator_config.get_prop_adapter('Alas.Emulator.Serial'))

        self.game_path_opt.setContent(self.ctx.game_account_config.game_path)
        self.game_region_opt.init_with_adapter(self.ctx.game_account_config.get_prop_adapter('game_region'))
        self.game_account_opt.init_with_adapter(self.ctx.game_account_config.get_prop_adapter('account'))
        self.game_password_opt.init_with_adapter(self.ctx.game_account_config.get_prop_adapter('password'))

    def _get_instanceSwitch_group(self) -> QWidget:
        instance_switch_group = SettingCardGroup(gt('账户列表', 'ui'))

        for instance in self.ctx.one_dragon_config.instance_list:
            instance_card = InstanceSettingCard(instance)
            self.instance_card_list.append(instance_card)
            instance_switch_group.addSettingCard(instance_card)
            instance_card.changed.connect(self._on_instance_changed)
            instance_card.active.connect(self._on_instance_active)
            instance_card.login.connect(self._on_instance_login)
            instance_card.delete.connect(self._on_instance_delete)

        self.add_btn = PrimaryPushButton(text='新增')
        self.add_btn.setFixedHeight(40)  # 设置按钮的固定高度
        self.add_btn.clicked.connect(self._on_add_clicked)
        instance_switch_group.addSettingCard(self.add_btn)

        return instance_switch_group

    def _get_instanceSettings_group(self) -> QWidget:
        instance_settings_group = SettingCardGroup(gt('当前账户设置', 'ui'))

        # 获取当前平台
        current_platform = self.ctx.game_account_config.platform if hasattr(self, 'ctx') else 0
        if current_platform == 'PC':
            is_emulator_platform = 0
            is_pc_platform = 1
        elif current_platform == '模拟器':
            is_emulator_platform = 1
            is_pc_platform = 0

        log.info(f"平台初始为: {current_platform}")
        self.game_platform_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='游戏平台', options_enum=GamePlatformEnum)
        instance_settings_group.addSettingCard(self.game_platform_opt)

        self.game_client_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='游戏客户端', options_enum=GameClient)
        instance_settings_group.addSettingCard(self.game_client_opt)
        self.game_client_opt.setVisible(is_emulator_platform)  # 根据平台设置初始可见性

        self.emulator_path_opt = PushSettingCard(icon=FluentIcon.FOLDER, title='模拟器路径', text='选择')
        self.emulator_path_opt.clicked.connect(self._on_emulator_path_clicked)
        instance_settings_group.addSettingCard(self.emulator_path_opt)
        self.emulator_path_opt.setVisible(is_emulator_platform)  # 根据平台设置初始可见性

        self.emulator_serial_opt = TextSettingCard(icon=FluentIcon.PEOPLE, title='模拟器 Serial')
        instance_settings_group.addSettingCard(self.emulator_serial_opt)
        self.emulator_serial_opt.setVisible(is_emulator_platform)  # 根据平台设置初始可见性

        self.game_path_opt = PushSettingCard(icon=FluentIcon.FOLDER, title='游戏路径', text='选择')
        self.game_path_opt.clicked.connect(self._on_game_path_clicked)
        instance_settings_group.addSettingCard(self.game_path_opt)
        self.game_path_opt.setVisible(is_pc_platform)  # 根据平台设置初始可见性

        self.game_region_opt = ComboBoxSettingCard(icon=FluentIcon.HOME, title='游戏区服', options_enum=GameRegionEnum)
        instance_settings_group.addSettingCard(self.game_region_opt)
        self.game_region_opt.setVisible(is_pc_platform)  # 根据平台设置初始可见性

        self.game_account_opt = TextSettingCard(
            icon=FluentIcon.PEOPLE,
            title='账号',
            input_placeholder='所有信息都明文保存在本地')
        instance_settings_group.addSettingCard(self.game_account_opt)

        self.game_password_opt = TextSettingCard(
            icon=FluentIcon.EXPRESSIVE_INPUT_ENTRY,
            title='密码',
            input_placeholder='请自行妥善管理',
            is_password=True  # 设置为密码模式
        )
        instance_settings_group.addSettingCard(self.game_password_opt)

        # self.input_way_opt = ComboBoxSettingCard(icon=FluentIcon.CLIPPING_TOOL, title='输入方式',
        #                                          options_enum=TypeInputWay)
        # instance_settings_group.addSettingCard(self.input_way_opt)

        return instance_settings_group

    def _on_add_clicked(self) -> None:
        self.ctx.one_dragon_config.create_new_instance(False)
        self._init_content_widget()

    def _on_instance_changed(self, instance: OneDragonInstance) -> None:
        self.ctx.one_dragon_config.update_instance(instance)

    def _on_instance_active(self, idx: int) -> None:
        self.ctx.switch_instance(idx)

        for instance_card in self.instance_card_list:
            instance_card.check_active(idx)

        # 更新当前账户设置中的内容
        active_instance = next((inst for inst in self.ctx.one_dragon_config.instance_list if inst.idx == idx), None)
        if active_instance is not None:
            self.init_game_account_config()

    def _on_instance_login(self, idx: int) -> None:
        log.error('未配置登录操作')

    def _on_instance_delete(self, idx: int) -> None:
        if len(self.ctx.one_dragon_config.instance_list) <= 1:
            return

        self.ctx.one_dragon_config.delete_instance(idx)
        self._init_content_widget()

    def _on_game_region_changed(self, index, value):
        self.ctx.init_by_config()

    def _on_game_path_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, gt('选择你的 ZenlessZoneZero.exe'), filter="Exe (*.exe)")
        if file_path is not None and file_path.endswith('.exe'):
            log.info('选择路径 %s', file_path)
            self._on_game_path_chosen(os.path.normpath(file_path))

    def _on_game_path_chosen(self, file_path) -> None:
        self.ctx.game_account_config.game_path = file_path
        self.game_path_opt.setContent(file_path)

    def _on_emulator_path_clicked(self) -> None:
        """
        当点击模拟器路径选择按钮时，弹出文件选择对话框
        """
        file_path, _ = QFileDialog.getOpenFileName(self, gt('选择模拟器可执行文件'), filter="Exe (*.exe)")
        if file_path is not None and file_path.endswith('.exe'):
            log.info('选择模拟器路径 %s', file_path)
            self._on_emulator_path_chosen(os.path.normpath(file_path))

    def _on_emulator_path_chosen(self, file_path) -> None:
        """
        当模拟器路径选择完成后，更新配置并显示在界面上
        """
        self.ctx.emulator_config.emulator_path = file_path
        self.emulator_path_opt.setContent(file_path)

    def _on_game_platform_changed(self, platform: str) -> None:
        """当游戏平台选择变化时，动态调整其他设置项的显示状态"""
        log.info(f"平台切换为: {platform}")
        
        # 确保所有元素都已创建
        if not hasattr(self, 'game_path_opt') or not hasattr(self, 'game_region_opt') or \
           not hasattr(self, 'game_client_opt') or not hasattr(self, 'emulator_path_opt') or \
           not hasattr(self, 'emulator_serial_opt'):
            log.error("界面元素尚未完全初始化")
            return
            
        if platform == 0 or platform == 'PC':
            # PC平台显示的元素
            self.game_path_opt.setVisible(True)
            self.game_region_opt.setVisible(True)
            
            # PC平台隐藏的元素
            self.game_client_opt.setVisible(False)
            self.emulator_path_opt.setVisible(False)
            self.emulator_serial_opt.setVisible(False)
            
            log.info("已切换到PC平台视图")
        elif platform == 1 or platform == '模拟器':
            # 模拟器平台显示的元素
            self.game_client_opt.setVisible(True)
            self.emulator_path_opt.setVisible(True)
            self.emulator_serial_opt.setVisible(True)
            
            # 模拟器平台隐藏的元素
            self.game_path_opt.setVisible(False)
            self.game_region_opt.setVisible(False)
            
            log.info("已切换到模拟器平台视图")
        else:
            log.warning(f"未知平台类型: {platform}")
            
        # 强制更新布局
        self.content_widget.updateGeometry()
        self.content_widget.update()
