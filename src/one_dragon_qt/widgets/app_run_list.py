from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal

from one_dragon.base.operation.application.application_group_config import (
    ApplicationGroupConfigItem,
)
from one_dragon_qt.widgets.draggable_list import DraggableList
from one_dragon_qt.widgets.setting_card.app_run_card import AppRunCard

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class AppRunList(DraggableList):
    """
    一条龙应用列表

    支持通过拖拽来调整应用执行顺序，并提供应用状态管理。

    Signals:
        app_list_changed(list[ApplicationGroupConfigItem]): 应用列表顺序改变时触发
        app_run_clicked(str): 运行某个应用时触发，参数为 app_id
        app_switch_changed(str, bool): 应用开关状态改变时触发，参数为 app_id 和 状态
        app_setting_clicked(str): 点击应用设置按钮时触发，参数为 app_id
    """

    # 应用列表改变信号（拖拽排序后触发）
    app_list_changed = Signal(list)

    # 运行某个应用
    app_run_clicked = Signal(str)

    # 应用开关状态改变
    app_switch_changed = Signal(str, bool)

    # 点击应用设置按钮
    app_setting_clicked = Signal(str)

    def __init__(self, ctx: OneDragonContext, parent=None, enable_opacity_effect: bool = True):
        """
        初始化一条龙应用列表

        Args:
            ctx: 上下文对象
            parent: 父组件
            enable_opacity_effect: 是否启用拖拽透明度效果（默认 True）
                在 MessageBoxBase 等对话框中建议设为 False，避免位置偏移
        """
        self.ctx: OneDragonContext = ctx
        self._enable_opacity_effect: bool = enable_opacity_effect

        # 调用父类初始化，传递透明度效果设置
        super().__init__(parent=parent, enable_opacity_effect=enable_opacity_effect)

        # 设置行间隔为 0
        self._layout.setSpacing(0)

        # 存储应用卡片
        self._app_cards: list[AppRunCard] = []

        # 连接父类的拖拽排序信号
        self.order_changed.connect(self._handle_order_changed)

    def set_app_list(
        self,
        app_list: list[ApplicationGroupConfigItem],
        instance_idx: int
    ) -> None:
        """
        设置应用列表

        Args:
            app_list: 应用配置列表
            instance_idx: 实例索引
        """
        # 如果已有卡片且数量一致，更新现有卡片（更高效）
        if len(self._app_cards) > 0 and len(self._app_cards) == len(app_list):
            self._update_existing_cards(app_list, instance_idx)
        else:
            # 数量不一致或首次创建，重建整个列表
            self._create_new_cards(app_list, instance_idx)

    def _update_existing_cards(
        self,
        app_list: list[ApplicationGroupConfigItem],
        instance_idx: int
    ) -> None:
        """
        更新现有的卡片（当卡片数量一致时，只更新数据）

        Args:
            app_list: 应用配置列表
            instance_idx: 实例索引
        """
        for idx, app in enumerate(app_list):
            if idx < len(self._app_cards):
                card = self._app_cards[idx]
                card.update_item(app, idx)
                run_record = self.ctx.run_context.get_run_record(
                    app_id=app.app_id,
                    instance_idx=instance_idx
                )
                card.set_app(app, run_record)
                card.set_switch_on(app.enabled)

    def _create_new_cards(
        self,
        app_list: list[ApplicationGroupConfigItem],
        instance_idx: int
    ) -> None:
        """
        创建新的卡片列表

        Args:
            app_list: 应用配置列表
            instance_idx: 实例索引
        """
        self._app_cards.clear()
        self.clear()

        for idx, app in enumerate(app_list):
            run_record = self.ctx.run_context.get_run_record(
                app_id=app.app_id,
                instance_idx=instance_idx
            )
            card = AppRunCard(
                app=app,
                index=idx,
                run_record=run_record,
                switch_on=app.enabled,
                enable_opacity_effect=self._enable_opacity_effect,
            )
            self._app_cards.append(card)
            self.add_list_item(card)

            # 移除卡片的 margins，使列表项之间没有间距
            card.layout().setContentsMargins(0, 0, 0, 0)

            card.update_display()

            # 连接信号
            card.move_top.connect(self._on_app_move_top)
            card.run.connect(self.app_run_clicked.emit)
            card.switched.connect(self.app_switch_changed.emit)
            card.setting_clicked.connect(self.app_setting_clicked.emit)

    def update_cards_display(self) -> None:
        """
        更新所有卡片的显示状态（用于刷新运行状态）
        """
        for card in self._app_cards:
            card.update_display()

    def _on_app_move_top(self, app_id: str) -> None:
        """
        应用置顶处理

        Args:
            app_id: 应用ID
        """
        # 找到对应应用的索引
        for idx, card in enumerate(self._app_cards):
            if card.app.app_id == app_id:
                if idx > 0:  # 不在第一位时才需要置顶
                    # 更新 _app_cards 列表
                    self._app_cards.pop(idx)
                    self._app_cards.insert(0, card)

                    # 同步更新父类的 _items 列表
                    self._items.pop(idx)
                    self._items.insert(0, card)

                    # 更新索引
                    for i, c in enumerate(self._app_cards):
                        c.update_item(c.data, i)

                    # 重新构建布局
                    self._rebuild_layout()

                    # 触发信号
                    new_app_list = [card.app for card in self._app_cards]
                    self.app_list_changed.emit(new_app_list)
                break

    def _handle_order_changed(self, new_data_list: list) -> None:
        """
        拖拽排序改变后的回调

        Args:
            new_data_list: 新顺序的数据列表
        """
        # 重新构建 _app_cards 的顺序
        new_card_list: list[AppRunCard] = []
        for data in new_data_list:
            for card in self._app_cards:
                if card.data == data:
                    new_card_list.append(card)
                    break
        self._app_cards = new_card_list

        # 更新所有卡片的索引
        for idx, card in enumerate(self._app_cards):
            card.update_item(card.data, idx)

        # 触发应用列表改变信号
        new_app_list = [card.app for card in self._app_cards]
        self.app_list_changed.emit(new_app_list)
