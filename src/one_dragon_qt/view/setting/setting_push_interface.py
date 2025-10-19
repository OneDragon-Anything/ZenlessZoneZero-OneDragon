import json

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, PushButton, InfoBar, InfoBarPosition, SettingCard

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.controller.pc_clipboard import PcClipboard
from one_dragon.base.push.curl_generator import CurlGenerator
from one_dragon.base.push.push_config import PushProxy
from one_dragon.base.push.push_email_services import PushEmailServices
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.base.push.push_channel_config import PushChannelConfigField, FieldTypeEnum
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.code_editor_setting_card import CodeEditorSettingCard
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.editable_combo_box_setting_card import EditableComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.key_value_setting_card import KeyValueSettingCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class SettingPushInterface(VerticalScrollInterface):

    def __init__(self, ctx: OneDragonContext, parent=None):

        VerticalScrollInterface.__init__(
            self,
            object_name='setting_push_interface',
            content_widget=None, parent=parent,
            nav_text_cn='通知设置',
            nav_icon=FluentIcon.MESSAGE
        )
        self.ctx: OneDragonContext = ctx

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.custom_push_title = TextSettingCard(
            icon=FluentIcon.MESSAGE,
            title='自定义通知标题',
            input_placeholder='一条龙运行通知'
        )
        content_widget.add_widget(self.custom_push_title)

        self.send_image_opt = SwitchSettingCard(icon=FluentIcon.PHOTO, title='通知中附带图片')
        content_widget.add_widget(self.send_image_opt)

        self.proxy_opt = ComboBoxSettingCard(
            icon=FluentIcon.GLOBE,
            title='代理设置',
            options_enum=PushProxy,
        )
        content_widget.add_widget(self.proxy_opt)

        self.test_current_btn = PushButton(text='测试当前方式', icon=FluentIcon.SEND, parent=self)
        self.test_current_btn.clicked.connect(self._send_test_message)
        self.test_all_btn = PushButton(text='测试全部', icon=FluentIcon.SEND_FILL, parent=self)
        self.test_all_btn.clicked.connect(self._send_test_all_message)

        self.test_notification_card = MultiPushSettingCard(
            icon=FluentIcon.MESSAGE,
            title='测试通知方式',
            content='发送测试消息验证通知配置',
            btn_list=[self.test_current_btn, self.test_all_btn]
        )
        content_widget.add_widget(self.test_notification_card)

        # 通知方式选择
        self.notification_method_opt = ComboBoxSettingCard(
            icon=FluentIcon.MESSAGE,
            title='通知方式',
            options_list=[
                ConfigItem(label=i.channel_name, value=i.channel_id)
                for i in self.ctx.push_service.channels
            ]
        )
        self.notification_method_opt.value_changed.connect(self._update_notification_ui)
        content_widget.add_widget(self.notification_method_opt)

        self.pwsh_curl_btn = PushButton(text='PowerShell 风格')
        self.pwsh_curl_btn.clicked.connect(lambda: self._generate_curl('pwsh'))

        self.unix_curl_btn = PushButton(text='Unix 风格')
        self.unix_curl_btn.clicked.connect(lambda: self._generate_curl('unix'))

        self.curl_btn = MultiPushSettingCard(icon=FluentIcon.CODE, title='生成 cURL 命令', btn_list=[self.pwsh_curl_btn, self.unix_curl_btn])
        self.curl_btn.setVisible(False)
        content_widget.add_widget(self.curl_btn)

        email_services = PushEmailServices.load_services()
        service_options = [ConfigItem(label=name, value=name, desc="") for name in email_services.keys()]
        self.email_service_opt = EditableComboBoxSettingCard(
            icon=FluentIcon.MESSAGE,
            title='邮箱服务选择',
            options_list=service_options,
            input_placeholder='选择后自动填充相关配置'
        )
        self.email_service_opt.value_changed.connect(lambda idx, val: self._on_email_service_selected(val))
        self.email_service_opt.combo_box.setFixedWidth(320)
        self.email_service_opt.combo_box.setCurrentIndex(-1)  # 设置为无选中状态
        self.email_service_opt.setVisible(False)  # 默认隐藏，SMTP方式时显示
        content_widget.add_widget(self.email_service_opt)

        self.push_channel_cards: dict[str, list] = {}
        all_cards_widget = Column()
        for channel in self.ctx.push_service.channels:
            channel_cards = []

            for field in channel.config_schema:
                card = self._create_card(channel.channel_id, field)
                channel_cards.append(card)
                all_cards_widget.add_widget(card)

            self.push_channel_cards[channel.channel_id] = channel_cards

        content_widget.add_widget(all_cards_widget)
        content_widget.add_stretch(1)

        return content_widget

    def _create_card(self, channel_id: str, field: PushChannelConfigField) -> QWidget:
        """
        根据推送渠道所需的配置字段 动态创建配置组件

        Args:
            channel_id: 推送渠道ID
            field: 配置字段

        Returns:
            QWidget: 配置组件
        """

        """"""
        var_name = self._get_channel_field_card_name(channel_id, field)
        title = field.title
        card_type = field.field_type
        is_required = field.required

        # 如果是必选项，在标题后添加红色星号
        if is_required:
            title += " <span style='color: #ff6b6b;'>*</span>"

        if card_type == FieldTypeEnum.COMBO:
            options = field.options
            card = ComboBoxSettingCard(
                icon=getattr(FluentIcon, field.icon),
                title=title,
                options_list=[ConfigItem(label=opt, value=opt) for opt in options]
            )
        elif card_type == FieldTypeEnum.KEY_VALUE:
            card = KeyValueSettingCard(
                icon=getattr(FluentIcon, field.icon),
                title=title,
            )
        elif card_type == FieldTypeEnum.CODE_EDITOR:
            card = CodeEditorSettingCard(
                icon=getattr(FluentIcon, field.icon),
                title=title,
            )
        else:  # 默认为 text
            card = TextSettingCard(
                icon=getattr(FluentIcon, field.icon),
                title=title,
                input_max_width=320,
                input_placeholder=field.placeholder,
            )

        card.setObjectName(var_name)
        card.setVisible(False)
        setattr(self, var_name, card)
        return card

    def _get_channel_field_card_name(self, channel_id: str, field: PushChannelConfigField) -> str:
        """
        获取推送渠道的配置字段的组件名称

        Args:
            channel_id: 推送渠道ID
            field: 推送渠道的配置字段

        Returns:
            str: 组件名称
        """
        return f"{channel_id}_{field.var_suffix}_push_card".lower()

    def _send_test_message(self):
        """发送测试消息到当前选择的通知方式"""
        selected_method = self.notification_method_opt.getValue()
        test_method = str(selected_method)
        if test_method == "WEBHOOK":
            # 如果是Webhook方式，先验证配置
            try:
                self._validate_webhook_config()
            except ValueError as e:
                self._show_error_message(str(e))
                return

        try:
            ok, msg = self.ctx.push_service.push(
                channel_id=test_method,
                content=gt('这是一条测试消息'),
            )
            if not ok:
                self._show_error_message(msg)
            else:
                self._show_success_message("已向当前通知方式发送测试消息")
        except ValueError as e:
            self._show_error_message(str(e))
        except Exception as e:
            self._show_error_message(f"测试推送失败: {str(e)}")

    def _send_test_all_message(self):
        """发送测试消息到所有已配置的通知方式"""
        try:
            self._show_success_message("正在向所有已配置的通知方式发送测试消息...")
            ok, msg = self.ctx.push_service.push(
                content=gt('这是一条测试消息'),
            )
            if not ok:
                self._show_error_message(msg)
            else:
                self._show_success_message("已向所有已配置的通知方式发送测试消息")
        except ValueError as e:
            self._show_error_message(str(e))
        except Exception as e:
            self._show_error_message(f"测试推送失败: {str(e)}")

    def _on_email_service_selected(self, text):
        config = PushEmailServices.get_configs(str(text))
        if config:
            # 自动填充SMTP相关卡片
            smtp_server = config["host"]
            smtp_port = config.get("port", 465)
            smtp_ssl = str(config.get("secure", True)).lower() if "secure" in config else "true"
            # 找到对应的TextSettingCard并赋值
            server_card: SettingCard = getattr(self, "smtp_server_push_card", None)
            if server_card is not None:
                host = f"{smtp_server}:{smtp_port}"
                server_card.setValue(host)
                adapter: YamlConfigAdapter = getattr(server_card, "adapter", None)
                if adapter is not None:
                    adapter.set_value(host)
            ssl_card: SettingCard = getattr(self, "smtp_ssl_push_card", None)
            if ssl_card is not None:
                ssl_card.setValue(smtp_ssl)
                adapter: YamlConfigAdapter = getattr(ssl_card, "adapter", None)
                if adapter is not None:
                    adapter.set_value(smtp_ssl)

    def _update_notification_ui(self):
        """根据选择的通知方式更新界面"""
        selected_method = self.notification_method_opt.getValue()

        # 隐藏所有卡片
        for method_name, method_cards in self.push_channel_cards.items():
            is_selected = (method_name == selected_method)
            for card in method_cards:
                card.setVisible(is_selected)

        # 特殊按钮
        self.email_service_opt.setVisible(selected_method == "SMTP")
        self.curl_btn.setVisible(selected_method == "WEBHOOK")

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        config = self.ctx.push_service.push_config

        self.custom_push_title.init_with_adapter(get_prop_adapter(config, 'custom_push_title'))
        self.send_image_opt.init_with_adapter(get_prop_adapter(config, 'send_image'))
        self.proxy_opt.init_with_adapter(get_prop_adapter(config, 'proxy'))

        # 动态初始化所有通知卡片
        for channel in self.ctx.push_service.channels:
            channel_id = channel.channel_id
            for field in channel.config_schema:
                var_name = self._get_channel_field_card_name(channel_id, field)
                config_key = self.ctx.push_service.push_config.get_channel_config_key(channel_id, field.var_suffix)
                card = getattr(self, var_name, None)
                if card is not None:
                    card.init_with_adapter(get_prop_adapter(config, config_key))

        # 初始更新界面状态
        self._update_notification_ui()

    def _generate_curl(self, style: str):
        """生成 cURL 示例命令"""
        # 获取配置
        original_config = self.ctx.push_service.get_channel_config('WEBHOOK')
        config = {}
        for key, value in original_config.items():
            config[key.lower()] = value

        # 检查必需的 URL 配置
        if not config['url']:
            self._show_error_message("请先配置 Webhook URL")
            return

        # 使用 CurlGenerator 处理配置
        curl_generator = CurlGenerator()
        curl_command = curl_generator.generate_curl_command(config, style)

        if not curl_command:
            self._show_error_message("Webhook URL 不能为空")
            return

        # 复制到剪贴板
        PcClipboard.copy_string(curl_command)
        self._show_success_message("cURL 命令已复制到剪贴板！")

    def _validate_webhook_config(self) -> None:
        """
        验证Webhook配置
        验证失败时抛出异常
        """
        config = self.ctx.push_service.get_channel_config('WEBHOOK')
        url = config.get('URL')
        if not url:
            raise ValueError("Webhook URL 未配置，无法推送")

        body = config.get('BODY')
        headers = config.get('HEADERS')
        content_type = config.get('CONTENT_TYPE')

        # 检查是否包含 $content
        if not any('$content' in str(field) for field in [url, body, headers]):
            raise ValueError("URL、请求头或者请求体中必须包含 $content 变量")

        # 如果是JSON格式，验证JSON的合法性
        if content_type == "application/json":
            # 检查body模板是否为合法JSON
            if not self._validate_json_format(body):
                raise ValueError("请求体不是合法的JSON格式")

        # 检查请求头是否为合法JSON
        if headers and headers != "{}":
            if not self._validate_json_format(headers):
                raise ValueError("请求头不是合法的JSON格式")

    def _validate_json_format(self, json_str: str) -> bool:
        """验证JSON格式的合法性"""
        try:
            json.loads(json_str)
            return True
        except (json.JSONDecodeError, TypeError):
            return False

    def _show_success_message(self, message: str):
        """显示成功消息提示"""
        InfoBar.success(
            title='成功',
            content=message,
            orient=InfoBarPosition.TOP,
            isClosable=True,
            duration=3000,
            parent=self
        )

    def _show_error_message(self, message: str):
        """显示错误消息提示"""
        InfoBar.error(
            title='错误',
            content=message,
            orient=InfoBarPosition.TOP,
            isClosable=True,
            duration=5000,
            parent=self
        )
