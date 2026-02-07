from __future__ import annotations

from functools import cached_property

from one_dragon.base.operation.one_dragon_context import OneDragonContext


class ZContext(OneDragonContext):

    def __init__(self,):

        OneDragonContext.__init__(self)

        # 后续所有用到自动战斗的 都统一设置到这个里面
        from zzz_od.auto_battle.auto_battle_context import AutoBattleContext
        self.auto_battle_context: AutoBattleContext = AutoBattleContext(self)

    #------------------- 需要懒加载的都使用 @cached_property -------------------#

    #------------------- 以下是 游戏/脚本级别的 -------------------#

    @cached_property
    def model_config(self):
        from zzz_od.config.model_config import ModelConfig
        return ModelConfig()

    @cached_property
    def map_service(self):
        from zzz_od.game_data.map_area import MapAreaService
        return MapAreaService()

    @cached_property
    def compendium_service(self):
        from zzz_od.game_data.compendium import CompendiumService
        return CompendiumService()

    @cached_property
    def world_patrol_service(self):
        from zzz_od.application.world_patrol.world_patrol_service import (
            WorldPatrolService,
        )
        return WorldPatrolService(self)

    @cached_property
    def telemetry(self):
        from zzz_od.telemetry.telemetry_manager import TelemetryManager
        return TelemetryManager(self)

    @cached_property
    def lost_void(self):
        from zzz_od.application.hollow_zero.lost_void.context.lost_void_context import (
            LostVoidContext,
        )
        return LostVoidContext(self)

    @cached_property
    def withered_domain(self):
        from zzz_od.application.hollow_zero.withered_domain.withered_domain_context import (
            WitheredDomainContext,
        )
        return WitheredDomainContext(self)

    #------------------- 以下是 账号实例级别的 需要在 reload_instance_config 中刷新 -------------------#

    @cached_property
    def game_config(self):
        from zzz_od.config.game_config import GameConfig
        return GameConfig(self.current_instance_idx)

    @cached_property
    def team_config(self):
        from zzz_od.config.team_config import TeamConfig
        return TeamConfig(self.current_instance_idx)

    @cached_property
    def battle_assistant_config(self):
        from zzz_od.application.battle_assistant.battle_assistant_config import (
            BattleAssistantConfig,
        )
        return BattleAssistantConfig(self.current_instance_idx)

    def reload_instance_config(self) -> None:
        OneDragonContext.reload_instance_config(self)

        to_clear_props = [
            'game_config',
            'team_config',
            'battle_assistant_config',
        ]
        for prop in to_clear_props:
            if prop in self.__dict__:
                del self.__dict__[prop]

    def _get_win_title(self) -> str:
        """获取当前配置对应的窗口标题"""
        if self.game_account_config.use_custom_win_title:
            return self.game_account_config.custom_win_title
        from one_dragon.base.config.game_account_config import GameRegionEnum
        return '绝区零' if self.game_account_config.game_region == GameRegionEnum.CN.value.value else 'ZenlessZoneZero'

    def on_switch_instance(self) -> None:
        """
        切换实例后更新 controller 的窗口标题
        """
        if self.controller is not None:
            new_win_title = self._get_win_title()
            self.controller.set_window_title(new_win_title)

    def init_controller(self) -> None:
        from one_dragon.base.config.game_account_config import GamePlatformEnum
        from zzz_od.controller.zzz_pc_controller import ZPcController
        if self.game_account_config.platform == GamePlatformEnum.PC.value.value:
            self.controller: ZPcController = ZPcController(
                game_config=self.game_config,
                screenshot_method=self.env_config.screenshot_method,
                standard_width=self.project_config.screen_standard_width,
                standard_height=self.project_config.screen_standard_height
            )
            # 初始化窗口标题
            self.controller.set_window_title(self._get_win_title())

    def init_for_application(self) -> None:
        self.map_service.reload()  # 传送需要用的数据
        self.compendium_service.reload()  # 快捷手册
        self.auto_battle_context.init_screen_area()  # 自动战斗相关的区域 依赖 ScreenLoader

    def init_others(self) -> None:
        self.telemetry.initialize()  # 遥测

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        """
        if hasattr(self, 'telemetry') and self.telemetry:
            self.telemetry.shutdown()

        OneDragonContext.after_app_shutdown(self)
        self.withered_domain.after_app_shutdown()
        self.auto_battle_context.after_app_shutdown()

        from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
        AutoBattleOperator.after_app_shutdown()

    @cached_property
    def shared_dialog_manager(self):
        """
        获取共享的Dialog管理器

        Returns:
            SharedDialogManager: 共享的Dialog管理器
        """
        from zzz_od.gui.dialog.shared_dialog_manager import SharedDialogManager
        return SharedDialogManager(self)
