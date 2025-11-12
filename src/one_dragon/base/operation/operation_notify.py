from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING

from cv2.typing import MatLike

from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt

if TYPE_CHECKING:
    from one_dragon.base.operation.application_base import Application
    from one_dragon.base.operation.operation import Operation
    from one_dragon.base.operation.operation_node import OperationNode


class NotifyTiming(Enum):
    """通知触发时机枚举"""
    BEFORE = 'before'
    AFTER = 'after'
    AFTER_SUCCESS = 'after_success'
    AFTER_FAIL = 'after_fail'


def _get_app_info(operation: Operation) -> tuple[str | None, str | None]:
    """
    从 Operation 实例获取关联的应用 ID 和名称

    Args:
        operation: Operation 实例

    Returns:
        (app_id, app_name) 元组，如果无法获取则返回 (None, None)
    """
    # 如果本身就是 Application，直接返回其信息
    from one_dragon.base.operation.application_base import Application
    if isinstance(operation, Application):
        return getattr(operation, 'app_id', None), getattr(operation, 'op_name', None)

    # 否则从 run_context 获取当前运行的应用信息
    app_id = operation.ctx.run_context.current_app_id
    if app_id is None:
        return None, None

    # 尝试获取应用名称
    try:
        app_name = operation.ctx.run_context.get_application_name(app_id)
        return app_id, app_name
    except Exception:
        return app_id, None


def _should_notify(operation: Operation) -> bool:
    """
    检查是否应该发送通知

    Args:
        operation: Operation 实例

    Returns:
        bool: 是否应该发送通知
    """
    # 检查全局通知开关
    if not operation.ctx.notify_config.enable_notify:
        return False

    # 检查应用级别的通知开关
    app_id, _ = _get_app_info(operation)
    return operation.ctx.notify_config.is_app_notify_enabled(app_id)


def _build_app_message(app_name: str, status: str) -> str:
    """
    构建应用级别的通知消息

    Args:
        app_name: 应用名称
        status: 状态（成功/失败/开始）

    Returns:
        str: 格式化的消息
    """
    return f"{gt('任务「')}{app_name}{gt('」运行')}{status}"


def _build_node_message(
    app_name: str,
    node_name: str,
    phase: str,
    custom_message: str | None = None,
    status: str | None = None,
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
               f"{gt('」')}{phase}{status_text}")
    else:
        # 简化消息：只显示任务名和阶段
        msg = f"{gt('任务「')}{app_name}{gt('」')}{phase}"

    if custom_message:
        msg += '\n' + custom_message

    return msg


def send_application_notify(app: Application, status: bool | None) -> None:
    """向外部推送应用运行状态通知。

    Args:
        app: Application 实例
        status: True=成功, False=失败, None=开始
    """
    # 验证配置
    if not _should_notify(app):
        return

    # 检查全局的开始前通知开关
    if status is None and not app.ctx.notify_config.enable_before_notify:
            return

    # 确定状态和图片来源
    if status is True:
        status = gt('成功')
    elif status is False:
        status = gt('失败')
    else:  # status is None
        status = gt('开始')

    # 构建消息
    _, app_name = _get_app_info(app)
    app_name = gt(app_name)
    message = _build_app_message(app_name, status)

    # 异步推送
    app.ctx.push_service.push_async(
        title=app.ctx.notify_config.title,
        content=message,
    )


class NodeNotifyDesc:
    """操作节点通知描述。

    通过 @node_notify 装饰器使用，用于标注节点需要发送的通知。

    注意：装饰器只负责元数据标注，执行框架会在合适的生命周期钩子中读取
    func.operation_notify_annotation 并调用相应的通知函数。
    """

    def __init__(
            self,
            when: NotifyTiming,
            custom_message: str | None = None,
            send_image: bool = True,
            detail: bool = False,
    ):
        self.when: NotifyTiming = when
        self.custom_message: str | None = custom_message
        self.send_image: bool = send_image
        self.detail: bool = detail


def node_notify(
    when: NotifyTiming,
    custom_message: str | None = None,
    send_image: bool = True,
    detail: bool = False,
):
    """为操作节点函数附加通知元数据的装饰器。

    用法示例：
        @node_notify(when=NotifyTiming.AFTER)               # 节点结束后发送通知
        @node_notify(when=NotifyTiming.BEFORE)              # 上一节点完成后发送通知
        @node_notify(when=NotifyTiming.AFTER_SUCCESS)       # 仅成功后发送通知
        @node_notify(when=NotifyTiming.AFTER_FAIL)          # 仅失败后发送通知
        @node_notify(detail=True)                           # 显示节点名和返回状态
        @node_notify(custom_message='处理完成')             # 添加自定义消息
        @node_notify(send_image=False)                      # 不发送截图

    Args:
        when: 通知触发时机
            - BEFORE: 上一节点完成后发送（展示上一节点信息）
            - AFTER: 节点结束后发送（成功或失败都发送）
            - AFTER_SUCCESS: 仅节点成功后发送
            - AFTER_FAIL: 仅节点失败后发送
        custom_message: 自定义附加消息
        send_image: 是否发送截图
        detail: 是否显示详细信息（节点名和状态）

    自动行为：
        - 截图使用节点执行时的 last_screenshot
        - BEFORE 通知在上一节点的结束阶段发送
        - 其他通知在当前节点的结束阶段发送
        - 可多次装饰同一函数以实现多种时机通知
    """

    def decorator(func: Callable):
        if not hasattr(func, 'operation_notify_annotation'):
            func.operation_notify_annotation = []
        lst: list[NodeNotifyDesc] = func.operation_notify_annotation
        lst.append(NodeNotifyDesc(
            when=when,
            custom_message=custom_message,
            send_image=send_image,
            detail=detail,
        ))
        return func

    return decorator


def send_node_notify(
        operation: Operation,
        node_name: str,
        is_success: bool,
        desc: NodeNotifyDesc,
        image: MatLike | None = None,
        status: str | None = None,
):
    """
    发送节点级通知

    Args:
        operation: Operation 实例
        node_name: 节点名称
        is_success: 是否成功
        desc: 节点通知描述
        image: 截图（可选）
        status: 状态信息（可选）
    """
    # 获取应用名称
    _, app_name = _get_app_info(operation)
    if app_name is None:
        app_name = operation.op_name
    app_name = gt(app_name)

    # 获取阶段文本
    if is_success is True:
        phase = gt('成功')
    else:
        phase = gt('失败')

    # 构建消息
    message = _build_node_message(
        app_name=app_name,
        node_name=node_name,
        phase=phase,
        custom_message=desc.custom_message,
        status=status,
        detail=desc.detail
    )

    # 判断是否发送图片
    image = image if desc.send_image else None

    # 异步推送
    operation.ctx.push_service.push_async(
        title=operation.ctx.notify_config.title,
        content=message,
        image=image,
    )

def process_node_notifications(
    operation: Operation,
    round_result: OperationRoundResult,
    next_node: OperationNode | None = None
):
    """
    集中处理一个节点的所有通知

    Args:
        operation: Operation 实例
        round_result: OperationRoundResult 实例
        next_node: 下一个要执行的节点（用于处理 before 通知）
    """
    # 当前节点或方法不存在时直接返回
    current_node = operation.current_node.node
    if current_node is None or current_node.op_method is None:
        return

    if not _should_notify(operation):
        return

    notify_list: list[NodeNotifyDesc] = getattr(current_node.op_method, 'operation_notify_annotation', [])
    if not notify_list:
        return

    node_name = current_node.cn
    is_success = round_result.is_success
    image = operation.last_screenshot
    status = round_result.status

    # 发送当前节点的通知
    for desc in notify_list:
        # 根据时机过滤
        if desc.when == NotifyTiming.BEFORE:
            continue
        if desc.when == NotifyTiming.AFTER_SUCCESS and is_success is not True:
            continue
        if desc.when == NotifyTiming.AFTER_FAIL and is_success is not False:
            continue

        send_node_notify(
            operation,
            node_name,
            is_success,
            desc,
            image,
            status,
        )

    # 检查是否需要为下一节点发送通知
    if next_node is not None and next_node.op_method is not None:
        next_notify_list: list[NodeNotifyDesc] = getattr(
            next_node.op_method, 'operation_notify_annotation', []
        )

        for desc in next_notify_list:
            if desc.when == NotifyTiming.BEFORE:
                send_node_notify(
                    operation,
                    node_name,
                    is_success,
                    desc,
                    image,
                    status,
                )
