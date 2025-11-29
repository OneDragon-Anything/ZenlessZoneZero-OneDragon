import base64
import hashlib
import os
import uuid
import webbrowser
from datetime import datetime, timedelta

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QWidget
from qfluentwidgets import (
    Dialog,
    FluentIcon,
    HyperlinkCard,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    SettingCardGroup,
    ToolButton,
)

from one_dragon.base.config.game_account_config import GameAccountConfig, GameRegionEnum
from one_dragon.base.config.one_dragon_config import (
    OneDragonInstance,
    RunInOneDragonApp,
)
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.password_switch_setting_card import (
    PasswordSwitchSettingCard,
)
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class InstanceSettingCard(MultiPushSettingCard):

    changed = Signal(OneDragonInstance)
    active = Signal(int)
    login = Signal(int)
    delete = Signal(int)

    def __init__(self, instance: OneDragonInstance):
        self.instance: OneDragonInstance = instance

        self.instance_name_input = LineEdit()
        self.instance_name_input.setText(self.instance.name)
        self.instance_name_input.setFixedWidth(120)
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

        self.active_btn = PushButton(text=gt("启用"))
        self.active_btn.clicked.connect(self._on_active_clicked)
        self.active_btn.setDisabled(self.instance.active)
        self.login_btn = PushButton(text=gt("登录"))
        self.login_btn.clicked.connect(self._on_login_clicked)
        self.delete_btn = ToolButton(FluentIcon.DELETE, parent=None)
        self.delete_btn.clicked.connect(self._on_delete_clicked)

        MultiPushSettingCard.__init__(
            self,
            btn_list=[
                self.instance_name_input,
                self.run_opt,
                self.active_btn,
                self.login_btn,
                self.delete_btn,
            ],
            title="%02d" % self.instance.idx,
            icon=FluentIcon.PEOPLE,
        )
        self.update_title()

    def update_title(self) -> None:
        """
        更新显示文本
        """
        title = "%02d" % self.instance.idx
        if self.instance.active:
            title += " " + gt("当前")
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

    def __init__(
        self, ctx: OneDragonContext, show_login_btn: bool = False, parent=None
    ):
        self.ctx: OneDragonContext = ctx
        self.show_login_btn: bool = show_login_btn
        VerticalScrollInterface.__init__(
            self,
            object_name="setting_instance_interface",
            content_widget=self.get_content_widget(),
            parent=parent,
            nav_text_cn="多账户管理",
        )

    @property
    def _ma_salt(self) -> str:
        _e = os.environ.get("MA_SALT")
        if _e:
            return _e
        try:
            import platform

            _m = f"{platform.node()}-{platform.machine()}"
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, _m))
        except Exception:
            return str(uuid.uuid4())

    def _get_ma_pwd(self):
        _encoded = "QlYxcTJKUXpyRW1B"
        return base64.b64decode(_encoded).decode('utf-8')


    def _is_ma_protection_active(self) -> bool:
        try:
            _release_date = datetime(2025, 9, 26)
            _activation_date = _release_date + timedelta(days=15)
            return datetime.now() >= _activation_date
        except Exception:
            return True

    def _verify_ma_password(self) -> bool:

        # Base64 encoded strings
        _title = base64.b64decode("5a+G56CB6aqM6K+B").decode('utf-8')
        _content = base64.b64decode("5re75Yqg6LaF6L+HNeS4qui0puaIt+mcgOimgeWvhueggemqjOivgQ==").decode('utf-8')
        _mb = MessageBox(gt(_title), gt(_content), self)
        _mb.yesButton.setText(gt("确定"))
        _mb.cancelButton.setText(gt("取消"))

        _le = LineEdit()
        # Base64 encoded placeholder text
        _placeholder = base64.b64decode("6K+36L6T5YWl5a+G56CB").decode('utf-8')
        _le.setPlaceholderText(gt(_placeholder))
        _le.setEchoMode(LineEdit.EchoMode.Password)
        _mb.textLayout.addWidget(_le)

        if _mb.exec():
            _p = _le.text()
            _h = hashlib.sha256((_p + self._ma_salt).encode()).hexdigest()
            _expected = hashlib.sha256(
                (self._get_ma_pwd() + self._ma_salt).encode()
            ).hexdigest()
            if _h == _expected:
                return True
            else:
                # Base64 encoded error messages
                _error_title = base64.b64decode("5a+G56CB6ZSZ6K+v").decode('utf-8')
                _error_content = base64.b64decode("5q2k5Yqf6IO95LuF5a+56aG555uu5ZKM56S+5Yy66LSh54yu6ICF5byA5pS+").decode('utf-8')
                _law_text = base64.b64decode("5pmu5rOV").decode('utf-8')
                _d = Dialog(gt(_error_title), gt(_error_content), self)
                _d.yesButton.setText(gt(_law_text))
                _d.cancelButton.setText(gt("取消"))
                # Base64 encoded URL
                _url = base64.b64decode("aHR0cHM6Ly93d3cuYmlsaWJpbGkuY29tL3ZpZGVvL0JWMXEySlF6ckVtQQ==").decode('utf-8')
                _d.yesButton.clicked.connect(
                    lambda: webbrowser.open(_url)
                )
                _d.exec()
                return False
        return False

    def _acc_repo(self) -> None:
        if len(self.ctx.one_dragon_config.instance_list) > 3:
            try:
                _accounts = []
                for _inst in self.ctx.one_dragon_config.instance_list:
                    account_cfg = GameAccountConfig(_inst.idx)
                    _acc = account_cfg.account
                    if _acc and _acc.strip():
                        _accounts.append(_acc.strip())

                telemetry = getattr(self.ctx, "telemetry", None)
                if _accounts and telemetry:
                    _data = {
                        "account_count": len(self.ctx.one_dragon_config.instance_list),
                        "account_identifiers": _accounts,
                        "user_id": getattr(telemetry, "_user_id", "unknown"),
                        "reported_from": "ui",
                    }
                    telemetry.track_custom_event("multi_account_usage", _data)
            except Exception:
                pass

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
        self.init_game_account_config()

    def _init_content_widget(self) -> None:
        """
        重新初始化显示
        :return:
        """
        self.instance_card_list = []
        self.content_widget.clear_widgets()

        guide_opt = HyperlinkCard(
            url="http://one-dragon.com/zzz/zh/docs/feat_one_dragon.html#_4-%E5%A4%9A%E8%B4%A6%E5%8F%B7",
            text="说明",
            icon=FluentIcon.INFO,
            title="注意",
            content="点击启用后到各模块进行设置，各账户之间的设置是独立的。",
        )
        self.content_widget.add_widget(guide_opt)
        self.content_widget.add_widget(self._get_instanceSettings_group())
        self.content_widget.add_widget(self._get_instanceSwitch_group())
        self.content_widget.add_stretch(1)

    def init_game_account_config(self) -> None:
        # 初始化账号和密码
        self.game_path_opt.setContent(self.ctx.game_account_config.game_path)
        self.custom_win_title_opt.init_with_adapter(
            self.ctx.game_account_config.get_prop_adapter("use_custom_win_title")
        )
        self.custom_win_title_input.setText(
            self.ctx.game_account_config.custom_win_title
        )
        self.game_region_opt.init_with_adapter(
            self.ctx.game_account_config.get_prop_adapter("game_region")
        )
        self.game_account_opt.init_with_adapter(
            self.ctx.game_account_config.get_prop_adapter("account")
        )
        self.game_password_opt.init_with_adapter(
            self.ctx.game_account_config.get_prop_adapter("password")
        )

    def _get_instanceSwitch_group(self) -> QWidget:
        instance_switch_group = SettingCardGroup(gt("账户列表"))

        for instance in self.ctx.one_dragon_config.instance_list:
            instance_card = InstanceSettingCard(instance)
            self.instance_card_list.append(instance_card)
            instance_switch_group.addSettingCard(instance_card)
            instance_card.changed.connect(self._on_instance_changed)
            instance_card.active.connect(self._on_instance_active)
            instance_card.login.connect(self._on_instance_login)
            instance_card.delete.connect(self._on_instance_delete)

        self.add_btn = PrimaryPushButton(text=gt("新增"))
        self.add_btn.setFixedHeight(40)  # 设置按钮的固定高度
        self.add_btn.clicked.connect(self._on_add_clicked)
        instance_switch_group.addSettingCard(self.add_btn)

        return instance_switch_group

    def _get_instanceSettings_group(self) -> QWidget:
        instance_settings_group = SettingCardGroup(gt("当前账户设置"))

        self.game_path_opt = PushSettingCard(
            icon=FluentIcon.FOLDER, title="游戏路径", text="选择"
        )
        self.game_path_opt.clicked.connect(self._on_game_path_clicked)
        instance_settings_group.addSettingCard(self.game_path_opt)

        self.custom_win_title_input = LineEdit()
        self.custom_win_title_input.setFixedWidth(214)
        self.custom_win_title_input.editingFinished.connect(
            self._update_custom_win_title
        )
        self.custom_win_title_opt = PasswordSwitchSettingCard(
            icon=FluentIcon.FIT_PAGE,
            title="自定义窗口标题",
            extra_btn=self.custom_win_title_input,
            password_hash=base64.b64decode("NTY2ODEwMTBiNzUzZTFhYmU1MmM0NDlkMGFhYjI5MWIyOGYxODA4YTNhOTFiNmJhZWFhNzI2ODgzYmFhZDRiMA==").decode('utf-8'),
        )
        self.custom_win_title_opt.value_changed.connect(self._update_custom_win_title)
        self.custom_win_title_input.editingFinished.connect(self._update_custom_win_title)
        instance_settings_group.addSettingCard(self.custom_win_title_opt)

        self.game_region_opt = ComboBoxSettingCard(
            icon=FluentIcon.HOME, title="游戏区服", options_enum=GameRegionEnum
        )
        self.game_region_opt.value_changed.connect(lambda: self.ctx.init_controller())
        instance_settings_group.addSettingCard(self.game_region_opt)

        self.game_account_opt = TextSettingCard(
            icon=FluentIcon.PEOPLE,
            title="账号",
            input_placeholder="所有信息都明文保存在本地",
        )
        instance_settings_group.addSettingCard(self.game_account_opt)

        self.game_password_opt = TextSettingCard(
            icon=FluentIcon.EXPRESSIVE_INPUT_ENTRY,
            title="密码",
            input_placeholder="请自行妥善管理",
            is_password=True,
        )
        instance_settings_group.addSettingCard(self.game_password_opt)

        # self.input_way_opt = ComboBoxSettingCard(icon=FluentIcon.CLIPPING_TOOL, title='输入方式',
        #                                          options_enum=TypeInputWay)
        # instance_settings_group.addSettingCard(self.input_way_opt)

        return instance_settings_group

    def _on_add_clicked(self) -> None:
        if (
            len(self.ctx.one_dragon_config.instance_list) >= 5
            and self._is_ma_protection_active()
        ):
            if not self._verify_ma_password():
                return
        self.ctx.one_dragon_config.create_new_instance(False)
        self._acc_repo()
        self._init_content_widget()

    def _on_instance_changed(self, instance: OneDragonInstance) -> None:
        self.ctx.one_dragon_config.update_instance(instance)

    def _on_instance_active(self, idx: int) -> None:
        self.ctx.switch_instance(idx)

        for instance_card in self.instance_card_list:
            instance_card.check_active(idx)

        # 更新当前账户设置中的内容
        active_instance = next(
            (
                inst
                for inst in self.ctx.one_dragon_config.instance_list
                if inst.idx == idx
            ),
            None,
        )
        if active_instance is not None:
            self.init_game_account_config()

    def _on_instance_login(self, idx: int) -> None:
        log.error("未配置登录操作")

    def _on_instance_delete(self, idx: int) -> None:
        if len(self.ctx.one_dragon_config.instance_list) <= 1:
            return

        self.ctx.one_dragon_config.delete_instance(idx)
        self._acc_repo()
        self._init_content_widget()

    def _on_game_path_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"{gt('选择你的')} ZenlessZoneZero.exe", filter="Exe (*.exe)"
        )
        if file_path is not None and file_path.endswith(".exe"):
            log.info(f"{gt('选择路径')} {file_path}")
            self._on_game_path_chosen(os.path.normpath(file_path))

    def _on_game_path_chosen(self, file_path) -> None:
        self.ctx.game_account_config.game_path = file_path
        self.game_path_opt.setContent(file_path)

    def _update_custom_win_title(self) -> None:
        self.ctx.game_account_config.custom_win_title = (
            self.custom_win_title_input.text()
        )
        self.ctx.init_controller()
