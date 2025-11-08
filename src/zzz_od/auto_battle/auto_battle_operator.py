from __future__ import annotations

import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import List, Optional, Tuple, Any, TYPE_CHECKING

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.loader import ConditionalOperatorLoader
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.conditional_operation.operator import ConditionalOperator
from one_dragon.base.conditional_operation.state_recorder import StateRecorder
from one_dragon.utils import thread_utils
from one_dragon.utils.log_utils import log
from zzz_od.auto_battle.atomic_op.btn_lock import AtomicBtnLock
from zzz_od.auto_battle.atomic_op.turn import AtomicTurn
from zzz_od.context.zzz_context import ZContext

if TYPE_CHECKING:
    from zzz_od.auto_battle.auto_battle_context import AutoBattleContext

_auto_battle_operator_executor = ThreadPoolExecutor(thread_name_prefix='_auto_battle_operator_executor', max_workers=2)

# 自动战斗配置的默认回退模板名
FALLBACK_TEMPLATE_NAME = '全配队通用'


class AutoBattleOperator(ConditionalOperator):

    def __init__(
        self,
        ctx: AutoBattleContext,
        sub_dir: str,
        template_name: str,
        read_from_merged: bool = True,
    ):
        original_file_path = ConditionalOperatorLoader.get_yaml_file_path(
            sub_dir=[sub_dir],
            template_name=template_name,
            read_from_merged=read_from_merged,
        )
        if not os.path.exists(original_file_path):
            log.warning(f'自动战斗配置 {original_file_path} 不存在，回退到 {FALLBACK_TEMPLATE_NAME}')
            template_name = FALLBACK_TEMPLATE_NAME

        ConditionalOperator.__init__(
            self,
            sub_dir=[sub_dir],
            template_name=template_name,
            operation_template_sub_dir=['auto_battle_operation'],
            state_handler_template_sub_dir=['auto_battle_state_handler'],
            read_from_merged=read_from_merged,
            state_record_service=ctx.state_record_service,
        )

        # 配置文件的zzz定制内容
        self.author: str = ''  #  作者
        self.homepage: str = ''
        self.thanks: str = ''
        self.version: str = ''
        self.introduction: str = ''
        self.team_list: list[list[str]] = []  # 配队信息

        self.check_dodge_interval: float = 0.02  # 检测闪避的间隔
        self.check_agent_interval: float = 0.5  # 检测代理人的间隔
        self.check_chain_interval: float = 1  # 检测连携技的间隔
        self.check_quick_interval: float = 0.5  # 检测快速支援的间隔
        self.check_end_interval: float = 5  # 检测战斗结束的间隔
        self.target_lock_interval: float = 1  # 检测锁定目标的间隔
        self.abnormal_status_interval: float = 0  # 检测异常状态的间隔
        self.auto_lock_interval = 1  # 自动锁定的间隔
        self.auto_turn_interval = 2  # 自动转向的间隔

        self.ctx: AutoBattleContext = ctx

        # 自动周期
        self.last_lock_time: float = 0  # 上一次锁定的时间
        self.last_turn_time: float = 0  # 上一次转动视角的时间

    def load_other_info(self, data: dict[str, Any]) -> None:
        """
        加载其他所需的信息

        Args:
            data: 配置文件内容
        """
        self.author = data.get('author', '')
        self.homepage = data.get('homepage', 'https://qm.qq.com/q/wuVRYuZzkA')
        self.thanks = data.get('thanks', '')
        self.version = data.get('version', '')
        self.introduction = data.get('introduction', '')
        self.team_list = data.get('team_list', [])

        self.check_dodge_interval = data.get('check_dodge_interval', 0.02)
        self.check_agent_interval = data.get('check_agent_interval', 0.5)
        self.check_chain_interval = data.get('check_chain_interval', 1)
        self.check_quick_interval = data.get('check_quick_interval', 0.5)
        self.check_end_interval = data.get('check_end_interval', 5)
        self.target_lock_interval = data.get('target_lock_interval', 1)
        self.abnormal_status_interval = data.get('abnormal_status_interval', 0)
        self.auto_lock_interval = data.get('auto_lock_interval', 1)
        self.auto_turn_interval = data.get('auto_turn_interval', 2)

    def init_before_running(self) -> Tuple[bool, str]:
        """
        运行前进行初始化
        :return:
        """
        try:
            ConditionalOperator.init(self)
            log.info(f'自动战斗配置加载成功 {self.get_template_name()}')
            return True, ''
        except Exception as e:
            log.error('自动战斗初始化失败 共享配队文件请在群内提醒对应作者修复', exc_info=True)
            return False, '初始化失败'

    def get_atomic_op(self, op_def: OperationDef) -> AtomicOp:
        """
        获取一个原子操作

        Args:
            op_def: 操作定义

        Returns:
            AtomicOp: 原子操作
        """
        return self.ctx.atomic_op_factory.get_atomic_op(op_def)

    def dispose(self) -> None:
        """
        销毁 注意要解绑各种事件监听
        :return:
        """
        ConditionalOperator.dispose(self)

    def start_running_async(self) -> bool:
        success = ConditionalOperator.start_running_async(self)
        if success:
            lock_f = _auto_battle_operator_executor.submit(self.operate_periodically)
            lock_f.add_done_callback(thread_utils.handle_future_result)

        return success

    def operate_periodically(self) -> None:
        """
        周期性完成动作

        1. 锁定敌人
        2. 转向 - 有机会找到后方太远的敌人；迷失之地可以转动下层入口
        :return:
        """
        if self.auto_lock_interval <= 0 and self.auto_turn_interval <= 0:  # 不开启自动锁定 和 自动转向
            return
        lock_op = AtomicBtnLock(self.ctx)
        turn_op = AtomicTurn(self.ctx, 100)
        while self.is_running:
            now = time.time()

            if not self.ctx.last_check_in_battle:  # 当前画面不是战斗画面 就不运行了
                time.sleep(0.2)
                continue

            any_done: bool = False
            if self.auto_lock_interval > 0 and now - self.last_lock_time > self.auto_lock_interval:
                lock_op.execute()
                self.last_lock_time = now
                any_done = True
            if self.auto_turn_interval > 0 and now - self.last_turn_time > self.auto_turn_interval:
                turn_op.execute()
                self.last_turn_time = now
                any_done = True

            if not any_done:
                time.sleep(0.2)

    @staticmethod
    def after_app_shutdown() -> None:
        """
        整个脚本运行结束后的清理
        """
        _auto_battle_operator_executor.shutdown(wait=False, cancel_futures=True)


def __debug():
    ctx = ZContext()
    ctx.init()
    auto_op = AutoBattleOperator(ctx.auto_battle_context, 'auto_battle', '全配队通用')
    auto_op.init()
    auto_op.usage_states
    # auto_op.start_running_async()
    # time.sleep(5)
    # auto_op.stop_running()


if __name__ == '__main__':
    __debug()
