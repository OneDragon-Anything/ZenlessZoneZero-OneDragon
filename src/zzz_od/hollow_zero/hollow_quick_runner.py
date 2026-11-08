from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event.bangboo_plugin import BangbooPlugin, UseBangbooPlugin
from zzz_od.hollow_zero.hollow_map.hollow_zero_map import (
    HollowZeroMap,
    HollowZeroMapNode,
)
from zzz_od.hollow_zero.hollow_runner import HollowRunner


class HollowQuickRunner(HollowRunner):

    MAX_BOMB_TIMES: int = 2  # 单次空洞内最多尝试使用炸弹的次数 防止炸不掉时反复使用

    def __init__(self, ctx: ZContext):
        """
        空洞周期速刷的调度操作器
        在 HollowRunner 的基础上 全程接入邦布插件:
        速通寻路绕开小怪格 前往终点的路径被小怪格堵住时 走到小怪格旁使用炸弹 再用医疗包回血

        炸弹用不了(没有数量/弹窗打不开)时 不再尝试 回退为常规的战斗通过
        """
        HollowRunner.__init__(self, ctx)
        self.op_name = gt('空洞周期速刷', 'game')

        # 不进入商店 经过商人格子时直接前往下一格
        self._entry_event_handlers.pop('邦布商人', None)

        self._bomb_times: int = 0  # 已经使用炸弹的次数
        self._plugin_unavailable: bool = False  # 炸弹是否已经确认用不了

    def _before_move(self, current_map: HollowZeroMap,
                     target_node: HollowZeroMapNode) -> tuple[HollowZeroMapNode, OperationRoundResult | None]:
        self._log_map(current_map, target_node)

        if self._plugin_unavailable:
            return target_node, None

        blocker = self.ctx.withered_domain.find_blocker(current_map, target_node)
        if blocker is None:
            return target_node, None

        blocker_node, stand_node = blocker
        current_node = current_map.nodes[current_map.current_idx]
        if stand_node is not current_node:
            # 先走到挡路小怪的前一格 再使用炸弹
            log.info(f'终点被 [{blocker_node.entry.entry_name}] 挡住 先前往它旁边的格子')
            return stand_node, None

        log.info(f'终点被 [{blocker_node.entry.entry_name}] 挡住 使用炸弹')
        return target_node, self._use_bomb_and_medical()

    def _log_map(self, current_map: HollowZeroMap, target_node: HollowZeroMapNode) -> None:
        """
        记录当前层数和地图上关心的格子 排查没有去业绩/S门时使用
        """
        level_info = self.ctx.withered_domain.level_info
        names = ['业绩考察点', '业绩考察点空', '门扉禁闭-善战', '门扉禁闭-侵蚀', '门扉禁闭-财富',
                 '诡雾', '传送点', '守门人', '不宜久留', '危机', '双重危机', '限时战斗']
        counts = {
            name: sum(1 for node in current_map.nodes if node.entry.entry_name == name)
            for name in names
        }
        summary = ' '.join(f'{name}={cnt}' for name, cnt in counts.items() if cnt > 0)
        log.info(f'速刷地图 层={level_info.level} 阶段={level_info.phase} 目标=[{target_node.entry.entry_name}] {summary}')

    def _use_bomb_and_medical(self) -> OperationRoundResult | None:
        """
        使用炸弹 然后立刻使用医疗包回血
        :return: 本轮的结果；炸弹用不了时返回None 回退为常规处理
        """
        if self._bomb_times >= HollowQuickRunner.MAX_BOMB_TIMES:
            log.error('炸弹使用次数已达上限 炸不掉挡路的小怪 回退为战斗通过')
            self._plugin_unavailable = True
            return None

        self._bomb_times += 1
        bomb_result = UseBangbooPlugin(self.ctx, BangbooPlugin.BOMB).execute()
        if not bomb_result.success:
            log.error(f'使用炸弹失败 回退为战斗通过 {bomb_result.status}')
            self._plugin_unavailable = True
            return None

        # 炸弹对全队造成伤害 马上使用医疗包 失败了也继续
        medical_result = UseBangbooPlugin(self.ctx, BangbooPlugin.MEDICAL).execute()
        if not medical_result.success:
            log.error(f'使用医疗包失败 {medical_result.status}')

        # 小怪格被清除 之前识别的地图已经失效
        self.ctx.withered_domain.map_service.clear_map_result()
        self.ctx.withered_domain.last_target_node = None
        return self.round_wait('已使用炸弹', wait=1.5)
