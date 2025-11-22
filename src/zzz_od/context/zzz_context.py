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
            if hasattr(self, prop):
                delattr(self, prop)

    def init_controller(self) -> None:
        from one_dragon.base.config.game_account_config import GamePlatformEnum
        from zzz_od.controller.zzz_pc_controller import ZPcController
        if self.game_account_config.platform == GamePlatformEnum.PC.value.value:
            if self.game_account_config.use_custom_win_title:
                win_title = self.game_account_config.custom_win_title
            else:
                from one_dragon.base.config.game_account_config import GameRegionEnum
                win_title = '绝区零' if self.game_account_config.game_region == GameRegionEnum.CN.value.value else 'ZenlessZoneZero'
            self.controller: ZPcController = ZPcController(
                game_config=self.game_config,
                win_title=win_title,
                screenshot_method=self.env_config.screenshot_method,
                standard_width=self.project_config.screen_standard_width,
                standard_height=self.project_config.screen_standard_height
            )

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

    def register_application_factory(self) -> None:
        """
        注册应用

        Returns:
            None
        """
        from zzz_od.application.battle_assistant.auto_battle.auto_battle_app_factory import (
            AutoBattleAppFactory,
        )
        from zzz_od.application.battle_assistant.dodge_assitant.dodge_assistant_factory import (
            DodgeAssistantFactory,
        )
        from zzz_od.application.battle_assistant.operation_debug.operation_debug_app_factory import (
            OperationDebugAppFactory,
        )
        from zzz_od.application.commission_assistant.commission_assistant_app_factory import (
            CommissionAssistantAppFactory,
        )
        from zzz_od.application.devtools.screenshot_helper.screenshot_helper_app_factory import (
            ScreenshotHelperAppFactory,
        )
        from zzz_od.application.game_config_checker.mouse_sensitivity_checker_factoru import (
            MouseSensitivityCheckerFactory,
        )
        from zzz_od.application.game_config_checker.predefined_team_checker_factory import (
            PredefinedTeamCheckerFactory,
        )
        from zzz_od.application.one_dragon_app.zzz_one_dragon_app_factory import (
            ZzzOneDragonAppFactory,
        )
        self.run_context.registry_application(
            [
                ZzzOneDragonAppFactory(self),
                AutoBattleAppFactory(self),
                DodgeAssistantFactory(self),
                OperationDebugAppFactory(self),
                ScreenshotHelperAppFactory(self),
                CommissionAssistantAppFactory(self),
                PredefinedTeamCheckerFactory(self),
                MouseSensitivityCheckerFactory(self),
            ],
            default_group=False,
        )

        from zzz_od.application.charge_plan.charge_plan_app_factory import (
            ChargePlanAppFactory,
        )
        from zzz_od.application.city_fund.city_fund_app_factory import (
            CityFundAppFactory,
        )
        from zzz_od.application.coffee.coffee_app_factory import CoffeeAppFactory
        from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_app_factory import (
            DriveDiscDismantleAppFactory,
        )
        from zzz_od.application.email_app.email_app_factory import EmailAppFactory
        from zzz_od.application.engagement_reward.engagement_reward_app_factory import (
            EngagementRewardAppFactory,
        )
        from zzz_od.application.hollow_zero.lost_void.lost_void_app_factory import (
            LostVoidAppFactory,
        )
        from zzz_od.application.hollow_zero.withered_domain.withered_domain_app_factory import (
            WitheredDomainAppFactory,
        )
        from zzz_od.application.life_on_line.life_on_line_app_factory import (
            LifeOneLineAppFactory,
        )
        from zzz_od.application.notify.notify_app_factory import NotifyAppFactory
        from zzz_od.application.notorious_hunt.notorious_hunt_factory import (
            NotoriousHuntAppFactory,
        )
        from zzz_od.application.random_play.random_play_factory import (
            RandomPlayFactory,
        )
        from zzz_od.application.redemption_code.redemption_code_factory import (
            RedemptionCodeFactory,
        )
        from zzz_od.application.ridu_weekly.ridu_weekly_app_factory import (
            RiduWeeklyAppFactory,
        )
        from zzz_od.application.scratch_card.scratch_card_factory import (
            ScratchCardFactory,
        )
        from zzz_od.application.shiyu_defense.shiyu_defense_app_factory import (
            ShiyuDefenseAppFactory,
        )
        from zzz_od.application.suibian_temple.suibian_temple_factory import (
            SuibianTempleFactory,
        )
        from zzz_od.application.trigrams_collection.trigrams_collection_factory import (
            TrigramsCollectionFactory,
        )
        from zzz_od.application.world_patrol.world_patrol_factory import (
            WorldPatrolAppFactory,
        )
        self.run_context.registry_application(
            [
                RedemptionCodeFactory(self),
                EmailAppFactory(self),
                RandomPlayFactory(self),
                TrigramsCollectionFactory(self),
                SuibianTempleFactory(self),
                ScratchCardFactory(self),
                CoffeeAppFactory(self),
                ChargePlanAppFactory(self),
                NotoriousHuntAppFactory(self),
                EngagementRewardAppFactory(self),
                CityFundAppFactory(self),
                WitheredDomainAppFactory(self),
                RiduWeeklyAppFactory(self),
                DriveDiscDismantleAppFactory(self),
                LostVoidAppFactory(self),
                NotifyAppFactory(self),
                WorldPatrolAppFactory(self),
                LifeOneLineAppFactory(self),
                ShiyuDefenseAppFactory(self),
            ],
            default_group=True,
        )
