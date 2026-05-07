from one_dragon.base.operation.operation_base import OperationBase
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame


class ZOperationMixin:
    """绝区零操作通用能力。"""

    _ctx: ZContext
    _op_to_enter_game: OperationBase | None

    @property
    def ctx(self) -> ZContext:
        return self._ctx

    @ctx.setter
    def ctx(self, value: ZContext) -> None:
        self._ctx = value

    @property
    def op_to_enter_game(self) -> OperationBase:
        if self._op_to_enter_game is None:
            self._op_to_enter_game = OpenAndEnterGame(self.ctx)
        return self._op_to_enter_game

    @op_to_enter_game.setter
    def op_to_enter_game(self, value: OperationBase | None) -> None:
        self._op_to_enter_game = value


class ZZZCloudMixin:
    """云游戏场景下的通用检查逻辑。"""

    CLOUD_GAME_NOT_ENTERED_AREA_LIST: list[tuple[str, str]] = [
        ('云游戏', '国服PC云-点击空白区域关闭'),
        ('云游戏', '国服PC云-排队中'),
        ('云游戏', '国服PC云-开始游戏'),
        ('云游戏', '国服PC云-邦邦点快速队列'),
        ('云游戏', '国服PC云-普通队列'),
        ('云游戏', '国服PC云-切换窗口'),
        ('打开游戏', '点击进入游戏'),
    ]

    def check_game_initialized(self) -> OperationRoundResult:
        """检查游戏是否完成初始化，云游戏未进入时视为未就绪。"""
        if not self.ctx.game_account_config.is_cloud_game:
            return self.round_success()

        screen = self.screenshot()
        for screen_name, area_name in self.CLOUD_GAME_NOT_ENTERED_AREA_LIST:
            result = self.round_by_find_area(screen, screen_name, area_name)
            if result.is_success:
                return self.round_fail(result.status)

        return self.round_success()
