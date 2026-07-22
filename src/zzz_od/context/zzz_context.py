from __future__ import annotations

from functools import cached_property

from one_dragon.base.operation.one_dragon_context import OneDragonContext


class ZContext(OneDragonContext):

    def __init__(self,):

        OneDragonContext.__init__(self)
        self._init_managed_ocr()

        # 后续所有用到自动战斗的 都统一设置到这个里面
        from zzz_od.auto_battle.auto_battle_context import AutoBattleContext
        self.auto_battle_context: AutoBattleContext = AutoBattleContext(self)

    def _init_managed_ocr(self) -> None:
        """替换基础 OCR 为绝区零侧的懒加载管理实现。"""
        from one_dragon.base.matcher.ocr.ocr_service import OcrService
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrParam
        from zzz_od.context.managed_ocr_matcher import ManagedOnnxOcrMatcher

        self.ocr = ManagedOnnxOcrMatcher(
            OnnxOcrParam(
                use_gpu=self.model_config.ocr_use_gpu,
                det_limit_side_len=max(
                    self.project_config.screen_standard_width,
                    self.project_config.screen_standard_height,
                ),
            )
        )
        self.ocr.overlay_debug_bus = self.overlay_debug_bus
        self.ocr_service = OcrService(ocr_matcher=self.ocr)

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
        if self.game_account_config.game_region == GameRegionEnum.CN.value.value \
                or self.game_account_config.game_region == GameRegionEnum.CNB.value.value:
            return '绝区零'
        else:
            return 'ZenlessZoneZero'

    def on_switch_instance(self) -> None:
        """
        切换实例后更新 controller 的窗口标题
        """
        if self.controller is not None:
            new_win_title = self._get_win_title()
            self.controller.set_window_title(new_win_title)

    def init_controller(self) -> None:
        from one_dragon.base.config.game_account_config import GamePlatformEnum
        if self.game_account_config.platform == GamePlatformEnum.PC.value.value:
            if self.controller is not None:
                self.controller.cleanup_after_app_shutdown()
            from zzz_od.controller.zzz_pc_controller import ZPcController
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

    def init_ocr(self) -> None:
        """配置 OCR 运行参数，不在 GUI 启动阶段加载 ONNX 会话。"""
        from zzz_od.context.managed_ocr_matcher import ManagedOnnxOcrMatcher

        if isinstance(self.ocr, ManagedOnnxOcrMatcher):
            self.ocr.configure_runtime(
                use_gpu=self.model_config.ocr_use_gpu,
                proxy_url=self.env_config.personal_proxy if self.env_config.is_personal_proxy else None,
                ghproxy_url=self.env_config.gh_proxy_url if self.env_config.is_gh_proxy else None,
            )
            return

        OneDragonContext.init_ocr(self)

    def init_others(self) -> None:
        self.telemetry.initialize()  # 遥测

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        """
        if hasattr(self, 'telemetry') and self.telemetry:
            self.telemetry.shutdown()

        # 上层清理依赖框架服务(如 StateRecordService)，必须先于框架清理
        self.withered_domain.after_app_shutdown()
        self.auto_battle_context.after_app_shutdown()

        from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
        AutoBattleOperator.after_app_shutdown()

        if hasattr(self.ocr, 'shutdown'):
            self.ocr.shutdown()

        OneDragonContext.after_app_shutdown(self)
