import time
from typing import Optional

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.base.operation.one_dragon_context import ContextKeyboardEventEnum
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import debug_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.devtools.screenshot_helper import screenshot_helper_const
from zzz_od.application.devtools.screenshot_helper.screenshot_helper_config import (
    ScreenshotHelperConfig,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext


class ScreenshotHelperApp(ZApplication):

    def __init__(self, ctx: ZContext):
        """
        按闪避的时候自动截图 用于保存素材训练模型
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=screenshot_helper_const.APP_ID,
            op_name=gt(screenshot_helper_const.APP_NAME),
        )
        self.config: Optional[ScreenshotHelperConfig] = self.ctx.run_context.get_config(
            app_id=screenshot_helper_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.to_save_screenshot: bool = False  # 去保存截图 由按键触发
        self.last_save_screenshot_time: float = 0  # 上次保存截图时间
        self.auto_op: Optional[AutoBattleOperator] = None
        self.screenshot_cache: list = []  # 缓存所有截图
        self.cache_start_time: Optional[float] = None  # 缓存开始时间
        self.cache_max_count: int = 0  # 最大缓存数量
        self.is_saving_after_key: bool = False  # 是否正在保存按键后的截图

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        ZApplication.handle_init(self)
        length_second = self.config.length_second
        freq_second = self.config.frequency_second
        self.ctx.controller.screenshot_alive_seconds = length_second + 1
        self.ctx.controller.max_screenshot_cnt = length_second // freq_second + 5
        self.cache_max_count = length_second // freq_second + 1
        self.screenshot_cache = []
        self.cache_start_time = time.time()
        self.ctx.listen_event(ContextKeyboardEventEnum.PRESS.value, self._on_key_press)

    @operation_node(name='初始化上下文', is_start_node=True)
    def init_context(self) -> OperationRoundResult:
        auto_battle_utils.load_auto_op(self, 'dodge',
                                       self.ctx.battle_assistant_config.dodge_assistant_config)
        return self.round_success()

    @node_from(from_name='初始化上下文')
    @node_from(from_name='保存截图')
    @operation_node(name='持续截图', mute=True)
    def repeat_screenshot(self) -> OperationRoundResult:
        """
        持续截图
        """
        # 缓存截图
        if self.cache_start_time is None:
            self.cache_start_time = self.last_screenshot_time
        self.screenshot_cache.append(self.last_screenshot)

        if self.config.mini_map_angle_detect:
            mm = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)
            angle = mm.view_angle
            log.info(f'当前角度 {angle}')
            if angle is None:
                self.save_screenshot()
        # 动态计算最大缓存数量
        if len(self.screenshot_cache) > self.cache_max_count:
            self.screenshot_cache.pop(0)

        if self.config.dodge_detect:
            if self.auto_op.auto_battle_context.dodge_context.check_dodge_flash(self.last_screenshot, self.last_screenshot_time):
                debug_utils.save_debug_image(self.last_screenshot, prefix='dodge')
            elif self.auto_op.auto_battle_context.dodge_context.check_dodge_audio(self.last_screenshot_time):
                debug_utils.save_debug_image(self.last_screenshot, prefix='dodge')

        if self.to_save_screenshot:
            if not self.config.screenshot_before_key and self.is_saving_after_key:
                # 在按键后截图模式下，保存当前截图
                debug_utils.save_debug_image(self.last_screenshot, prefix='switch')
            return self.round_success()
        else:
            # 确保每次截图间隔正确
            next_time = self.config.frequency_second - (time.time() - self.last_screenshot_time)
            return self.round_wait(wait_round_time=max(0.01, next_time))

    def _on_key_press(self, event: ContextEventItem) -> None:
        """
        按键监听
        """
        if self.to_save_screenshot:  # 上轮截图还没有完成保存
            return
        key: str = event.data
        if time.time() - self.last_save_screenshot_time <= 1:  # 每秒最多保持一次 防止战斗中按得太多
            return
        if key != self.config.key_save:
            return

        self.to_save_screenshot = True

    @node_from(from_name='持续截图')
    @operation_node(name='保存截图')
    def do_save_screenshot(self) -> OperationRoundResult:
        """
        保存截图
        """
        if self.config.screenshot_before_key:
            # 保存缓存中的截图
            for screen in self.screenshot_cache:
                debug_utils.save_debug_image(screen, prefix='switch')
            self.screenshot_cache = []
            self.cache_start_time = time.time()
            self.to_save_screenshot = False
            self.last_save_screenshot_time = time.time()
        else:
            # 清空缓存并开始保存按键后的截图
            self.screenshot_cache = []
            self.cache_start_time = time.time()
            self.is_saving_after_key = True
            # 等待一个截图周期后再关闭保存标志，以确保能够捕获按键后的截图
            next_time = self.config.frequency_second
            return self.round_wait(wait_round_time=next_time)
        return self.round_success()

    def after_operation_done(self, result: OperationResult):
        ZApplication.after_operation_done(self, result)

        self.ctx.controller.max_screenshot_cnt = 0
