"""迷失之地战斗 op(shadow 基类节点 + 重定义开始自动战斗 + 覆写 hook detector 状态机)。

从 ``application/hollow_zero/lost_void/operation/lost_void_run_level.py`` 复制
``in_battle`` 状态机(:849-983)。原 ``LostVoidRunLevel`` 不动。

op 边界:等战斗画面(shadow,wait_battle 控制)→ 开始自动战斗 → 自动战斗(detector 判断结束返回 status)。
移动(进下一区域)/ 失败链 / 结束后操作交外层。
设计依据:docs/superpowers/specs/2026-07-21-battle-op-boundary-design.md。
"""
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen import screen_utils
from one_dragon.utils import gpu_executor
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.battle.base import BattleOpBase

if TYPE_CHECKING:
    from one_dragon.yolo.detect_utils import DetectFrameResult
    from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import (
        LostVoidDetector,
    )


class LostVoidBattleOp(BattleOpBase):
    """迷失之地战斗 op。

    shadow 基类「战前移动」/「等待战斗画面」(wait_battle 控制:True 轮询 check_battle_encounter / False 跳过);
    重定义「开始自动战斗」(独立节点,只调一次 start_auto_battle);
    覆写 _get_auto_battle_op_name + _check_battle_state(无 flag) + _check_in_battle_secondary(detector 状态机)。
    移动(进下一区域)/ 失败链 / 结束后操作交外层。
    """

    _interact_as_wait_fallback: bool = True    # 迷失之地开战后画面可能出现「按键-交互」

    def __init__(self, ctx: ZContext, region_type: LostVoidRegionType, wait_battle: bool = False) -> None:
        """Args:
            ctx: ZContext。
            region_type: 当前区域类型(ELITE/BOSS 跳 detector 守卫)。
            wait_battle: 是否在 wait_battle_screen 轮询 check_battle_encounter 判战斗开始。
                True=智能体进入下层用(op 自适应判战斗/事件);False=原流程用(外层已判,op 跳过)。
        """
        BattleOpBase.__init__(self, ctx, op_name='迷失之地 自动战斗')
        self.region_type: LostVoidRegionType = region_type
        self._wait_battle: bool = wait_battle
        # 帧间战斗状态 + 双计数器(复制自 lost_void_run_level.py:121-125)
        self._last_frame_in_battle: bool = True
        self._current_frame_in_battle: bool = True
        self._last_det_time: float = 0              # 上一次进行识别的时间(in_battle 分支 0.8s 节流)
        self._last_check_finish_time: float = 0     # 上一次识别结束的时间(not-in_battle 分支 1s 节流)
        self._no_in_battle_times: int = 0           # 识别到不在战斗的次数(in>=10 / not-in>=3 分流)
        # detector 前置断言(由 ctx.lost_void.init_before_run() 初始化)
        self.detector: LostVoidDetector = ctx.lost_void.detector
        if self.detector is None:
            raise RuntimeError('LostVoidBattleOp: detector is None, 需 ctx.lost_void.init_before_run()')

    # ===== shadow:移除基类「战前移动」节点;覆写「等待战斗画面」(wait_battle 控制)=====

    def pre_battle_move(self) -> None:
        """shadow:移除基类「战前移动」节点(迷失之地进区域直接战斗,无战前移动)。"""
        pass

    @node_from(from_name='加载自动战斗指令')
    @operation_node(name='等待战斗画面加载', node_max_retry_times=60)
    def wait_battle_screen(self) -> OperationRoundResult:
        """shadow:迷失之地大世界攻击按钮常驻,基类等攻击按钮不可靠。

        - wait_battle=True:轮询 ``ctx.lost_void.check_battle_encounter``(文本「战斗开始」/血量扣减/闪避光)判战斗开始;
          超时未进入(事件区域)→ op 失败,外层(智能体)处理事件。
        - wait_battle=False:跳过(外层 non_battle_check 已判),直接进 start_auto_battle。
        """
        if not self._wait_battle:
            return self.round_success()
        if self.ctx.lost_void.check_battle_encounter(self.last_screenshot, self.last_screenshot_time):
            return self.round_success()
        return self.round_retry('未进入战斗', wait=1)

    # ===== 重定义节点 =====

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='开始自动战斗')
    def start_auto_battle(self) -> OperationRoundResult:
        """独立节点(替代基类「战前移动 → 开始自动战斗」链),只调一次 start_auto_battle。
        入口重置 _last_det_time + _last_check_finish_time(避免上一区域遗留时间戳导致节流失效)。
        """
        self.ctx.auto_battle_context.start_auto_battle()
        self._last_det_time = self.last_screenshot_time
        self._last_check_finish_time = self.last_screenshot_time
        return self.round_success()

    # auto_battle 继承基类(@node_from from 开始自动战斗 + _do_auto_battle_round;不覆写)

    # ===== hook 覆写 =====

    def _get_auto_battle_op_name(self) -> str | None:
        """迷失之地用 ctx.lost_void.get_auto_op_name()(对齐原 lost_void_run_level.py:1104)。"""
        return self.ctx.lost_void.get_auto_op_name()

    def _check_battle_state(self) -> bool:
        """不传 flag(迷失之地只跑 normal end 检测;detector 在 _check_in_battle_secondary 自管)。"""
        return self.ctx.auto_battle_context.check_battle_state(
            self.last_screenshot, self.last_screenshot_time)

    def _check_in_battle_secondary(self, in_battle: bool) -> str | None:
        """战中副判:迷失之地 detector + OCR 状态机(复制自 lost_void_run_level.py:849-983)。

        - in_battle 分支:detector(ELITE/BOSS 跳)或 OCR「前往下一个区域」识别脱战
          → _no_in_battle_times >= 10 → STATUS_NEED_MOVE。
        - not-in_battle 分支:画面识别(武备/通用选择/挑战结果/战斗失败)
          → _no_in_battle_times >= 3 后分流(战斗失败 vs STATUS_NEED_MOVE)。

        返回 None=继续等待;STATUS_NEED_MOVE/'迷失之地-战斗失败'=交基类 round_success(status),op 返回(外层处理)。
        """
        self._last_frame_in_battle = self._current_frame_in_battle
        self._current_frame_in_battle = in_battle
        now = self.last_screenshot_time

        if in_battle:  # 当前回到可战斗画面
            if (not self._last_frame_in_battle  # 之前在非战斗画面
                    or now - self._last_det_time >= 0.8  # 0.8秒识别一次
                    or (self._no_in_battle_times > 0 and now - self._last_check_finish_time >= 0.1)):  # 之前也识别到脱离战斗 0.1秒识别一次
                no_in_battle = False
                found_next_region_hint = False

                # 尝试识别下层入口 (道中危机 和 终结之役 不需要识别)
                if self.region_type not in (LostVoidRegionType.ELITE, LostVoidRegionType.BOSS):
                    self._last_det_time = now  # 块内更新(ELITE/BOSS 不更新 → 节流永开)
                    try:
                        # 为了不随意打断战斗 这里的识别阈值要高一点
                        if self.ctx.model_config.lost_void_det_gpu:
                            f = gpu_executor.submit(
                                self.detector.run,
                                image=self.last_screenshot,
                                conf=0.9,
                                run_time=now,
                            )
                            frame_result: DetectFrameResult = f.result()
                        else:
                            frame_result = self.detector.run(
                                image=self.last_screenshot,
                                conf=0.9,
                                run_time=now,
                            )
                        with_interact, with_distance, with_entry = self.detector.is_frame_with_all(frame_result)
                        if with_interact or with_distance or with_entry:
                            no_in_battle = True
                    except Exception as e:
                        # 刚开始可能有一段时间识别报错 有可能是一张图同时在两个onnx里面跑 加入第二次截图观察
                        log.error('战斗中识别交互出现异常', exc_info=e)
                        return None  # 异常 → None

                # OCR「前往下一个区域」(region_type 块外,所有类型都跑)
                if not no_in_battle:
                    area = self.ctx.screen_loader.get_area('迷失之地-大世界', '区域-文本提示')
                    if self.ctx.model_config.ocr_use_gpu:
                        f = gpu_executor.submit(
                            screen_utils.find_by_ocr,
                            ctx=self.ctx,
                            screen=self.last_screenshot,
                            target_cn='前往下一个区域',
                            area=area,
                        )
                        found = f.result()
                    else:
                        found = screen_utils.find_by_ocr(
                            self.ctx, self.last_screenshot, target_cn='前往下一个区域', area=area)

                    if found:
                        found_next_region_hint = True
                        no_in_battle = True

                # 「前往下一个区域」单次命中即判脱战 → STATUS_NEED_MOVE
                if found_next_region_hint:
                    self._no_in_battle_times = 0
                    return BattleOpBase.STATUS_NEED_MOVE

                if no_in_battle:
                    self._no_in_battle_times += 1
                else:
                    self._no_in_battle_times = 0

                if self._no_in_battle_times >= 10:
                    return BattleOpBase.STATUS_NEED_MOVE

            return None
        else:  # 当前不在战斗画面
            if (now - self._last_check_finish_time >= 1  # 1秒识别一次
                    or (self._no_in_battle_times > 0 and now - self._last_check_finish_time >= 0.1)):  # 之前也识别到脱离战斗 0.1秒识别一次
                self._last_check_finish_time = now

                # 部分情况刚好战斗结束站在交互点上
                interact_result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')

                no_in_battle_screen_name_list = [
                    '迷失之地-武备选择', '迷失之地-通用选择',
                    '迷失之地-挑战结果',
                    '迷失之地-战斗失败',
                ]
                if self.ctx.model_config.ocr_use_gpu:
                    f = gpu_executor.submit(
                        self.check_and_update_current_screen,
                        screen=self.last_screenshot,
                        screen_name_list=no_in_battle_screen_name_list,
                    )
                    screen_name = f.result()
                else:
                    screen_name = self.check_and_update_current_screen(  # 局部变量(对齐原 :946)
                        self.last_screenshot, no_in_battle_screen_name_list)

                # 以下情况会出现确认对话框
                # 1. 所有战术棱镜均已升级
                if self.ctx.model_config.ocr_use_gpu:
                    f = gpu_executor.submit(
                        self.round_by_find_and_click_area,
                        screen=self.last_screenshot,
                        screen_name='迷失之地-大世界',
                        area_name='按钮-挑战-确认',
                    )
                    confirm_result = f.result()
                else:
                    confirm_result = self.round_by_find_and_click_area(
                        self.last_screenshot,
                        screen_name='迷失之地-大世界',
                        area_name='按钮-挑战-确认',
                    )

                if screen_name in no_in_battle_screen_name_list or interact_result.is_success or confirm_result.is_success:
                    self._no_in_battle_times += 1
                else:
                    self._no_in_battle_times = 0

                if self._no_in_battle_times >= 3:
                    self._no_in_battle_times = 0  # 分支前清零(对齐原 :972)
                    if screen_name == '迷失之地-战斗失败':
                        return '迷失之地-战斗失败'
                    return BattleOpBase.STATUS_NEED_MOVE

            return None
