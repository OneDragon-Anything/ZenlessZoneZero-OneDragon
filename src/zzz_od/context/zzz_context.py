from typing import Optional

from one_dragon.base.operation.one_dragon_context import OneDragonContext
from zzz_od.game_data.agent import AgentEnum


class ZContext(OneDragonContext):

    def __init__(self,):
        OneDragonContext.__init__(self)

        from zzz_od.context.hollow_context import HollowContext
        self.hollow: HollowContext = HollowContext(self)
        from zzz_od.application.hollow_zero.lost_void.context.lost_void_context import LostVoidContext
        self.lost_void: LostVoidContext = LostVoidContext(self)

        # 基础配置
        from zzz_od.config.model_config import ModelConfig
        self.model_config: ModelConfig = ModelConfig()

        # 游戏数据
        from zzz_od.game_data.map_area import MapAreaService
        self.map_service: MapAreaService = MapAreaService()  # 这是
        from zzz_od.game_data.compendium import CompendiumService
        self.compendium_service: CompendiumService = CompendiumService()
        from zzz_od.application.world_patrol.world_patrol_service import WorldPatrolService
        self.world_patrol_service: WorldPatrolService = WorldPatrolService(self)

        # 服务
        from one_dragon.base.cv_process.cv_service import CvService
        self.cv_service: CvService = CvService(self)

        from zzz_od.telemetry.telemetry_manager import TelemetryManager
        self.telemetry: TelemetryManager = TelemetryManager(self)

        # 后续所有用到自动战斗的 都统一设置到这个里面
        from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
        self.auto_op: AutoBattleOperator | None = None

        # 实例独有的配置
        self.load_instance_config()

    def load_instance_config(self) -> None:
        OneDragonContext.load_instance_config(self)

        from zzz_od.config.game_config import GameConfig
        self.game_config: GameConfig = GameConfig(self.current_instance_idx)
        from one_dragon.base.config.game_account_config import GameAccountConfig
        self.game_account_config: GameAccountConfig = GameAccountConfig(self.current_instance_idx)

        from zzz_od.application.battle_assistant.battle_assistant_config import BattleAssistantConfig
        from zzz_od.application.charge_plan.charge_plan_config import ChargePlanConfig
        from zzz_od.application.charge_plan.charge_plan_run_record import ChargePlanRunRecord
        from zzz_od.application.city_fund.city_fund_run_record import CityFundRunRecord
        from zzz_od.application.coffee.coffee_config import CoffeeConfig
        from zzz_od.application.coffee.coffee_run_record import CoffeeRunRecord
        from zzz_od.application.devtools.screenshot_helper.screenshot_helper_config import ScreenshotHelperConfig
        from zzz_od.application.email_app.email_run_record import EmailRunRecord
        from zzz_od.application.engagement_reward.engagement_reward_run_record import EngagementRewardRunRecord
        from zzz_od.application.hollow_zero.withered_domain.hollow_zero_config import HollowZeroConfig
        from zzz_od.application.hollow_zero.withered_domain.hollow_zero_run_record import HollowZeroRunRecord
        from zzz_od.application.life_on_line.life_on_line_config import LifeOnLineConfig
        from zzz_od.application.life_on_line.life_on_line_run_record import LifeOnLineRunRecord
        from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntConfig
        from zzz_od.application.notorious_hunt.notorious_hunt_run_record import NotoriousHuntRunRecord
        from zzz_od.application.random_play.random_play_run_record import RandomPlayRunRecord
        from zzz_od.application.scratch_card.scratch_card_run_record import ScratchCardRunRecord
        from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig
        from zzz_od.application.redemption_code.redemption_code_run_record import RedemptionCodeRunRecord
        from zzz_od.application.commission_assistant.commission_assistant_config import CommissionAssistantConfig
        from zzz_od.config.team_config import TeamConfig
        self.team_config: TeamConfig = TeamConfig(self.current_instance_idx)

        # 应用配置
        self.screenshot_helper_config: ScreenshotHelperConfig = ScreenshotHelperConfig(self.current_instance_idx)
        self.battle_assistant_config: BattleAssistantConfig = BattleAssistantConfig(self.current_instance_idx)
        self.charge_plan_config: ChargePlanConfig = ChargePlanConfig(self.current_instance_idx)
        self.notorious_hunt_config: NotoriousHuntConfig = NotoriousHuntConfig(self.current_instance_idx)
        self.hollow_zero_config: HollowZeroConfig = HollowZeroConfig(self.current_instance_idx)
        self.hollow_zero_challenge_config: Optional[HollowZeroChallengeConfig] = None
        self.coffee_config: CoffeeConfig = CoffeeConfig(self.current_instance_idx)
        self.life_on_line_config: LifeOnLineConfig = LifeOnLineConfig(self.current_instance_idx)
        self.commission_assistant_config: CommissionAssistantConfig = CommissionAssistantConfig(self.current_instance_idx)
        from zzz_od.application.random_play.random_play_config import RandomPlayConfig
        self.random_play_config: RandomPlayConfig = RandomPlayConfig(self.current_instance_idx)

        from zzz_od.config.agent_outfit_config import AgentOutfitConfig
        self.agent_outfit_config: AgentOutfitConfig = AgentOutfitConfig(self.current_instance_idx)

        # 运行记录
        game_refresh_hour_offset = self.game_account_config.game_refresh_hour_offset
        self.email_run_record: EmailRunRecord = EmailRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        self.email_run_record.check_and_update_status()
        self.random_play_run_record: RandomPlayRunRecord = RandomPlayRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        self.random_play_run_record.check_and_update_status()
        self.scratch_card_run_record: ScratchCardRunRecord = ScratchCardRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        self.scratch_card_run_record.check_and_update_status()
        self.charge_plan_run_record: ChargePlanRunRecord = ChargePlanRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        self.charge_plan_run_record.check_and_update_status()
        self.engagement_reward_run_record: EngagementRewardRunRecord = EngagementRewardRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        self.engagement_reward_run_record.check_and_update_status()
        self.notorious_hunt_record: NotoriousHuntRunRecord = NotoriousHuntRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        self.notorious_hunt_record.check_and_update_status()
        self.hollow_zero_record: HollowZeroRunRecord = HollowZeroRunRecord(self.hollow_zero_config, self.current_instance_idx, game_refresh_hour_offset)
        self.hollow_zero_record.check_and_update_status()
        self.coffee_record: CoffeeRunRecord = CoffeeRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        self.coffee_record.check_and_update_status()
        self.city_fund_record: CityFundRunRecord = CityFundRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        self.city_fund_record.check_and_update_status()
        self.life_on_line_record: LifeOnLineRunRecord = LifeOnLineRunRecord(self.life_on_line_config, self.current_instance_idx, game_refresh_hour_offset)
        self.life_on_line_record.check_and_update_status()
        self.redemption_code_record: RedemptionCodeRunRecord = RedemptionCodeRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        self.redemption_code_record.check_and_update_status()
        from zzz_od.application.trigrams_collection.trigrams_collection_record import TrigramsCollectionRunRecord
        self.trigrams_collection_record: TrigramsCollectionRunRecord = TrigramsCollectionRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        self.trigrams_collection_record.check_and_update_status()

        from zzz_od.application.ridu_weekly.ridu_weekly_run_record import RiduWeeklyRunRecord
        self.ridu_weekly_record: RiduWeeklyRunRecord = RiduWeeklyRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        self.ridu_weekly_record.check_and_update_status()

        from zzz_od.application.shiyu_defense.shiyu_defense_config import ShiyuDefenseConfig
        self.shiyu_defense_config: ShiyuDefenseConfig = ShiyuDefenseConfig(self.current_instance_idx)
        from zzz_od.application.shiyu_defense.shiyu_defense_run_record import ShiyuDefenseRunRecord
        self.shiyu_defense_record: ShiyuDefenseRunRecord = ShiyuDefenseRunRecord(self.shiyu_defense_config, self.current_instance_idx, game_refresh_hour_offset)

        from zzz_od.application.miscellany.miscellany_run_record import MiscellanyRunRecord
        self.miscellany_record: MiscellanyRunRecord = MiscellanyRunRecord(self.current_instance_idx, game_refresh_hour_offset)
        from zzz_od.application.miscellany.miscellany_config import MiscellanyConfig
        self.miscellany_config: MiscellanyConfig = MiscellanyConfig(self.current_instance_idx)

        from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_config import DriveDiscDismantleConfig
        self.drive_disc_dismantle_config: DriveDiscDismantleConfig = DriveDiscDismantleConfig(self.current_instance_idx)
        from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_run_record import DriveDiscDismantleRunRecord
        self.drive_disc_dismantle_record: DriveDiscDismantleRunRecord = DriveDiscDismantleRunRecord(self.current_instance_idx, game_refresh_hour_offset)

        from zzz_od.config.notify_config import NotifyConfig
        self.notify_config: NotifyConfig = NotifyConfig(self.current_instance_idx)
        from zzz_od.application.notify.notify_run_record import NotifyRunRecord
        self.notify_record: NotifyRunRecord = NotifyRunRecord(self.current_instance_idx, game_refresh_hour_offset)

        from zzz_od.application.hollow_zero.lost_void.lost_void_config import LostVoidConfig
        self.lost_void_config: LostVoidConfig = LostVoidConfig(self.current_instance_idx)
        from zzz_od.application.hollow_zero.lost_void.lost_void_run_record import LostVoidRunRecord
        self.lost_void_record: LostVoidRunRecord = LostVoidRunRecord(self.lost_void_config, self.current_instance_idx, game_refresh_hour_offset)

        from zzz_od.application.suibian_temple.suibian_temple_run_record import SuibianTempleRunRecord
        self.suibian_temple_record: SuibianTempleRunRecord = SuibianTempleRunRecord(self.current_instance_idx, game_refresh_hour_offset)

        from zzz_od.application.world_patrol.world_patrol_config import WorldPatrolConfig
        self.world_patrol_config: WorldPatrolConfig = WorldPatrolConfig(self.current_instance_idx)
        from zzz_od.application.world_patrol.world_patrol_run_record import WorldPatrolRunRecord
        self.world_patrol_run_record: WorldPatrolRunRecord = WorldPatrolRunRecord(self.current_instance_idx, game_refresh_hour_offset)

        self.init_by_config()

        self.telemetry.initialize()

    def init_by_config(self) -> None:
        """
        根据配置进行初始化
        :return:
        """
        OneDragonContext.init_by_config(self)

        from zzz_od.controller.zzz_pc_controller import ZPcController
        from one_dragon.base.config.game_account_config import GamePlatformEnum
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

        self.hollow.data_service.reload()
        self.init_hollow_config()
        if self.agent_outfit_config.compatibility_mode:
            self.init_agent_template_id()
        else:
            self.init_agent_template_id_list()

    def init_hollow_config(self) -> None:
        """
        对空洞配置进行初始化
        :return:
        """
        from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig
        challenge_config = self.hollow_zero_config.challenge_config
        if challenge_config is None:
            self.hollow_zero_challenge_config = HollowZeroChallengeConfig('', is_mock=True)
        else:
            self.hollow_zero_challenge_config = HollowZeroChallengeConfig(challenge_config)

    def init_agent_template_id(self) -> None:
        """
        代理人头像模板ID的初始化
        :return:
        """
        AgentEnum.NICOLE.value.template_id_list = [self.agent_outfit_config.nicole]
        AgentEnum.ELLEN.value.template_id_list = [self.agent_outfit_config.ellen]
        AgentEnum.ASTRA_YAO.value.template_id_list = [self.agent_outfit_config.astra_yao]
        AgentEnum.YIXUAN.value.template_id_list = [self.agent_outfit_config.yixuan]
        AgentEnum.YUZUHA.value.template_id_list = [self.agent_outfit_config.yuzuha]
        AgentEnum.ALICE.value.template_id_list = [self.agent_outfit_config.alice]

    def init_agent_template_id_list(self) -> None:
        """
        代理人头像模板ID的初始化
        :return:
        """
        AgentEnum.NICOLE.value.template_id_list = self.agent_outfit_config.nicole_outfit_list
        AgentEnum.ELLEN.value.template_id_list = self.agent_outfit_config.ellen_outfit_list
        AgentEnum.ASTRA_YAO.value.template_id_list = self.agent_outfit_config.astra_yao_outfit_list
        AgentEnum.YIXUAN.value.template_id_list = self.agent_outfit_config.yixuan_outfit_list
        AgentEnum.YUZUHA.value.template_id_list = self.agent_outfit_config.yuzuha_outfit_list
        AgentEnum.ALICE.value.template_id_list = self.agent_outfit_config.alice_outfit_list

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        @return:
        """
        if hasattr(self, 'telemetry') and self.telemetry:
            self.telemetry.shutdown()

        OneDragonContext.after_app_shutdown(self)

    def init_auto_op(self, op_name: str, sub_dir: str = 'auto_battle') -> None:
        """
        加载自动战斗指令

        Args:
            sub_dir: 子文件夹
            op_name: 模板名称

        Returns:
            None
        """
        if self.auto_op is not None:  # 如果有上一个 先销毁
            self.auto_op.dispose()

        from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
        self.auto_op = AutoBattleOperator(self, sub_dir, op_name)
        success, msg = self.auto_op.init_before_running()
        if not success:
            raise Exception(msg)

    def stop_auto_battle(self) -> None:
        """
        停止自动战斗
        Returns:
            None
        """
        if self.auto_op is not None:
            self.auto_op.stop_running()

    def start_auto_battle(self) -> None:
        """
        开始自动战斗
        """
        if self.auto_op is not None:
            self.auto_op.start_running_async()
