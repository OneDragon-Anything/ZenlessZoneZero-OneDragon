from zzz_od.context.zzz_context import ZContext


class BattleLoadingTimeout:
    """战斗画面加载节点的超时 读取游戏设置中的战斗加载等待上限"""

    def resolve(self, ctx: ZContext) -> float:
        return ctx.game_config.battle_loading_timeout


BATTLE_LOADING_TIMEOUT = BattleLoadingTimeout()
