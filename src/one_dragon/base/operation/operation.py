from __future__ import annotations

import difflib
import inspect
import time
from functools import cached_property
from io import BytesIO
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Optional

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContextStateEventEnum,
)
from one_dragon.base.operation.operation_base import OperationBase, OperationResult
from one_dragon.base.operation.operation_edge import OperationEdge, OperationEdgeDesc
from one_dragon.base.operation.operation_node import OperationNode
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_utils import FindAreaResultEnum, OcrClickResultEnum
from one_dragon.utils import cv2_utils, debug_utils, str_utils
from one_dragon.utils.i18_utils import coalesce_gt, gt
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext

class PreviousNodeStateProxy:
    """
    一个代理类，用于安全、便捷地访问上一个节点的静态信息和动态执行结果。
    """

    def __init__(self, node: Optional[OperationNode], result: Optional[OperationRoundResult]):
        self._node = node
        self._result = result

    @property
    def name(self) -> Optional[str]:
        """
        上一个节点的名称
        """
        return self._node.cn if self._node else None

    @property
    def status(self) -> Optional[str]:
        """
        上一个节点的返回状态
        """
        return self._result.status if self._result else None

    @property
    def data(self) -> Optional[Any]:
        """
        上一个节点的返回数据
        """
        return self._result.data if self._result else None

    @property
    def is_success(self) -> bool:
        """
        上一个节点是否成功
        """
        if self._result is None:
            return False
        return self._result.result == OperationRoundResultEnum.SUCCESS

    @property
    def is_fail(self) -> bool:
        """
        上一个节点是否失败
        """
        if self._result is None:
            return False
        return self._result.result == OperationRoundResultEnum.FAIL

    @property
    def raw_node(self) -> Optional[OperationNode]:
        """
        获取原始的 OperationNode 对象，用于高级访问
        """
        return self._node


class Operation(OperationBase):

    STATUS_TIMEOUT: ClassVar[str] = '执行超时'
    STATUS_SCREEN_UNKNOWN: ClassVar[str] = '未能识别当前画面'

    def __init__(
            self,
            ctx: OneDragonContext,
            node_max_retry_times: int = 3,
            op_name: str = '',
            timeout_seconds: float = -1,
            op_callback: Optional[Callable[[OperationResult], None]] = None,
            need_check_game_win: bool = True,
            op_to_enter_game: Optional[OperationBase] = None
    ):
        """初始化操作实例。

        Args:
            ctx: 用于管理操作状态的OneDragonContext实例。
            node_max_retry_times: 每个节点的最大重试次数。默认为3。
            op_name: 操作名称。默认为''。
            timeout_seconds: 操作超时时间（秒）。默认为-1（无超时）。
            op_callback: 操作完成后执行的回调函数。默认为None。
            need_check_game_win: 是否检查游戏窗口。默认为True。
            op_to_enter_game: 用于进入游戏的操作实例。默认为None。
        """
        OperationBase.__init__(self)

        # 指令自身属性
        self.ctx: OneDragonContext = ctx
        """上下文"""

        self.op_name: str = op_name
        """指令名称"""

        self.node_max_retry_times: int = node_max_retry_times
        """每个节点可以重试的次数"""

        self.timeout_seconds: float = timeout_seconds
        """指令超时时间"""

        self.op_callback: Optional[Callable[[OperationResult], None]] = op_callback
        """指令结束后的回调"""

        self.need_check_game_win: bool = need_check_game_win
        """是否检测游戏窗口"""

        self.op_to_enter_game: OperationBase = op_to_enter_game
        """用于打开游戏的指令"""

        # 指令节点网络相关属性
        self._node_map: dict[str, OperationNode] = {}
        """节点集合 key=节点名称 value=节点"""

        self._node_edges_map: dict[str, list[OperationEdge]] = {}
        """节点的边集合 key=节点名称 value=从该节点出发的边列表"""

        self._start_node: OperationNode | None = None
        """起始节点 初始化后才会有"""

        # 指令运行时相关属性
        self.operation_start_time: float = 0
        """指令开始执行的时间"""

        self.pause_start_time: float = 0
        """本次暂停开始的时间 on_pause时填入"""

        self.current_pause_time: float = 0
        """本次暂停的总时间 on_resume时填入"""

        self.pause_total_time: float = 0
        """暂停的总时间"""

        self.round_start_time: float = 0
        """本轮指令的开始时间"""

        self._current_node_start_time: Optional[float] = None
        """当前节点的开始运行时间"""

        self._current_node: OperationNode | None = None
        """当前执行的节点"""

        self._previous_node: OperationNode | None = None
        """上一个执行的节点"""

        self._previous_round_result: OperationRoundResult | None = None
        """上一个执行节点的结果"""

        self.node_clicked: bool = False
        """本节点是否已经完成了点击"""

        self.node_retry_times: int = 0
        """当前节点的重试次数"""

        self.last_screenshot: np.ndarray | None = None
        """上一次的截图 用于出错时保存"""

        self.last_screenshot_time: float = 0
        """上一次截图的时间"""

        self.node_status: dict[str, PreviousNodeStateProxy] = {}
        """已保存节点状态的字典"""

    def _init_before_execute(self):
        """在操作开始前初始化执行状态。

        此方法重置执行相关的属性并设置事件监听器。
        应在每次操作执行前调用。
        """
        now = time.time()

        # 初始化节点网络
        self._init_network()

        # 初始化相关属性
        self.operation_start_time: float = now
        self.pause_start_time: float = now
        self.current_pause_time: float = 0
        self.pause_total_time: float = 0
        self.round_start_time: float = 0

        # 重置节点状态
        self.node_retry_times = 0
        self.node_clicked = False
        self._current_node_start_time = now
        self._previous_round_result = None
        self.node_status.clear()

        # 监听事件
        self.ctx.run_context.event_bus.unlisten_all_event(self)
        self.ctx.run_context.event_bus.listen_event(ApplicationRunContextStateEventEnum.PAUSE, self._on_pause)
        self.ctx.run_context.event_bus.listen_event(ApplicationRunContextStateEventEnum.RESUME, self._on_resume)

        self.handle_init()

    def _analyse_node_annotations(self) -> tuple[OperationNode, list[OperationNode], list[OperationEdge]]:
        """
        扫描类方法的操作节点和边注解
        Returns:
            tuple[OperationNode, list[OperationNode], list[OperationEdge]]: 起始节点 节点列表 边列表
        """
        start_node: OperationNode | None = None
        node_list: list[OperationNode] = []
        edge_list: list[OperationEdge] = []

        node_name_map: dict[str, OperationNode] = {}
        edge_desc_list: list[OperationEdgeDesc] = []

        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            # 从方法对象上直接获取 @operation_node 附加的节点信息
            node: OperationNode = getattr(method, 'operation_node_annotation', None)
            if node is None:
                # 如果方法没有被 @operation_node 装饰，则不是节点，直接跳过
                continue

            node_name_map[node.cn] = node
            node_list.append(node)
            if node.is_start_node:
                if start_node is not None and start_node.cn != node.cn:
                    raise ValueError(f'存在多个起始节点 {start_node.cn} {node.cn}')
                start_node = node

            # 从方法对象上直接获取 @node_from 附加的节点信息
            edges: list[OperationEdgeDesc] = getattr(method, 'operation_edge_annotation', None)
            if edges is None:
                continue
            for edge in edges:
                edge.node_to_name = node.cn
                edge_desc_list.append(edge)

        for edge_desc in edge_desc_list:
            node_from = node_name_map.get(edge_desc.node_from_name, None)
            if node_from is None:
                raise ValueError('找不到节点 %s' % edge_desc.node_from_name)
            node_to = node_name_map.get(edge_desc.node_to_name, None)
            if node_to is None:
                raise ValueError('找不到节点 %s' % edge_desc.node_to_name)

            new_node = OperationEdge(
                node_from,
                node_to,
                success=edge_desc.success,
                status=edge_desc.status,
                ignore_status=edge_desc.ignore_status
            )
            edge_list.append(new_node)

        return start_node, node_list, edge_list

    def _init_network(self) -> None:
        """初始化操作节点网络。

        此方法通过以下步骤构建操作图：
        1. 从注解添加节点和边
        2. 从子类实现添加节点和边
        3. 构建用于图遍历的内部数据结构
        4. 确定起始节点
        """
        # 初始化节点和边集合
        self._node_edges_map.clear()
        self._node_map.clear()

        start_node, node_list, edge_list = self._analyse_node_annotations()

        # 添加节点
        for node in node_list:
            self._add_node(node)

        # 添加边
        op_in_map: dict[str, int] = {}  # 入度
        for edge in edge_list:
            from_id = edge.node_from.cn
            if from_id not in self._node_edges_map:
                self._node_edges_map[from_id] = []
            self._node_edges_map[from_id].append(edge)

            to_id = edge.node_to.cn
            if to_id not in op_in_map:
                op_in_map[to_id] = 0
            op_in_map[to_id] = op_in_map[to_id] + 1

        if start_node is None:  # 没有指定开始节点时 自动判断
            # 找出入度为0的开始点
            for node in node_list:
                if op_in_map.get(node.cn, 0) == 0:
                    if start_node is not None and start_node.cn != node.cn:
                        raise ValueError(f'存在多个起始节点 {start_node.cn} {node.cn}')
                    start_node = node

        if start_node is None:
            raise ValueError('找不到起始节点')

        start_node = self._add_check_game_node(start_node)
        # 初始化开始节点
        self._start_node = start_node
        self._current_node = start_node
        self._previous_node = None
        self._previous_round_result = None

    def _add_check_game_node(self, start_node: OperationNode) -> OperationNode:
        """
        在起始节点前 增加游戏窗口检查节点
        Args:
            start_node: 当前的起始节点

        Returns:
            OperationNode: 新的起始节点

        """
        if self.need_check_game_win and start_node is not None:
            check_game_window = OperationNode('检测游戏窗口', lambda _: self.check_game_window(), screenshot_before_round=False)
            self._add_node(check_game_window)

            open_and_enter_game = OperationNode('打开并进入游戏', lambda _: self.open_and_enter_game(), screenshot_before_round=False)
            self._add_node(open_and_enter_game)

            no_game_edge = OperationEdge(check_game_window, open_and_enter_game, success=False)
            with_game_edge = OperationEdge(check_game_window, start_node)
            enter_game_edge = OperationEdge(open_and_enter_game, start_node)

            self._node_edges_map[check_game_window.cn] = [no_game_edge, with_game_edge]
            self._node_edges_map[open_and_enter_game.cn] = [enter_game_edge]

            start_node = check_game_window

        return start_node

    def _add_node(self, node: OperationNode):
        """
        增加一个节点
        Args:
            node: 节点
        """
        if node.cn in self._node_map:
            raise ValueError(f'存在重复的节点 {node.cn}')
        self._node_map[node.cn] = node

    def check_game_window(self) -> OperationRoundResult:
        """检查游戏窗口是否准备就绪。

        Returns:
            OperationRoundResult: 如果游戏窗口准备就绪则成功，否则失败。
        """
        if self.ctx.is_game_window_ready:
            return self.round_success()
        else:
            return self.round_fail('未打开游戏窗口 %s' % self.ctx.controller.game_win.win_title)

    def open_and_enter_game(self) -> OperationRoundResult:
        """打开并进入游戏。

        Returns:
            OperationRoundResult: 基于游戏进入操作的结果。
        """
        if self.op_to_enter_game is None:
            return self.round_fail('未提供打开游戏方式')
        else:
            return self.round_by_op_result(self.op_to_enter_game.execute())

    def handle_init(self):
        """处理执行前的初始化。

        此方法应由子类实现以进行自定义初始化。
        注意：初始化应该全面，以便操作可以重复使用。
        """
        pass

    def execute(self) -> OperationResult:
        """循环执行操作直到完成。

        Returns:
            OperationResult: 操作执行的最终结果。
        """
        try:
            self._init_before_execute()
        except Exception:
            log.error('初始化失败', exc_info=True)
            return self.op_fail('初始化失败')

        op_result: Optional[OperationResult] = None
        while True:
            self.round_start_time = time.time()
            if self.timeout_seconds != -1 and self.operation_usage_time >= self.timeout_seconds:
                op_result = self.op_fail(Operation.STATUS_TIMEOUT)
                break
            if self.ctx.run_context.is_context_stop:
                op_result = self.op_fail('人工结束')
                break
            elif self.ctx.run_context.is_context_pause:
                time.sleep(1)
                continue

            try:
                round_result: OperationRoundResult = self._execute_one_round()
                if (self._current_node is None
                        or (self._current_node is not None and not self._current_node.mute)
                ):
                    node_name = 'none' if self._current_node is None else self._current_node.cn
                    from_node_name = 'none' if self._previous_node is None else self._previous_node.cn
                    round_result_status = 'none' if round_result is None else coalesce_gt(round_result.status, round_result.status_display, model='ui')
                    if (self._current_node is not None
                            and self._current_node.mute
                        and (round_result.result == OperationRoundResultEnum.WAIT or round_result.result == OperationRoundResultEnum.RETRY)):
                        pass
                    else:
                        arrow = f"{from_node_name} -> {node_name}" if self._previous_node is not None else node_name
                        log.info('%s 节点 %s 返回状态 %s', self.display_name, arrow, round_result_status)
                if self.ctx.run_context.is_context_pause:  # 有可能触发暂停的时候仍在执行指令 执行完成后 再次触发暂停回调 保证操作的暂停回调真正生效
                    self._on_pause()
            except Exception as e:
                round_result: OperationRoundResult = self.round_retry('异常')
                if self.last_screenshot is not None:
                    file_name = self.save_screenshot()
                    log.error('%s 执行出错 相关截图保存至 %s', self.display_name, file_name, exc_info=True)
                else:
                    log.error('%s 执行出错', self.display_name, exc_info=True)

            # 重试或者等待的
            if round_result.result == OperationRoundResultEnum.RETRY:
                self.node_retry_times += 1
                if self.node_retry_times <= self.node_max_retry_times:
                    continue
                else:
                    round_result.result = OperationRoundResultEnum.FAIL
            else:
                self.node_retry_times = 0

            if round_result.result == OperationRoundResultEnum.WAIT:
                continue

            # 成功或者失败的 找下一个节点
            next_node = self._get_next_node(round_result)
            if next_node is None:  # 没有下一个节点了 当前返回什么就是什么
                if round_result.result == OperationRoundResultEnum.SUCCESS:
                    op_result = self.op_success(round_result.status, round_result.data)
                    break
                elif round_result.result == OperationRoundResultEnum.FAIL:
                    op_result = self.op_fail(round_result.status, round_result.data)
                    break
                else:
                    log.error('%s 执行返回结果错误 %s', self.display_name, op_result)
                    op_result = self.op_fail(round_result.status)
                    break
            else:  # 继续下一个节点
                self._previous_round_result = round_result
                self._previous_node = self._current_node
                self._current_node = next_node
                self._reset_status_for_new_node()  # 充值状态
                continue

        self.after_operation_done(op_result)
        return op_result

    def _execute_one_round(self) -> OperationRoundResult:
        """执行当前操作节点的一轮。

        Returns:
            OperationRoundResult: 执行当前节点的结果。
        """
        if self._current_node is None:
            return self.round_fail('当前节点为空')

        if self._current_node.timeout_seconds is not None \
                and self._current_node_start_time is not None \
                and time.time() - self._current_node_start_time > self._current_node.timeout_seconds:
            return self.round_fail(Operation.STATUS_TIMEOUT)

        self.node_max_retry_times = self._current_node.node_max_retry_times

        if self._current_node.op_method is not None:
            if self._current_node.screenshot_before_round:
                self.screenshot()
            current_round_result: OperationRoundResult = self._current_node.op_method(self)
        elif self._current_node.op is not None:
            op_result = self._current_node.op.execute()
            current_round_result = self.round_by_op_result(op_result,
                                                           retry_on_fail=self._current_node.retry_on_op_fail,
                                                           wait=self._current_node.wait_after_op)
        else:
            return self.round_fail('节点处理函数和指令都没有设置')

        # 自动保存启用了 save_status 的节点状态
        if self._current_node.save_status and current_round_result.result in (
            OperationRoundResultEnum.SUCCESS, OperationRoundResultEnum.FAIL
        ):
            self.node_status[self._current_node.cn] = PreviousNodeStateProxy(self._current_node, current_round_result)

        return current_round_result

    def _get_next_node(self, current_round_result: OperationRoundResult):
        """根据当前轮结果找到下一个节点。

        Args:
            current_round_result: 当前轮执行的结果。

        Returns:
            OperationNode or None: 要执行的下一个节点，如果没有下一个节点则为None。
        """
        if self._current_node is None:
            return None
        edges = self._node_edges_map.get(self._current_node.cn)
        if edges is None or len(edges) == 0:  # 没有下一个节点了
            return None

        next_node_id: Optional[str] = None
        final_next_node_id: Optional[str] = None  # 兜底指令
        for edge in edges:
            if edge.success != (current_round_result.result == OperationRoundResultEnum.SUCCESS):
                continue

            if edge.ignore_status:
                final_next_node_id = edge.node_to.cn

            if edge.status is None and current_round_result.status is None:
                next_node_id = edge.node_to.cn
                break
            elif edge.status is None or current_round_result.status is None:
                continue
            elif edge.status == current_round_result.status:
                next_node_id = edge.node_to.cn
                break

        if next_node_id is not None:
            return self._node_map[next_node_id]
        elif final_next_node_id is not None:
            return self._node_map[final_next_node_id]
        else:
            return None

    def _reset_status_for_new_node(self) -> None:
        """进入新节点时重置状态。

        此方法为下一个节点执行初始化节点特定状态。
        """
        self.node_retry_times = 0  # 每个节点都可以重试
        self._current_node_start_time = time.time()  # 每个节点单独计算耗时
        self.node_clicked = False  # 重置节点点击

    def _on_pause(self, e=None):
        """操作暂停时触发的回调。

        注意：由于暂停触发时操作可能仍在执行，
        _execute_one_round会检查暂停状态并再次触发on_pause
        以确保暂停回调正确生效。
        子类应确保多次触发不会造成问题。

        Args:
            e: 事件参数（可选）。
        """
        if not self.ctx.run_context.is_context_pause:
            return
        self.current_pause_time = 0
        self.pause_start_time = time.time()
        self.handle_pause()

    def handle_pause(self) -> None:
        """处理暂停处理。

        此方法应由子类实现以进行自定义暂停处理。
        """
        pass

    def _on_resume(self, e=None):
        """操作恢复时触发的回调。

        Args:
            e: 事件参数（可选）。
        """
        if not self.ctx.run_context.is_context_running:
            return
        self.current_pause_time = time.time() - self.pause_start_time
        self.pause_total_time += self.current_pause_time
        self._current_node_start_time += self.current_pause_time
        self.handle_resume()

    def handle_resume(self) -> None:
        """处理恢复处理。

        此方法应由子类实现以进行自定义恢复处理。
        """
        pass

    @property
    def operation_usage_time(self) -> float:
        """获取操作执行时间（不包括暂停时间）。

        Returns:
            float: 实际执行时间（秒）。
        """
        return time.time() - self.operation_start_time - self.pause_total_time

    def screenshot(self):
        """截图并保存在内存中。

        此方法包装截图功能并将最后一张截图保存在内存中
        以用于错误处理。

        Returns:
            np.ndarray: 截图图像。
        """
        self.last_screenshot_time, self.last_screenshot = self.ctx.controller.screenshot()
        return self.last_screenshot

    def save_screenshot(self, prefix: Optional[str] = None) -> str:
        """保存最后一张截图并对UID进行遮罩。

        Args:
            prefix: 文件名的可选前缀。默认为类名。

        Returns:
            str: 保存截图的文件路径。
        """
        if self.last_screenshot is None:
            return ''
        if prefix is None:
            prefix = self.__class__.__name__
        return debug_utils.save_debug_image(self.last_screenshot, prefix=prefix)

    def save_screenshot_bytes(self) -> Optional[BytesIO]:
        """截图并保存为字节。

        Returns:
            BytesIO or None: 字节流对象，如果截图不存在则为None。
        """
        screen = self.screenshot()
        retval, buffer = cv2.imencode('.png', cv2.cvtColor(screen, cv2.COLOR_RGB2BGR))
        if retval:
            return BytesIO(buffer.tobytes())
        else:
            return None

    @cached_property
    def display_name(self) -> str:
        """获取此操作的显示名称。

        Returns:
            str: 格式化的显示名称。
        """
        return '指令[ %s ]' % self.op_name

    def after_operation_done(self, result: OperationResult):
        """处理操作完成后的处理。

        Args:
            result: 最终操作结果。
        """
        self.ctx.unlisten_all_event(self)
        if result.success:
            log.info('%s 执行成功 返回状态 %s', self.display_name, coalesce_gt(result.status, '成功', model='ui'))
        else:
            log.error('%s 执行失败 返回状态 %s', self.display_name, coalesce_gt(result.status, '失败', model='ui'))

        if self.op_callback is not None:
            self.op_callback(result)

    def round_success(self, status: str = None, data: Any = None,
                      wait: Optional[float] = None, wait_round_time: Optional[float] = None) -> OperationRoundResult:
        """创建成功的轮次结果。

        Args:
            status: 可选状态消息。默认为None。
            data: 可选返回数据。默认为None。
            wait: 等待时间（秒）。默认为None。
            wait_round_time: 等待直到轮次时间达到此值，如果设置了wait则忽略。默认为None。

        Returns:
            OperationRoundResult: 具有指定参数的成功结果。
        """
        self._after_round_wait(wait=wait, wait_round_time=wait_round_time)
        return OperationRoundResult(result=OperationRoundResultEnum.SUCCESS, status=status, data=data)

    def round_wait(self, status: str = None, data: Any = None,
                   wait: Optional[float] = None, wait_round_time: Optional[float] = None) -> OperationRoundResult:
        """创建等待的轮次结果。

        Args:
            status: 可选状态消息。默认为None。
            data: 可选返回数据。默认为None。
            wait: 等待时间（秒）。默认为None。
            wait_round_time: 等待直到轮次时间达到此值，如果设置了wait则忽略。默认为None。

        Returns:
            OperationRoundResult: 具有指定参数的等待结果。
        """
        self._after_round_wait(wait=wait, wait_round_time=wait_round_time)
        return OperationRoundResult(result=OperationRoundResultEnum.WAIT, status=status, data=data)

    def round_retry(self, status: str = None, data: Any = None,
                    wait: Optional[float] = None, wait_round_time: Optional[float] = None) -> OperationRoundResult:
        """创建重试的轮次结果。

        Args:
            status: 可选状态消息。默认为None。
            data: 可选返回数据。默认为None。
            wait: 等待时间（秒）。默认为None。
            wait_round_time: 等待直到轮次时间达到此值，如果设置了wait则忽略。默认为None。

        Returns:
            OperationRoundResult: 具有指定参数的重试结果。
        """
        self._after_round_wait(wait=wait, wait_round_time=wait_round_time)
        return OperationRoundResult(result=OperationRoundResultEnum.RETRY, status=status, data=data)

    def round_fail(self, status: str = None, data: Any = None,
                   wait: Optional[float] = None, wait_round_time: Optional[float] = None) -> OperationRoundResult:
        """创建失败的轮次结果。

        Args:
            status: 可选状态消息。默认为None。
            data: 可选返回数据。默认为None。
            wait: 等待时间（秒）。默认为None。
            wait_round_time: 等待直到轮次时间达到此值，如果设置了wait则忽略。默认为None。

        Returns:
            OperationRoundResult: 具有指定参数的失败结果。
        """
        self._after_round_wait(wait=wait, wait_round_time=wait_round_time)
        return OperationRoundResult(result=OperationRoundResultEnum.FAIL, status=status, data=data)

    def _after_round_wait(self, wait: Optional[float] = None, wait_round_time: Optional[float] = None):
        """每轮操作后的等待。

        Args:
            wait: 等待时间（秒）。默认为None。
            wait_round_time: 等待直到轮次时间达到此值，如果设置了wait则忽略。默认为None。
        """
        if wait is not None and wait > 0:
            time.sleep(wait)
        elif wait_round_time is not None and wait_round_time > 0:
            to_wait = wait_round_time - (time.time() - self.round_start_time)
            if to_wait > 0:
                time.sleep(to_wait)

    def round_by_op_result(self, op_result: OperationResult, retry_on_fail: bool = False,
                           wait: Optional[float] = None, wait_round_time: Optional[float] = None) -> OperationRoundResult:
        """根据操作结果获取当前轮次结果。

        Args:
            op_result: 要转换的操作结果。
            retry_on_fail: 失败时是否重试。默认为False。
            wait: 等待时间（秒）。默认为None。
            wait_round_time: 等待直到轮次时间达到此值，如果设置了wait则忽略。默认为None。

        Returns:
            OperationRoundResult: 转换后的轮次结果。
        """
        if op_result.success:
            return self.round_success(status=op_result.status, data=op_result.data, wait=wait,
                                      wait_round_time=wait_round_time)
        elif retry_on_fail:
            return self.round_retry(status=op_result.status, data=op_result.data, wait=wait,
                                    wait_round_time=wait_round_time)
        else:
            return self.round_fail(status=op_result.status, data=op_result.data, wait=wait,
                                   wait_round_time=wait_round_time)

    def round_by_find_and_click_area(
            self,
            screen: np.ndarray = None,
            screen_name: str = None, area_name: str = None,
            success_wait: Optional[float] = None, success_wait_round: Optional[float] = None,
            retry_wait: Optional[float] = None, retry_wait_round: Optional[float] = None,
            until_find_all: list[tuple[str, str]] = None,
            until_not_find_all: list[tuple[str, str]] = None,
    ) -> OperationRoundResult:
        """在屏幕上查找并点击目标区域。

        Args:
            screen: 截图图像。默认为None（将截取新截图）。
            screen_name: 屏幕名称。默认为None。
            area_name: 区域名称。默认为None。
            success_wait: 成功后等待时间（秒）。默认为None。
            success_wait_round: 成功后等待直到轮次时间达到此值，如果设置了success_wait则忽略。默认为None。
            retry_wait: 失败后等待时间（秒）。默认为None。
            retry_wait_round: 失败后等待直到轮次时间达到此值，如果设置了retry_wait则忽略。默认为None。
            until_find_all: 点击直到找到所有目标 [(屏幕, 区域)]。默认为None。
            until_not_find_all: 点击直到未找到所有目标 [(屏幕, 区域)]。默认为None。

        Returns:
            OperationRoundResult: 点击结果。
        """
        if screen is None:
            screen = self.last_screenshot

        if screen_name is None or area_name is None:
            return self.round_fail('未指定画面区域')

        if until_find_all is not None and self.node_clicked:
            all_found: bool = True
            for (until_screen_name, until_area_name) in until_find_all:
                result = screen_utils.find_area(ctx=self.ctx, screen=screen, screen_name=until_screen_name, area_name=until_area_name)
                if result != FindAreaResultEnum.TRUE:
                    all_found = False
                    break

            if all_found:
                return self.round_success(status=area_name, wait=success_wait, wait_round_time=success_wait_round)

        if until_not_find_all is not None and self.node_clicked:
            any_found: bool = False
            for (until_screen_name, until_area_name) in until_not_find_all:
                result = screen_utils.find_area(ctx=self.ctx, screen=screen, screen_name=until_screen_name, area_name=until_area_name)
                if result == FindAreaResultEnum.TRUE:
                    any_found = True
                    break

            if not any_found:
                return self.round_success(status=area_name, wait=success_wait, wait_round_time=success_wait_round)

        click = screen_utils.find_and_click_area(ctx=self.ctx, screen=screen, screen_name=screen_name, area_name=area_name)
        if click == OcrClickResultEnum.OCR_CLICK_SUCCESS:
            self.node_clicked = True
            self.update_screen_after_operation(screen_name, area_name)
            if until_find_all is None and until_not_find_all is None:
                return self.round_success(status=area_name, wait=success_wait, wait_round_time=success_wait_round)
            else:
                return self.round_wait(status=area_name, wait=success_wait, wait_round_time=success_wait_round)
        elif click == OcrClickResultEnum.OCR_CLICK_NOT_FOUND:
            return self.round_retry(status=f'未找到 {area_name}', wait=retry_wait, wait_round_time=retry_wait_round)
        elif click == OcrClickResultEnum.OCR_CLICK_FAIL:
            return self.round_retry(status=f'点击失败 {area_name}', wait=retry_wait, wait_round_time=retry_wait_round)
        elif click == OcrClickResultEnum.AREA_NO_CONFIG:
            return self.round_fail(status=f'区域未配置 {area_name}')
        else:
            return self.round_retry(status='未知状态', wait=retry_wait, wait_round_time=retry_wait_round)

    def round_by_find_area(self, screen: np.ndarray, screen_name: str, area_name: str,
                           success_wait: Optional[float] = None, success_wait_round: Optional[float] = None,
                           retry_wait: Optional[float] = None, retry_wait_round: Optional[float] = None
                           ) -> OperationRoundResult:
        """检查是否能在屏幕上找到目标区域。

        Args:
            screen: 截图图像。
            screen_name: 屏幕名称。
            area_name: 区域名称。
            success_wait: 成功后等待时间（秒）。默认为None。
            success_wait_round: 成功后等待直到轮次时间达到此值，如果设置了success_wait则忽略。默认为None。
            retry_wait: 失败后等待时间（秒）。默认为None。
            retry_wait_round: 失败后等待直到轮次时间达到此值，如果设置了retry_wait则忽略。默认为None。

        Returns:
            OperationRoundResult: 匹配结果。
        """
        result = screen_utils.find_area(ctx=self.ctx, screen=screen, screen_name=screen_name, area_name=area_name)
        if result == FindAreaResultEnum.AREA_NO_CONFIG:
            return self.round_fail(status=f'区域未配置 {area_name}')
        elif result == FindAreaResultEnum.TRUE:
            return self.round_success(status=area_name, wait=success_wait, wait_round_time=success_wait_round)
        else:
            return self.round_retry(status=f'未找到 {area_name}', wait=retry_wait, wait_round_time=retry_wait_round)

    def round_by_click_area(
            self, screen_name: str, area_name: str, click_left_top: bool = False,
            success_wait: Optional[float] = None, success_wait_round: Optional[float] = None,
            retry_wait: Optional[float] = None, retry_wait_round: Optional[float] = None
    ) -> OperationRoundResult:
        """点击特定区域。

        Args:
            screen_name: 屏幕名称。
            area_name: 区域名称。
            click_left_top: 是否点击左上角。默认为False。
            success_wait: 成功后等待时间（秒）。默认为None。
            success_wait_round: 成功后等待直到轮次时间达到此值，如果设置了success_wait则忽略。默认为None。
            retry_wait: 失败后等待时间（秒）。默认为None。
            retry_wait_round: 失败后等待直到轮次时间达到此值，如果设置了retry_wait则忽略。默认为None。

        Returns:
            OperationRoundResult: 点击结果。
        """
        area = self.ctx.screen_loader.get_area(screen_name, area_name)
        if area is None:
            return self.round_fail(status=f'区域未配置 {area_name}')

        if click_left_top:
            to_click = area.left_top
        else:
            to_click = area.center
        click = self.ctx.controller.click(pos=to_click, pc_alt=area.pc_alt)
        if click:
            self.update_screen_after_operation(screen_name, area_name)
            return self.round_success(status=area_name, wait=success_wait, wait_round_time=success_wait_round)
        else:
            return self.round_retry(status=f'点击失败 {area_name}', wait=retry_wait, wait_round_time=retry_wait_round)

    def round_by_ocr_and_click(
            self,
            screen: np.ndarray, target_cn: str,
            area: Optional[ScreenArea] = None, lcs_percent: float = 0.5,
            success_wait: Optional[float] = None, success_wait_round: Optional[float] = None,
            retry_wait: Optional[float] = None, retry_wait_round: Optional[float] = None,
            color_range: Optional[list] = None,
            offset: Optional[Point] = None,
    ) -> OperationRoundResult:
        """使用OCR在区域内查找目标文本并点击。

        Args:
            screen: 游戏截图。
            target_cn: 要查找的目标文本。
            area: 要搜索的目标区域。默认为None（搜索整个屏幕）。
            lcs_percent: 文本匹配阈值。默认为0.5。
            success_wait: 成功后等待时间（秒）。默认为None。
            success_wait_round: 成功后等待直到轮次时间达到此值，如果设置了success_wait则忽略。默认为None。
            retry_wait: 失败后等待时间（秒）。默认为None。
            retry_wait_round: 失败后等待直到轮次时间达到此值，如果设置了retry_wait则忽略。默认为None。
            color_range: 文本匹配的颜色范围。默认为None。
            offset: 点击位置的偏移量。默认为None。

        Returns:
            OperationRoundResult: 点击结果。
        """
        # 优先使用OCR缓存服务
        if self.ctx.env_config.ocr_cache:
            ocr_result_map = self.ctx.ocr_service.get_ocr_result_map(
                image=screen,
                color_range=color_range,
                rect=area.rect if area is not None else None
            )
        else:
            # 回退到原有方法
            to_ocr_part = screen if area is None else cv2_utils.crop_image_only(screen, area.rect)
            if color_range is not None:
                mask = cv2.inRange(to_ocr_part, color_range[0], color_range[1])
                mask = cv2_utils.dilate(mask, 5)
                to_ocr_part = cv2.bitwise_and(to_ocr_part, to_ocr_part, mask=mask)
                # cv2_utils.show_image(to_ocr_part, win_name='round_by_ocr_and_click', wait=0)

            ocr_result_map = self.ctx.ocr.run_ocr(to_ocr_part)

        to_click: Optional[Point] = None
        ocr_result_list: list[str] = []
        mrl_list: list[MatchResultList] = []

        for ocr_result, mrl in ocr_result_map.items():
            if mrl.max is None:
                continue
            ocr_result_list.append(ocr_result)
            mrl_list.append(mrl)

        results = difflib.get_close_matches(gt(target_cn, 'game'), ocr_result_list, n=1)
        if results is None or len(results) == 0:
            return self.round_retry(f'找不到 {target_cn}', wait=retry_wait, wait_round_time=retry_wait_round)

        for result in results:
            idx: int = ocr_result_list.index(result)
            ocr_result = ocr_result_list[idx]
            mrl = mrl_list[idx]
            if str_utils.find_by_lcs(gt(target_cn, 'game'), ocr_result, percent=lcs_percent):
                to_click = mrl.max.center
                break

        if to_click is None:
            return self.round_retry(f'找不到 {target_cn}', wait=retry_wait, wait_round_time=retry_wait_round)

        if area is not None:
            to_click = to_click + area.left_top

        if offset is not None:
            to_click = to_click + offset

        click = self.ctx.controller.click(to_click)
        if click:
            return self.round_success(target_cn, wait=success_wait, wait_round_time=success_wait_round)
        else:
            return self.round_retry(f'点击 {target_cn} 失败', wait=retry_wait, wait_round_time=retry_wait_round)

    def round_by_ocr_and_click_by_priority(
            self,
            target_cn_list: list[str],
            screen: MatLike | None = None,
            ignore_cn_list: list[str] = None,
            area: Optional[ScreenArea] = None,
            success_wait: Optional[float] = None, success_wait_round: Optional[float] = None,
            retry_wait: Optional[float] = None, retry_wait_round: Optional[float] = None,
            color_range: Optional[list[list[int]]] = None,
            offset: Optional[Point] = None,
    ) -> OperationRoundResult:
        """使用OCR按优先级在区域内查找文本并点击。

        Args:
            screen: 游戏截图。
            target_cn_list: 按优先级排序的目标文本列表。
            ignore_cn_list: 要忽略的文本列表。目标列表中的某些元素仅用于防止匹配错误，例如["领取", "已领取"]可以防止"已领取*1"匹配到"领取"，而"已领取"不需要实际匹配。默认为None。
            area: 要搜索的目标区域。默认为None。
            success_wait: 成功后等待时间（秒）。默认为None。
            success_wait_round: 成功后等待直到轮次时间达到此值，如果设置了success_wait则忽略。默认为None。
            retry_wait: 失败后等待时间（秒）。默认为None。
            retry_wait_round: 失败后等待直到轮次时间达到此值，如果设置了retry_wait则忽略。默认为None。
            color_range: 文本匹配的颜色范围。默认为None。
            offset: 点击位置的偏移量。默认为None。

        Returns:
            OperationRoundResult: 点击结果。
        """
        if screen is None:
            screen = self.last_screenshot

        # 优先使用OCR缓存服务
        if self.ctx.env_config.ocr_cache:
            ocr_result_map = self.ctx.ocr_service.get_ocr_result_map(
                image=screen,
                color_range=color_range,
                rect=area.rect if area is not None else None
            )
        else:
            # 回退到原有方法
            to_ocr_part = screen if area is None else cv2_utils.crop_image_only(screen, area.rect)
            if color_range is not None:
                mask = cv2.inRange(to_ocr_part, np.array(color_range[0]), np.array(color_range[1]))
                mask = cv2_utils.dilate(mask, 5)
                to_ocr_part = cv2.bitwise_and(to_ocr_part, to_ocr_part, mask=mask)
                # cv2_utils.show_image(to_ocr_part, win_name='round_by_ocr_and_click', wait=0)

            ocr_result_map = self.ctx.ocr.run_ocr(to_ocr_part)
            if area is not None:
                for _, mrl in ocr_result_map.items():
                    mrl.add_offset(area.left_top)

        match_word, match_word_mrl = ocr_utils.match_word_list_by_priority(
            ocr_result_map,
            target_cn_list,
            ignore_list=ignore_cn_list
        )
        if match_word is not None and match_word_mrl is not None and match_word_mrl.max is not None:
            to_click = match_word_mrl.max.center

            if offset is not None:
                to_click = to_click + offset

            self.ctx.controller.click(to_click)
            return self.round_success(status=match_word, wait=success_wait, wait_round_time=success_wait_round)

        return self.round_retry(status='未匹配到目标文本', wait=retry_wait, wait_round_time=retry_wait_round)

    def round_by_ocr(
            self,
            screen: np.ndarray,
            target_cn: str,
            area: Optional[ScreenArea] = None,
            lcs_percent: float = 0.5,
            success_wait: Optional[float] = None, success_wait_round: Optional[float] = None,
            retry_wait: Optional[float] = None, retry_wait_round: Optional[float] = None,
            color_range: Optional[list] = None,
    ) -> OperationRoundResult:
        """使用OCR在区域内查找目标文本。

        Args:
            screen: 游戏截图。
            target_cn: 要查找的目标文本。
            area: 要搜索的目标区域。默认为None。
            lcs_percent: 文本匹配阈值。默认为0.5。
            success_wait: 成功后等待时间（秒）。默认为None。
            success_wait_round: 成功后等待直到轮次时间达到此值，如果设置了success_wait则忽略。默认为None。
            retry_wait: 失败后等待时间（秒）。默认为None。
            retry_wait_round: 失败后等待直到轮次时间达到此值，如果设置了retry_wait则忽略。默认为None。
            color_range: 文本匹配的颜色范围。默认为None。

        Returns:
            OperationRoundResult: 匹配结果。
        """
        if screen_utils.find_by_ocr(self.ctx, screen, target_cn,
                                    lcs_percent=lcs_percent,
                                    area=area, color_range=color_range):
            return self.round_success(target_cn, wait=success_wait, wait_round_time=success_wait_round)
        else:
            return self.round_retry(f'找不到 {target_cn}', wait=retry_wait, wait_round_time=retry_wait_round)


    def round_by_goto_screen(self, screen: Optional[np.ndarray] = None, screen_name: Optional[str] = None,
                             success_wait: Optional[float] = None, success_wait_round: Optional[float] = None,
                             retry_wait: Optional[float] = 1, retry_wait_round: Optional[float] = None) -> OperationRoundResult:
        """从当前屏幕导航到目标屏幕。

        Args:
            screen: 游戏截图。默认为None（将截取新截图）。
            screen_name: 目标屏幕名称。默认为None。
            success_wait: 成功后等待时间（秒）。默认为None。
            success_wait_round: 成功后等待时间减去当前轮执行时间。默认为None。
            retry_wait: 不成功时等待时间（秒）。默认为1。
            retry_wait_round: 不成功时等待时间减去当前轮执行时间。默认为None。

        Returns:
            OperationRoundResult: 导航结果。
        """
        if screen is None:
            screen = self.last_screenshot

        current_screen_name = screen_utils.get_match_screen_name(self.ctx, screen)
        self.ctx.screen_loader.update_current_screen_name(current_screen_name)
        if current_screen_name is None:
            return self.round_retry(Operation.STATUS_SCREEN_UNKNOWN, wait=retry_wait, wait_round_time=retry_wait_round)
        log.debug(f'当前识别画面 {current_screen_name}')
        if current_screen_name == screen_name:
            return self.round_success(current_screen_name, wait=success_wait, wait_round_time=success_wait_round)

        route = self.ctx.screen_loader.get_screen_route(current_screen_name, screen_name)
        if route is None or not route.can_go:
            return self.round_fail(f'无法从 {current_screen_name} 前往 {screen_name}')

        result = self.round_by_find_and_click_area(screen, current_screen_name, route.node_list[0].from_area)
        if result.is_success:
            self.ctx.screen_loader.update_current_screen_name(route.node_list[0].to_screen)
            return self.round_wait(result.status, wait=retry_wait, wait_round_time=retry_wait_round)
        else:
            return self.round_retry(result.status, wait=retry_wait, wait_round_time=retry_wait_round)

    def update_screen_after_operation(self, screen_name: str, area_name: str) -> None:
        """点击某个区域后尝试更新当前画面。

        Args:
            screen_name: 屏幕名称。
            area_name: 区域名称。
        """
        area = self.ctx.screen_loader.get_area(screen_name, area_name)
        if area.goto_list is not None and len(area.goto_list) > 0:
            self.ctx.screen_loader.update_current_screen_name(area.goto_list[0])

    def check_and_update_current_screen(self, screen: np.ndarray | None = None, screen_name_list: Optional[list[str]] = None) -> str:
        """识别当前画面的名称并保存起来。

        Args:
            screen: 游戏截图。默认为None。
            screen_name_list: 传入时只判断这里的画面。默认为None。

        Returns:
            str: 画面名称。
        """
        if screen is None:
            screen = self.last_screenshot
        current_screen_name = screen_utils.get_match_screen_name(self.ctx, screen,
                                                                 screen_name_list=screen_name_list)
        self.ctx.screen_loader.update_current_screen_name(current_screen_name)
        return current_screen_name

    def check_screen_with_can_go(self, screen: np.ndarray, screen_name: str) -> tuple[str, bool]:
        """识别当前画面的名称并判断能否前往目标画面。

        Args:
            screen: 游戏截图。
            screen_name: 目标画面名称。

        Returns:
            tuple[str, bool]: 当前画面名称和能否前往目标画面。
        """
        current_screen_name = self.check_and_update_current_screen(screen)
        route = self.ctx.screen_loader.get_screen_route(current_screen_name, screen_name)
        can_go = current_screen_name == screen_name or (route is not None and route.can_go)
        return current_screen_name, can_go

    def check_current_can_go(self, screen_name: str) -> bool:
        """判断当前画面能否前往目标画面（需要已识别当前画面）。

        Args:
            screen_name: 目标画面名称。

        Returns:
            bool: 能否前往目标画面。
        """
        current_screen_name = self.ctx.screen_loader.current_screen_name
        route = self.ctx.screen_loader.get_screen_route(current_screen_name, screen_name)
        return route is not None and route.can_go

    @property
    def previous_node(self) -> PreviousNodeStateProxy:
        """
        获取一个代理对象，用于安全地访问上一个节点的执行状态和结果。

        在节点的执行函数中，可以通过 `self.previous_node` 来获取前一个节点的信息，
        这对于根据上一步的结果来决定当前步骤的行为非常有用。

        Returns:
            PreviousNodeStateProxy: 一个包含上一个节点状态和结果的代理对象。

        Example:
            @operation_node(name='处理节点')
            def process_node(self) -> OperationRoundResult:
                # 检查上一个节点是否成功，并且状态是'前置完成'
                if self.previous_node.is_success and self.previous_node.status == '前置完成':
                    print(f'来自节点: {self.previous_node.name}')
                    # 使用上一个节点返回的数据
                    prev_data = self.previous_node.data
                    # ... 进行处理 ...
                return self.round_success()
        """
        return PreviousNodeStateProxy(self._previous_node, self._previous_round_result)
