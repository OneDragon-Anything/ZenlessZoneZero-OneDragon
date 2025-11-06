from __future__ import annotations

from typing import Optional, Callable, List, TYPE_CHECKING, Literal
from io import BytesIO
from enum import Enum
from dataclasses import dataclass

from one_dragon.utils.i18_utils import gt
from one_dragon.base.operation.operation_round_result import OperationRoundResult, OperationRoundResultEnum

if TYPE_CHECKING:
    from one_dragon.base.operation.application_base import Application
    from one_dragon.base.operation.operation import Operation


class NotifyTiming(str, Enum):
    """通知触发时机枚举"""
    BEFORE = 'before'
    AFTER = 'after'
    AFTER_SUCCESS = 'after_success'
    AFTER_FAIL = 'after_fail'


class CaptureStrategy(str, Enum):
    """截图捕获策略枚举"""
    NONE = 'none'
    BEFORE = 'before'
    AFTER = 'after'


def _should_notify(app: Application, desc: Optional[NodeNotifyDesc] = None) -> bool:
    """
    检查是否应该发送通知

    Args:
        app: Application 实例
        desc: 节点通知描述（可选，用于节点级通知）

    Returns:
        bool: 是否应该发送通知
    """
    # 检查全局通知开关
    if not app.ctx.notify_config.enable_notify:
        return False

    # 检查 before 通知开关
    if desc and desc.when == NotifyTiming.BEFORE:
        if not app.ctx.notify_config.enable_before_notify:
            return False

    # 检查应用级别的通知开关
    if app.app_id and not getattr(app.ctx.notify_config, app.app_id, False):
        return False

    return True


def _should_send_image(app: Application, desc: Optional[NodeNotifyDesc] = None) -> bool:
    """
    检查是否应该发送图片

    Args:
        app: Application 实例
        desc: 节点通知描述（可选）

    Returns:
        bool: 是否应该发送图片
    """
    # 如果描述中明确指定了是否发送图片，优先使用
    if desc and desc.send_image is not None:
        return desc.send_image

    # 否则使用全局配置
    return app.ctx.push_service.push_config.send_image


def _build_application_message(app_name: str, status: str) -> str:
    """
    构建应用级别的通知消息

    Args:
        app_name: 应用名称
        status: 状态（成功/失败/开始）

    Returns:
        str: 格式化的消息
    """
    return f"{gt('任务「')}{app_name}{gt('」运行')}{status}\n"


def _build_node_message(
    app_name: str,
    node_name: str,
    phase: str,
    custom_message: Optional[str] = None,
    status: Optional[str] = None,
    detail: bool = False
) -> str:
    """
    构建节点级别的通知消息

    Args:
        app_name: 应用名称
        node_name: 节点名称
        phase: 阶段描述（成功/失败/开始/结束）
        custom_message: 自定义消息
        status: 状态信息
        detail: 是否显示详细信息（节点名和状态）

    Returns:
        str: 格式化的消息
    """
    if detail:
        # 显示详细信息：任务名、节点名、阶段、状态
        status_text = f" [{status}]" if status else ''
        msg = (f"{gt('任务「')}{app_name}{gt('」节点「')}{node_name}"
               f"{gt('」')}{phase}{status_text}\n")
    else:
        # 简化消息：只显示任务名和阶段
        msg = f"{gt('任务「')}{app_name}{gt('」')}{phase}\n"

    if custom_message:
        msg += custom_message + '\n'

    return msg


def _get_phase_text(timing: NotifyTiming, success: Optional[bool]) -> str:
    """
    根据时机和成功状态获取阶段文本

    Args:
        timing: 通知时机
        success: 是否成功（None 表示未知）

    Returns:
        str: 阶段文本
    """
    if timing == NotifyTiming.BEFORE:
        return gt('开始')

    if timing in (NotifyTiming.AFTER, NotifyTiming.AFTER_SUCCESS, NotifyTiming.AFTER_FAIL):
        if success is True:
            return gt('成功')
        elif success is False:
            return gt('失败')
        else:
            return gt('结束')

    return ''


@dataclass
class _NotifyImageContext:
    """通知图片上下文 - 管理截图状态（内部使用）"""
    before_image: Optional[BytesIO] = None
    after_image: Optional[BytesIO] = None

    def get_image(self, strategy: CaptureStrategy) -> Optional[BytesIO]:
        """根据策略获取对应的图片"""
        if strategy == CaptureStrategy.BEFORE:
            return self.before_image
        elif strategy == CaptureStrategy.AFTER:
            return self.after_image
        return None


def application_notify(app: Application, is_success: Optional[bool]) -> None:
    """向外部推送应用运行状态通知。

    参数含义与原 `Application.notify` 一致。该函数被抽离出来便于复用与单元测试，
    并避免在运行期产生循环依赖（此处仅向下依赖 Push 与 i18n）。

    Args:
        app: Application 实例
        is_success: True=成功, False=失败, None=开始
    """
    # 验证配置
    if not _should_notify(app):
        return

    # before 通知需要额外检查
    if is_success is None:
        if not app.ctx.notify_config.enable_before_notify:
            return

    # 确定状态和图片来源
    if is_success is True:
        status = gt('成功')
    elif is_success is False:
        status = gt('失败')
    else:  # is_success is None
        status = gt('开始')

    # 构建消息
    app_name = getattr(app, 'op_name', '')
    message = _build_application_message(app_name, status)

    # 异步推送
    app.ctx.push_service.push_async(message)


class NodeNotifyDesc:
    """操作节点通知描述。

    用法示例：

    # 基础用法
    @node_notify()                              # 节点结束后（成功或失败）发送通知
    def some_node(...): ...

    # 控制触发时机
    @node_notify(when='before')                 # 节点开始前发送"开始"通知
    @node_notify(when='after_success')          # 仅成功后发送通知
    @node_notify(when='after_fail')             # 仅失败后发送通知
    def another_node(...): ...

    # 显示详细信息
    @node_notify(detail=True)                   # 显示节点名和返回状态
    def detailed_node(...): ...

    # 自定义消息
    @node_notify(custom_message='处理完成')     # 添加自定义消息
    def custom_node(...): ...

    # 控制图片发送
    @node_notify(send_image=True)               # 强制发送截图
    @node_notify(send_image=False)              # 强制不发送截图
    @node_notify(send_image=None)               # 使用全局配置（默认）
    def image_node(...): ...

    # 组合使用
    @node_notify(when='before')
    @node_notify(when='after_success', detail=True, send_image=True)
    def important_node(...): ...

    参数说明：
    - when: 控制通知触发时机（before/after/after_success/after_fail）
    - custom_message: 自定义附加消息，会追加在标准消息后
    - send_image: 控制是否发送截图（True/False/None），None 表示使用全局配置
    - detail: 是否显示详细信息（节点名和返回状态）

    自动行为：
    - 截图策略：when='before' 时使用 before 截图，其他时机使用 after 截图
    - 多次装饰：可在同一函数上多次使用以实现多种时机通知

    注意：装饰器只负责元数据标注，执行框架会在合适的生命周期钩子中读取
    func.operation_notify_annotation 并调用相应的通知函数。
    """

    def __init__(
            self,
            when: Literal['before', 'after', 'after_success', 'after_fail'] = 'after',
            custom_message: Optional[str] = None,
            send_image: Optional[bool] = None,
            detail: bool = False,
    ):
        """
        初始化节点通知描述

        Args:
            when: 通知触发时机，控制何时发送通知
                - 'before': 节点开始前发送通知
                - 'after': 节点结束后发送通知（无论成功或失败）
                - 'after_success': 仅在节点成功后发送通知
                - 'after_fail': 仅在节点失败后发送通知
            custom_message: 自定义附加消息，会追加在标准消息后面
            send_image: 是否随通知发送截图
                - True: 强制发送截图
                - False: 强制不发送截图
                - None: 使用全局配置（push_config.send_image）
            detail: 是否显示详细信息（节点名称和返回状态）
                - True: 显示完整信息，如"任务「xxx」节点「node」成功 [status]"
                - False: 简化消息，如"任务「xxx」成功"
        """
        try:
            self.when: NotifyTiming = NotifyTiming(when)
        except ValueError:
            valid_values = [t.value for t in NotifyTiming]
            raise ValueError(f"when 必须是 {valid_values} 之一, 当前: {when}")

        # 捕获策略自动根据触发时机决定
        if self.when == NotifyTiming.BEFORE:
            self.capture: CaptureStrategy = CaptureStrategy.BEFORE
        else:
            self.capture: CaptureStrategy = CaptureStrategy.AFTER

        self.custom_message: Optional[str] = custom_message
        self.send_image: Optional[bool] = send_image
        self.detail: bool = detail


def node_notify(
    when: Literal['before', 'after', 'after_success', 'after_fail'] = 'after',
    custom_message: Optional[str] = None,
    send_image: Optional[bool] = None,
    detail: bool = False,
):
    """为操作节点函数附加通知元数据的装饰器（仿照 operation_edge.node_from 实现）。

    Args:
        when: 通知触发时机，可选 'before' | 'after' | 'after_success' | 'after_fail'
            - 'before': 节点开始前发送通知
            - 'after': 节点结束后发送通知（无论成功或失败）
            - 'after_success': 仅在节点成功后发送通知
            - 'after_fail': 仅在节点失败后发送通知
        custom_message: 自定义附加消息，会追加在标准消息后面
        send_image: 是否随通知发送截图
            - True: 强制发送截图（覆盖全局配置）
            - False: 强制不发送截图（覆盖全局配置）
            - None: 使用全局配置（push_config.send_image，默认值）
        detail: 是否显示详细信息（节点名称和返回状态），默认 False
            - True: 显示完整信息，如"任务「xxx」节点「node」成功 [status]"
            - False: 简化消息，如"任务「xxx」成功"
    """

    def decorator(func: Callable):
        if not hasattr(func, 'operation_notify_annotation'):
            setattr(func, 'operation_notify_annotation', [])
        lst: List[NodeNotifyDesc] = getattr(func, 'operation_notify_annotation')
        lst.append(NodeNotifyDesc(
            when=when,
            custom_message=custom_message,
            send_image=send_image,
            detail=detail,
        ))
        return func

    return decorator


def send_node_notify(
        app: Application,
        node_name: str,
        success: Optional[bool],
        desc: NodeNotifyDesc,
        image: Optional[BytesIO] = None,
        status: Optional[str] = None,
):
    """
    发送节点级通知

    Args:
        app: Application 实例
        node_name: 节点名称
        success: 是否成功（None=未知）
        desc: 节点通知描述
        image: 截图（可选）
        status: 状态信息（可选）
    """
    # 验证配置
    if not _should_notify(app, desc):
        return

    # 判定是否需要发送（after_success / after_fail 需要匹配）
    if desc.when == NotifyTiming.AFTER_SUCCESS and success is not True:
        return
    if desc.when == NotifyTiming.AFTER_FAIL and success is not False:
        return

    # 获取阶段文本
    phase = _get_phase_text(desc.when, success)

    # 构建消息
    msg = _build_node_message(
        app_name=app.op_name,
        node_name=node_name,
        phase=phase,
        custom_message=desc.custom_message,
        status=status,
        detail=desc.detail
    )

    # 判断是否发送图片
    should_send_image = _should_send_image(app, desc)
    img = image if should_send_image else None

    # 异步推送
    app.ctx.push_service.push_async(msg, img)


def process_node_notifications(
    operation: Operation,
    phase: Literal['before', 'after'],
    round_result: Optional[OperationRoundResult] = None
):
    """
    集中处理一个节点的所有通知

    Args:
        operation: Operation 实例（含 ctx / save_screenshot_bytes 等方法）
        phase: 'before' 或 'after'
        round_result: OperationRoundResult 实例（before 阶段为 None）
    """
    # 当前节点或方法不存在时直接返回
    current_node = operation.get_current_node()
    if current_node is None or current_node.op_method is None:
        return

    notify_list: List[NodeNotifyDesc] = getattr(current_node.op_method, 'operation_notify_annotation', [])
    if not notify_list:
        return

    # 使用上下文对象管理图片状态
    image_ctx = _NotifyImageContext()

    if phase == 'before':
        # before 阶段：捕获需要的截图并发送 before 通知
        if any(d.capture == CaptureStrategy.BEFORE for d in notify_list):
            image_ctx.before_image = operation.last_screenshot
            setattr(operation, '_node_notify_image_ctx', image_ctx)

        for desc in notify_list:
            if desc.when == NotifyTiming.BEFORE:
                img = image_ctx.get_image(desc.capture)
                send_node_notify(operation, current_node.cn, None, desc, image=img)

    elif phase == 'after':
        # after 阶段：处理 after 相关的通知
        if round_result is None:
            return

        # 恢复 before 阶段的图片上下文
        if hasattr(operation, '_node_notify_image_ctx'):
            image_ctx = getattr(operation, '_node_notify_image_ctx')

        # 捕获 after 截图（如果需要）
        if any(d.capture == CaptureStrategy.AFTER for d in notify_list):
            image_ctx.after_image = operation.last_screenshot

        # 确定成功状态
        success_flag: Optional[bool] = None
        if round_result.result in (OperationRoundResultEnum.SUCCESS, OperationRoundResultEnum.FAIL):
            success_flag = (round_result.result == OperationRoundResultEnum.SUCCESS)

        # 发送 after/after_success/after_fail 通知
        for desc in notify_list:
            if desc.when == NotifyTiming.BEFORE:
                continue

            # 根据时机过滤
            if desc.when == NotifyTiming.AFTER_SUCCESS and success_flag is not True:
                continue
            if desc.when == NotifyTiming.AFTER_FAIL and success_flag is not False:
                continue

            # 获取对应的图片
            img = image_ctx.get_image(desc.capture)

            # 发送通知
            send_node_notify(
                operation,
                current_node.cn,
                success_flag,
                desc,
                image=img,
                status=round_result.status
            )

        # 清理图片上下文
        if hasattr(operation, '_node_notify_image_ctx'):
            delattr(operation, '_node_notify_image_ctx')
