from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.base.operation.application.application_factory import ApplicationFactory
from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.battle_assistant.dodge_assitant import dodge_assistant_const
from zzz_od.application.battle_assistant.dodge_assitant.dodge_assistant_app import (
    DodgeAssistantApp,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class DodgeAssistantFactory(ApplicationFactory):
    """
    闪避助手工厂类。

    继承自ApplicationFactory，负责创建闪避助手应用实例。
    闪避助手用于在战斗中自动检测并执行闪避操作，提高游戏体验。

    Attributes:
        ctx: 绝区零游戏上下文，提供游戏状态和操作接口
    """

    def __init__(self, ctx: ZContext):
        """
        初始化闪避助手工厂。

        Args:
            ctx: 绝区零游戏上下文，提供游戏状态和操作接口
        """
        ApplicationFactory.__init__(
            self,
            app_id=dodge_assistant_const.APP_ID,
            app_name=dodge_assistant_const.APP_NAME,
        )
        self.ctx: ZContext = ctx

    def create_application(self, instance_idx: int, group_id: str) -> Application:
        """
        创建闪避助手应用实例。

        创建并返回一个闪避助手应用实例，用于自动闪避功能。

        Args:
            instance_idx: 账号实例下标
            group_id: 应用组ID，可将应用分组运行

        Returns:
            Application: 闪避助手应用实例
        """
        return DodgeAssistantApp(self.ctx)

    def create_config(
        self, instance_idx: int, group_id: str
    ) -> Optional[ApplicationConfig]:
        """
        创建应用配置实例。

        闪避助手目前不需要额外的配置，因此返回None。

        Args:
            instance_idx: 账号实例下标
            group_id: 应用组ID，不同应用组可以有不同的应用配置

        Returns:
            Optional[ApplicationConfig]: 配置实例，闪避助手返回None
        """
        return None

    def create_run_record(self, instance_idx: int) -> Optional[AppRunRecord]:
        """
        创建运行记录实例。

        闪避助手目前不需要运行记录功能，因此返回None。

        Args:
            instance_idx: 账号实例下标

        Returns:
            Optional[AppRunRecord]: 运行记录实例，闪避助手返回None
        """
        return None