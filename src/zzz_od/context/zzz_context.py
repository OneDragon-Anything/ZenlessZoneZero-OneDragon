from __future__ import annotations

import threading
from functools import cached_property
from pathlib import Path

from one_dragon.base.matcher.ocr.onnx_ocr_matcher import (
    DEFAULT_OCR_MODEL_NAME,
    PPOCRV6_MODEL_NAME,
    OnnxOcrMatcher,
    OnnxOcrParam,
    get_final_file_list,
)
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.log_utils import log


class ZContext(OneDragonContext):

    def __init__(self,):

        OneDragonContext.__init__(self)
        self._ocr_v6_downloading: bool = False  # 后台下载 V6 是否进行中 防止重复启动

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
        if self.game_account_config.game_region == GameRegionEnum.CN.value.value \
                or self.game_account_config.game_region == GameRegionEnum.CNB.value.value:
            return '绝区零'
        else:
            return 'ZenlessZoneZero'

    def on_switch_instance(self) -> None:
        """
        切换实例后更新 controller 的窗口标题和账号配置
        """
        from zzz_od.controller.zzz_pc_controller import ZPcController

        controller = self.controller
        if not isinstance(controller, ZPcController):
            return

        new_win_title = self._get_win_title()
        controller.set_window_title(new_win_title)
        controller.sync_game_config(self.game_config)

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

    def init_ocr(self) -> None:
        """
        初始化OCR 正常模式下按本地模型文件状态向 V6 收敛
        """
        super().init_ocr()

        # 正常模式下 向 V6 收敛
        if not self.env_config.is_debug:
            if self._is_ocr_model_ready(PPOCRV6_MODEL_NAME):
                # V6 已就绪（启动就有 或 刚同步下载完成） 落盘配置
                self.model_config.ocr = PPOCRV6_MODEL_NAME
            elif self._is_ocr_model_ready(DEFAULT_OCR_MODEL_NAME):
                # 当前用 V5 顶住 后台下载 V6 成功后自动切换
                self._download_ocr_v6_in_background()

    def _decide_ocr_model_name(self) -> str:
        """
        决定本次初始化使用的 OCR 模型名 覆写框架层钩子

        调试模式: 直接使用配置里的模型 不自动切换
        正常模式: 向 V6 收敛
          - V6 文件齐全 -> 用 V6
          - V6 不齐 但 V5 齐全 -> 先用 V5 顶住 后台下载 V6
          - 都没有 -> 直接用 V6（会触发下载）
        """
        if self.env_config.is_debug:
            return self.model_config.ocr

        if self._is_ocr_model_ready(PPOCRV6_MODEL_NAME):
            return PPOCRV6_MODEL_NAME

        if self._is_ocr_model_ready(DEFAULT_OCR_MODEL_NAME):
            return DEFAULT_OCR_MODEL_NAME

        return PPOCRV6_MODEL_NAME

    @staticmethod
    def _is_ocr_model_ready(ocr_model_name: str) -> bool:
        """
        判断某个 OCR 模型的文件是否已经全部就绪
        """
        return all(Path(f).exists() for f in get_final_file_list(ocr_model_name))

    def _download_ocr_v6_in_background(self) -> None:
        """
        后台下载 V6 模型 下载成功后落盘配置 下次启动自动生效
        已有下载任务进行中时 不重复启动
        """
        if self._ocr_v6_downloading:
            return
        self._ocr_v6_downloading = True

        def download_task() -> None:
            try:
                v6_matcher = OnnxOcrMatcher(
                    OnnxOcrParam(
                        ocr_model_name=PPOCRV6_MODEL_NAME,
                    )
                )
                done = v6_matcher.download(
                    download_by_github=True,
                    download_by_gitee=False,
                    download_by_mirror_chan=False,
                    ghproxy_url=self.env_config.gh_proxy_url if self.env_config.is_gh_proxy else None,
                    proxy_url=self.env_config.personal_proxy if self.env_config.is_personal_proxy else None,
                )
                if done:
                    # 只落盘配置 不立刻切换 避免切换失败导致当前可用的 V5 失效
                    self.model_config.ocr = PPOCRV6_MODEL_NAME
                    log.info('OCR V6 后台下载完成 配置已更新 下次启动自动切换')
                else:
                    log.error('OCR V6 后台下载失败 保持当前 V5 可用 下次启动再试')
            except Exception:
                log.error('OCR V6 后台下载异常 保持当前 V5 可用 下次启动再试', exc_info=True)
            finally:
                self._ocr_v6_downloading = False

        threading.Thread(target=download_task, daemon=True, name='ocr_v6_download').start()

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

        # 上层清理依赖框架服务(如 StateRecordService)，必须先于框架清理
        self.withered_domain.after_app_shutdown()
        self.auto_battle_context.after_app_shutdown()

        from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
        AutoBattleOperator.after_app_shutdown()

        OneDragonContext.after_app_shutdown(self)
