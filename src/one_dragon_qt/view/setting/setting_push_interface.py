from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, SubtitleLabel, ExpandGroupSettingCard, PushButton

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.push_config import NotifyMethodEnum
from one_dragon.base.notify.push import Push
from one_dragon.base.notify.push_email_services import PushEmailServices
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.push_cards import PushCards
from one_dragon_qt.widgets.setting_card.code_editor_setting_card import CodeEditorSettingCard
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.editable_combo_box_setting_card import EditableComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.key_value_setting_card import KeyValueSettingCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
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

        # 测试通知方式 - 使用MultiPushSettingCard
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

        # cURL 示例生成器（仅在 WEBHOOK 模式下显示）
        self.curl_btn = PushSettingCard(icon=FluentIcon.CODE, title='生成 cURL 示例', text='生成调试命令')
        self.curl_btn.clicked.connect(self._generate_curl)
        self.curl_btn.setVisible(False)
        content_widget.add_widget(self.curl_btn)

        # 通知方式选择
        self.notification_method_opt = ComboBoxSettingCard(
            icon=FluentIcon.MESSAGE,
            title='通知方式',
            options_enum=NotifyMethodEnum
        )
        self.notification_method_opt.value_changed.connect(self._update_notification_ui)
        content_widget.add_widget(self.notification_method_opt)

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

        self.cards = {}
        all_cards_widget = Column()
        for method, configs in PushCards.get_configs().items():
            method_cards = []

            if method == 'WEBHOOK':
                # Webhook 使用新的带分组的格式
                for group_config in configs:
                    group_title = group_config['group']
                    is_collapsible = group_config.get('collapsible', False)

                    if is_collapsible:
                        # 创建可折叠的分组
                        expand_group = ExpandGroupSettingCard(
                            icon=FluentIcon.SETTING,
                            title=group_title,
                            parent=self
                        )
                        expand_group.setExpand(False)
                        all_cards_widget.add_widget(expand_group)
                        method_cards.append(expand_group)

                        # 将卡片添加到可折叠分组中
                        for item_config in group_config['items']:
                            card = self._create_card(method, item_config)
                            setattr(self, card.objectName(), card)
                            expand_group.addGroupWidget(card)
                            method_cards.append(card)
                    else:
                        # 普通的分组标题
                        group_title_widget = SubtitleLabel(group_title, self)
                        all_cards_widget.add_widget(group_title_widget)
                        method_cards.append(group_title_widget)

                        for item_config in group_config['items']:
                            card = self._create_card(method, item_config)
                            setattr(self, card.objectName(), card)
                            all_cards_widget.add_widget(card)
                            method_cards.append(card)
            else:
                # legacy通知
                for config in configs:
                    var_name = f"{method}_{config['var_suffix']}_push_card".lower()
                    card = TextSettingCard(
                        icon=config["icon"],
                        title=config["title"],
                        input_max_width=320,
                        input_placeholder=config.get("placeholder", "")
                    )
                    card.setObjectName(var_name)
                    card.setVisible(False)
                    setattr(self, var_name, card)
                    method_cards.append(card)
                    all_cards_widget.add_widget(card)

            self.cards[method] = method_cards

        content_widget.add_widget(all_cards_widget)
        content_widget.add_stretch(1)

        return content_widget

    def _create_card(self, method: str, config: dict):
        """根据配置动态创建卡片"""
        var_name = f"{method}_{config['var_suffix']}_push_card".lower()
        title = config["title"]
        card_type = config.get("type", "text")

        if card_type == "combo":
            options = config.get("options", [])
            card = ComboBoxSettingCard(
                icon=config["icon"],
                title=title,
                options_list=[ConfigItem(label=opt, value=opt) for opt in options]
            )
            if "default" in config:
                card.setValue(config["default"])        
        elif card_type == "key_value":
            card = KeyValueSettingCard(
                icon=config["icon"],
                title=title,
            )
        elif card_type == "code_editor":
            card = CodeEditorSettingCard(
                icon=config["icon"],
                title=title,
            )
            # 设置占位符文本
            if "placeholder" in config:
                card.editor.setPlaceholderText(config["placeholder"])
            # 设置默认值
            if "default" in config:
                card.setValue(config["default"])
        else:  # 默认为 text
            card = TextSettingCard(
                icon=config["icon"],
                title=title,
                input_max_width=320,
                input_placeholder=config.get("placeholder", "")
            )

        card.setObjectName(var_name)
        card.setVisible(False)
        return card

    def _send_test_message(self):
        """发送测试消息到当前选择的通知方式"""
        try:
            selected_method = self.notification_method_opt.getValue()
            if not selected_method:
                self._show_error_message("请先选择通知方式")
                return
                
            # 验证配置
            validation_error = self._validate_push_config(str(selected_method))
            if validation_error:
                self._show_error_message(validation_error)
                return

            pusher = Push(self.ctx)
            test_method = str(selected_method) if selected_method is not None else None

            # 显示发送中的提示
            self._show_success_message("正在发送测试消息...")

            pusher.send(gt('这是一条测试消息'), None, test_method)

        except Exception as e:
            error_msg = f"发送测试消息失败: {str(e)}"
            self._show_error_message(error_msg)
            self.log_error(error_msg)

    def _send_test_all_message(self):
        """发送测试消息到所有已配置的通知方式"""
        try:
            pusher = Push(self.ctx)
            
            # 显示发送中的提示
            self._show_success_message("正在向所有已配置的通知方式发送测试消息...")

            # 不指定test_method，将使用所有已配置的通知方式
            pusher.send(gt('这是一条测试消息（全部通知）'), None, None)
            
            self._show_success_message("已向所有已配置的通知方式发送测试消息")

        except Exception as e:
            error_msg = f"发送测试消息失败: {str(e)}"
            self._show_error_message(error_msg)
            self.log_error(error_msg)

    def _on_email_service_selected(self, text):
        config = PushEmailServices.get_configs(str(text))
        if config:
            # 自动填充SMTP相关卡片
            smtp_server = config["host"]
            smtp_port = config.get("port", 465)
            smtp_ssl = str(config.get("secure", True)).lower() if "secure" in config else "true"
            # 找到对应的TextSettingCard并赋值
            server_card = getattr(self, "smtp_server_push_card", None)
            if server_card:
                server_card.setValue(f"{smtp_server}:{smtp_port}")
            ssl_card = getattr(self, "smtp_ssl_push_card", None)
            if ssl_card:
                ssl_card.setValue(smtp_ssl)

    def _update_notification_ui(self):
        """根据选择的通知方式更新界面"""
        selected_method = self.notification_method_opt.getValue()

        # 隐藏所有卡片
        for method_name, method_cards in self.cards.items():
            is_selected = (method_name == selected_method)
            for card in method_cards:
                # 检查是否是 ExpandGroupSettingCard
                if hasattr(card, 'addGroupWidget'):
                    # 这是一个 ExpandGroupSettingCard，始终保持可见以便交互
                    # 但只在对应的通知方式被选中时才让其内容可见
                    card.setVisible(is_selected)
                else:
                    # 普通卡片，根据选择状态设置可见性
                    card.setVisible(is_selected)

        # 特殊处理邮箱服务下拉框
        self.email_service_opt.setVisible(selected_method == "SMTP")

        # 特殊处理 cURL 生成按钮（仅在 WEBHOOK 模式下显示）
        self.curl_btn.setVisible(selected_method == "WEBHOOK")

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.custom_push_title.init_with_adapter(self.ctx.push_config.get_prop_adapter('custom_push_title'))
        self.send_image_opt.init_with_adapter(self.ctx.push_config.get_prop_adapter('send_image'))

        # 动态初始化所有通知卡片
        for method, configs in PushCards.get_configs().items():
            if method == 'WEBHOOK':
                # Webhook 使用新的带分组的格式
                if configs and isinstance(configs[0], dict) and 'group' in configs[0]:
                    for group_config in configs:
                        for item_config in group_config['items']:
                            var_suffix = item_config["var_suffix"]
                            var_name = f"{method.lower()}_{var_suffix.lower()}_push_card"
                            config_key = f"{method.lower()}_{var_suffix.lower()}"
                            card = getattr(self, var_name, None)
                            if card:
                                card.init_with_adapter(self.ctx.push_config.get_prop_adapter(config_key))
            else:
                # 其他通知方式使用旧的简单格式
                for item_config in configs:
                    var_suffix = item_config["var_suffix"]
                    var_name = f"{method.lower()}_{var_suffix.lower()}_push_card"
                    config_key = f"{method.lower()}_{var_suffix.lower()}"
                    card = getattr(self, var_name, None)
                    if card:
                        card.init_with_adapter(self.ctx.push_config.get_prop_adapter(config_key))

        # 初始更新界面状态
        self._update_notification_ui()

        # 为 webhook URL 添加验证
        webhook_url_card = getattr(self, "webhook_url_push_card", None)
        if webhook_url_card and hasattr(webhook_url_card, 'value_changed'):
            webhook_url_card.value_changed.connect(self._on_webhook_url_changed)

    def _generate_curl(self):
        """生成 cURL 示例命令"""
        try:
            import json
            import datetime
            import time
            from PySide6.QtWidgets import QApplication

            # 获取 webhook 配置
            url_card = getattr(self, "webhook_url_push_card", None)
            method_card = getattr(self, "webhook_method_push_card", None)
            content_type_card = getattr(self, "webhook_content_type_push_card", None)
            headers_card = getattr(self, "webhook_headers_push_card", None)
            body_card = getattr(self, "webhook_body_push_card", None)

            if not url_card:
                self._show_error_message("请先配置 Webhook URL")
                return

            url = url_card.getValue() if hasattr(url_card, 'getValue') else ""
            method = method_card.getValue() if method_card and hasattr(method_card, 'getValue') else "POST"
            content_type = content_type_card.getValue() if content_type_card and hasattr(content_type_card, 'getValue') else "application/json"

            if not url:
                self._show_error_message("Webhook URL 不能为空")
                return

            # 生成示例变量值
            sample_title = "测试通知标题"
            sample_content = "这是一条测试消息内容"
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            iso_timestamp = datetime.datetime.now().isoformat()
            unix_timestamp = str(int(time.time()))

            # 替换模板变量
            replacements = {
                "{{title}}": sample_title,
                "{{content}}": sample_content,
                "{{timestamp}}": timestamp,
                "{{iso_timestamp}}": iso_timestamp,
                "{{unix_timestamp}}": unix_timestamp
            }

            # 构建 cURL 命令
            curl_parts = [f'curl -X {method}']

            # 添加 Content-Type
            if content_type:
                curl_parts.append(f'-H "Content-Type: {content_type}"')

            # 添加自定义 headers
            if headers_card and hasattr(headers_card, 'getValue'):
                headers_str = headers_card.getValue()
                if headers_str:
                    try:
                        # KeyValueSettingCard 返回的是 JSON 字符串格式的字典
                        headers_data = json.loads(headers_str)
                        if isinstance(headers_data, dict):
                            for key, value in headers_data.items():
                                if key and value:
                                    # 替换模板变量
                                    header_value = str(value)
                                    for placeholder, replacement in replacements.items():
                                        header_value = header_value.replace(placeholder, replacement)
                                    curl_parts.append(f'-H "{key}: {header_value}"')
                        elif isinstance(headers_data, list):
                            # 兼容旧的列表格式
                            for item in headers_data:
                                if isinstance(item, dict):
                                    key = item.get("key", "")
                                    value = item.get("value", "")
                                    if key and value:
                                        # 替换模板变量
                                        header_value = str(value)
                                        for placeholder, replacement in replacements.items():
                                            header_value = header_value.replace(placeholder, replacement)
                                        curl_parts.append(f'-H "{key}: {header_value}"')
                    except (json.JSONDecodeError, TypeError):
                        # 如果解析失败，忽略headers
                        pass

            # 添加请求体
            if body_card and hasattr(body_card, 'getValue'):
                body = body_card.getValue()
                if body:
                    # 替换模板变量
                    for placeholder, replacement in replacements.items():
                        body = body.replace(placeholder, replacement)
                    # 转义引号
                    body = body.replace('"', '\\"')
                    curl_parts.append(f'-d "{body}"')

            # 替换 URL 中的模板变量
            for placeholder, replacement in replacements.items():
                url = url.replace(placeholder, replacement)

            # 添加 URL（放在最后）
            curl_parts.append(f'"{url}"')

            # 拼接完整命令
            curl_command = ' \\\n  '.join(curl_parts)

            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setText(curl_command)

            # 显示成功提示
            self._show_success_message("cURL 命令已复制到剪贴板！")
            self.log_info(f"cURL 命令已复制到剪贴板:\n{curl_command}")

        except Exception as e:
            error_msg = f"生成 cURL 命令失败: {str(e)}"
            self._show_error_message(error_msg)
            self.log_error(error_msg)

    def log_info(self, message: str):
        """记录信息日志"""
        log.info(message)

    def log_error(self, message: str):
        """记录错误日志"""
        log.error(message)

    def _show_success_message(self, message: str):
        """显示成功消息提示"""
        try:
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(
                title='成功',
                content=message,
                orient=InfoBarPosition.TOP,
                isClosable=True,
                duration=3000,
                parent=self
            )
        except ImportError:
            # 如果没有 InfoBar，就用日志代替
            self.log_info(message)

    def _show_error_message(self, message: str):
        """显示错误消息提示"""
        try:
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.error(
                title='错误',
                content=message,
                orient=InfoBarPosition.TOP,
                isClosable=True,
                duration=5000,
                parent=self
            )
        except ImportError:
            # 如果没有 InfoBar，就用日志代替
            self.log_error(message)

    def _validate_push_config(self, method: str) -> str:
        """验证推送配置，返回错误信息或空字符串"""
        if method == "WEBHOOK":
            return self._validate_webhook_config()
        elif method == "TG":
            return self._validate_telegram_config()
        elif method == "SMTP":
            return self._validate_smtp_config()
        return ""

    def _validate_webhook_config(self) -> str:
        """验证 Webhook 配置，返回错误信息或空字符串"""
        # 获取各个配置卡片
        url_card = getattr(self, "webhook_url_push_card", None)
        body_card = getattr(self, "webhook_body_push_card", None)
        
        # 验证 URL
        if not url_card:
            return "找不到 Webhook URL 配置项"
        
        url = url_card.getValue() if hasattr(url_card, 'getValue') else ""
        if not url:
            return "请先配置 Webhook URL"
        
        if not self._validate_webhook_url(url):
            return "Webhook URL 格式不正确，请检查是否包含 http:// 或 https://"
        
        # 验证请求体中的变量
        if body_card and hasattr(body_card, 'getValue'):
            body = body_card.getValue()
            if body:
                # 检查是否包含必需的变量
                has_old_vars = ("$title" in url or "$title" in body or 
                               "$content" in url or "$content" in body)
                has_new_vars = ("{{title}}" in url or "{{title}}" in body or
                               "{{content}}" in url or "{{content}}" in body)
                
                if not has_old_vars and not has_new_vars:
                    return "请求头或者请求体中必须包含 $title/$content 或 {{title}}/{{content}} 变量"
        
        return ""  # 验证通过

    def _validate_telegram_config(self) -> str:
        """验证 Telegram 配置"""
        token_card = getattr(self, "tg_bot_token_push_card", None)
        user_id_card = getattr(self, "tg_user_id_push_card", None)
        
        if not token_card or not token_card.getValue():
            return "请先配置 Telegram Bot Token"
        
        if not user_id_card or not user_id_card.getValue():
            return "请先配置 Telegram User ID"
        
        return ""

    def _validate_smtp_config(self) -> str:
        """验证 SMTP 配置"""
        server_card = getattr(self, "smtp_server_push_card", None)
        email_card = getattr(self, "smtp_email_push_card", None)
        password_card = getattr(self, "smtp_password_push_card", None)
        
        if not server_card or not server_card.getValue():
            return "请先配置 SMTP 服务器"
        
        if not email_card or not email_card.getValue():
            return "请先配置发送邮箱"
        
        if not password_card or not password_card.getValue():
            return "请先配置邮箱密码"
        
        return ""

    def _validate_webhook_url(self, url: str) -> bool:
        """验证 Webhook URL 格式"""
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// 或 https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # 域名
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP地址
            r'(?::\d+)?'  # 可选端口
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None

    def _on_webhook_url_changed(self, url: str):
        """当 Webhook URL 改变时的处理"""
        if url and not self._validate_webhook_url(url):
            self._show_error_message("URL 格式不正确，请检查是否包含 http:// 或 https://")
