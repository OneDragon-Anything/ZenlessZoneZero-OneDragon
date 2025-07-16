from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from zzz_od.application.notify.notify_config import NotifyMethodEnum, NotifyCard
from zzz_od.context.zzz_context import ZContext
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard

class ZOneDragonNotifySettingInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='zzz_one_dragon_notify_setting_interface',
            content_widget=None, parent=parent,
            nav_text_cn='通知设置'
        )
        self.ctx: ZContext = ctx

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        # 通知方式选择
        self.notification_method_opt = ComboBoxSettingCard(
            icon=FluentIcon.MESSAGE,
            title=gt('通知方式'),
            options_enum=NotifyMethodEnum
        )
        self.notification_method_opt.combo_box.currentIndexChanged.connect(self._update_notification_ui)
        content_widget.add_widget(self.notification_method_opt)

        self.cards = {} 
        for method, configs in NotifyCard.configs.items():
            method_cards = []
            
            for config in configs:
                # 动态生成变量名（如：tg_bot_token_card）
                var_name = f"{method}_{config['var_suffix']}_notify_card".lower()
                title=config["title"]
                # 创建卡片实例
                card = TextSettingCard(
                    icon=config["icon"],
                    title=title,
                    input_placeholder=config["placeholder"]
                )
                
                # 设置关键属性
                card.setObjectName(var_name.lower())  # 设置唯一标识
                card.setVisible(False)        # 初始状态隐藏
                
                # 将卡片存入实例变量
                setattr(self, var_name, card)
                method_cards.append(card)
            
            # 按方法分组存储
            self.cards[method] = method_cards
        
        # 将卡片添加到界面布局（根据实际布局调整）
        for cards in self.cards.values():
            for card in cards:
                content_widget.add_widget(card)
            
        content_widget.add_stretch(1)

        return content_widget

    def _update_notification_ui(self):
        """根据选择的通知方式更新界面"""
        method = self.notification_method_opt.combo_box.currentData()
        # 隐藏所有配置项
        for widget in self.findChildren(TextSettingCard):
            if widget.objectName().endswith("_notify_card"):
                widget.setVisible(False)

        prefix = f"{method.lower()}_"
        for widget in self.findChildren(TextSettingCard):
            if widget.objectName().startswith(prefix):
                widget.setVisible(True)

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.notification_method_opt.init_with_adapter(
            self.ctx.notify_config.get_prop_adapter('notify_method')
        )

        # 动态初始化所有通知卡片
        for method_group, configs in NotifyCard.configs.items():
            for config in configs:
                var_suffix = config["var_suffix"]
                var_name = f"{method_group.lower()}_{var_suffix.lower()}_notify_card"
                config_key = f"{method_group.lower()}_{var_suffix.lower()}"
                
                card = getattr(self, var_name, None)
                if card:
                    card.init_with_adapter(self.ctx.notify_config.get_prop_adapter(config_key))
                else:
                    print(f"未找到卡片: {var_name}")
    
        # 初始更新界面状态
        self._update_notification_ui()
