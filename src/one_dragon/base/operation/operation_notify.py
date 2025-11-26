from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING

from one_dragon.base.config.notify_config import NotifyLevel
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt

if TYPE_CHECKING:
    from one_dragon.base.operation.application_base import Application
    from one_dragon.base.operation.operation import Operation
    from one_dragon.base.operation.operation_node import OperationNode


class NotifyTiming(Enum):
    """通知触发时机枚举"""
    PREVIOUS_DONE = 'previous_done'
    CURRENT_DONE = 'current_done'
    CURRENT_SUCCESS = 'current_success'
    CURRENT_FAIL = 'current_fail'


def _get_app_info(operation: Operation) -> tuple[str | None, str | None]:
    """
    从 Operation 实例获取关联的应用 ID 和名称

    Args:
        operation: Operation 实例

    Returns:
        (app_id, app_name) 元组，如果无法获取则返回 (None, None)
    """
    # 从 run_context 获取当前运行的应用信息
    app_id = operation.ctx.run_context.current_app_id
    if app_id is None:
        return None, None

    # 尝试获取应用名称
    try:
        app_name = operation.ctx.run_context.get_application_name(app_id)
        return app_id, app_name
    except Exception:
        return app_id, None


def _get_notify_level(operation: Operation) -> int:
    """
    获取通知等级

    Args:
        operation: Operation 实例

    Returns:
        int: 通知等级
    """
    # 检查全局通知开关
    if not operation.ctx.notify_config.enable_notify:
        return NotifyLevel.OFF

    # 检查应用级别的通知开关
    app_id, _ = _get_app_info(operation)
    return operation.ctx.notify_config.get_app_notify_level(app_id)


def send_application_notify(app: Application, status: bool | None) -> None:
    """向外部推送应用运行状态通知。

    Args:
        app: Application 实例
        status: True=成功, False=失败, None=开始
    """
    # 验证配置
    if _get_notify_level(app) < NotifyLevel.APP:
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
    message = f"{gt('任务')}「{app_name}」{gt('运行')}{status}"

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
        @node_notify(when=NotifyTiming.CURRENT_DONE)        # 节点完成后发送通知
        @node_notify(detail=True)                           # 显示节点名和返回状态
        @node_notify(custom_message='处理完成')             # 添加自定义消息
        @node_notify(send_image=False)                      # 不发送截图

    Args:
        when: 通知触发时机
            - PREVIOUS_DONE: 上一节点完成后发送（显示上一节点信息）
            - CURRENT_DONE: 当前节点完成后发送（无论成功失败）
            - CURRENT_SUCCESS: 仅当前节点成功后发送
            - CURRENT_FAIL: 仅当前节点失败后发送
        custom_message: 自定义附加消息
        send_image: 是否发送截图
        detail: 是否显示详细信息（节点名和状态）

    自动行为：
        - 截图使用节点执行时的 last_screenshot
        - PREVIOUS_DONE 通知在上一节点的结束阶段发送
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
    round_result: OperationRoundResult,
    current_node: OperationNode | None = None,
    next_node: OperationNode | None = None
):
    """
    发送节点级通知

    Args:
        operation: Operation 实例
        round_result: OperationRoundResult 实例
        current_node: 当前正在执行的节点
        next_node: 下一个要执行的节点
    """
    if _get_notify_level(operation) < NotifyLevel.ALL or current_node is None:
        return

    # 初始化通知列表
    current_notify_list: list[NodeNotifyDesc] = []
    next_notify_list: list[NodeNotifyDesc] = []

    # 检查当前节点通知列表
    if current_node is not None and current_node.op_method is not None:
        current_notify_list = getattr(current_node.op_method, 'operation_notify_annotation', [])

    # 检查下一节点通知列表
    if next_node is not None and next_node.op_method is not None:
        next_notify_list = getattr(next_node.op_method, 'operation_notify_annotation', [])

    # 合并所有需要处理的通知
    all_notifications: list[NodeNotifyDesc] = []
    is_success = round_result.is_success

    # 收集当前节点的非 PREVIOUS_DONE 通知
    for desc in current_notify_list:
        if desc.when == NotifyTiming.PREVIOUS_DONE:
            continue
        if desc.when == NotifyTiming.CURRENT_SUCCESS and is_success is not True:
            continue
        if desc.when == NotifyTiming.CURRENT_FAIL and is_success is not False:
            continue
        all_notifications.append(desc)

    # 收集下一节点的 PREVIOUS_DONE 通知
    for desc in next_notify_list:
        if desc.when == NotifyTiming.PREVIOUS_DONE:
            all_notifications.append(desc)

    if not all_notifications:
        return

    detail = False
    send_image = False
    custom_message = ''

    for desc in all_notifications:
        if desc.detail:
            detail = True

        if desc.send_image:
            send_image = True

        if desc.custom_message:
            custom_message += f'\n{desc.custom_message}'

    # 构建消息内容
    _, app_name = _get_app_info(operation)
    if app_name is None:
        app_name = operation.op_name

    app_name = gt(app_name)
    node_name = gt(current_node.cn)

    result = gt('成功') if is_success else gt('失败')

    message = (f"{gt('任务')}「{app_name}」"
               f"{gt('节点')}「{node_name}」\n"
               f"{gt('运行')}「{result}」")

    if detail:
        status = round_result.status
        message += f"{gt('状态')}「{status}」" if status else ''

    if custom_message:
        message += custom_message

    # 异步推送
    operation.ctx.push_service.push_async(
        title=operation.ctx.notify_config.title,
        content=message,
        image=operation.last_screenshot if send_image else None,
    )
