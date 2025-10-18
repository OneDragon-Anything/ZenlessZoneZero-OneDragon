from __future__ import annotations

from typing import Optional, Callable, List, TYPE_CHECKING
from io import BytesIO

from concurrent.futures import ThreadPoolExecutor
from one_dragon.base.notify.push import Push
from one_dragon.utils.i18_utils import gt

__all__ = [
    'notify_application',
    'NodeNotifyDesc',
    'node_notify',
    'send_node_notify',
    'process_node_notifications'
]


if TYPE_CHECKING:  # 仅用于类型检查，避免运行时循环依赖
    from one_dragon.base.operation.application_base import Application


_node_notify_executor = ThreadPoolExecutor(thread_name_prefix='od_node_notify', max_workers=1)


def notify_application(app: 'Application', is_success: Optional[bool] = True) -> None:
    """向外部推送应用运行状态通知。

    参数含义与原 `Application.notify` 一致。该函数被抽离出来便于复用与单元测试，
    并避免在运行期产生循环依赖（此处仅向下依赖 Push 与 i18n）。
    """
    # 延迟导入以避免循环引用：Application 位于 operation.application_base 中
    if not hasattr(app.ctx, 'notify_config'):
        return
    notify_cfg = app.ctx.notify_config
    if not getattr(notify_cfg, 'enable_notify', False):
        return
    if not getattr(notify_cfg, 'enable_before_notify', False) and is_success is None:
        return

    app_id = getattr(app, 'app_id', None)
    app_name = getattr(app, 'op_name', None)

    if not getattr(notify_cfg, app_id, False):
        return

    if is_success is True:
        status = gt('成功')
        image_source: Optional[BytesIO] = app.notify_screenshot  # 运行成功时使用预先截图
    elif is_success is False:
        status = gt('失败')
        # 失败时即时截图
        image_source = app.save_screenshot_bytes()
    else:  # is_success is None
        status = gt('开始')
        image_source = None

    send_image = getattr(app.ctx.push_config, 'send_image', False)
    image = image_source if send_image else None

    message = f"{gt('任务「')}{app_name}{gt('」运行')}{status}\n"

    pusher = Push(app.ctx)
    _node_notify_executor.submit(pusher.send, message, image)


class NodeNotifyDesc:
    """操作节点通知描述。

    用法：

    @node_notify()                       # 节点结束后（成功或失败）发送通知
    def some_node(...): ...

    @node_notify(when='before')          # 节点开始前发送“开始”通知
    @node_notify(when='after_success')   # 仅成功后发送
    @node_notify(when='after_fail')      # 仅失败后发送
    def another_node(...): ...

    可在同一函数上多次使用以实现多种时机通知。
    目前装饰器只负责元数据标注，执行框架应在合适的生命周期钩子中读取
    func.operation_notify_annotation 并调用 notify_application。
    """

    WHEN_BEFORE = 'before'
    WHEN_AFTER = 'after'
    WHEN_AFTER_SUCCESS = 'after_success'
    WHEN_AFTER_FAIL = 'after_fail'
    VALID_WHEN = {WHEN_BEFORE, WHEN_AFTER, WHEN_AFTER_SUCCESS, WHEN_AFTER_FAIL}

    CAPTURE_NONE = 'none'
    CAPTURE_BEFORE = 'before'
    CAPTURE_AFTER = 'after'
    VALID_CAPTURE = {CAPTURE_NONE, CAPTURE_BEFORE, CAPTURE_AFTER}

    def __init__(
            self,
            when: str = 'after',
            custom_message: Optional[str] = None,
            send_image: Optional[bool] = None,
            capture: str = 'none',
            finished: bool = False,
            # set_app_image 已废弃，不再保留截图
    ):
        if when not in self.VALID_WHEN:
            raise ValueError(f"when 必须是 {self.VALID_WHEN} 之一, 当前: {when}")
        if capture not in self.VALID_CAPTURE:
            raise ValueError(f"capture 必须是 {self.VALID_CAPTURE} 之一, 当前: {capture}")
        self.when: str = when
        self.custom_message: Optional[str] = custom_message
        self.send_image: Optional[bool] = send_image  # None 表示沿用全局配置
        self.capture: str = capture
        self.finished: bool = finished
    # self.set_app_image 已废弃


def node_notify(
    when: str = 'after',
    custom_message: Optional[str] = None,
    send_image: Optional[bool] = None,
    capture: str = 'none',
    finished: bool = False,
    # set_app_image: 已废弃
):
    """为操作节点函数附加通知元数据的装饰器（仿照 operation_edge.node_from 实现）。

    参数:
    when: 通知触发时机，可选 'before' | 'after' | 'after_success' | 'after_fail'。
    custom_message: 自定义附加消息（可选，将在框架处理时拼接）。
    send_image: 是否强制发送/不发送图片；None 表示使用全局策略。
    """

    def decorator(func: Callable):
        if not hasattr(func, 'operation_notify_annotation'):
            setattr(func, 'operation_notify_annotation', [])
        lst: List[NodeNotifyDesc] = getattr(func, 'operation_notify_annotation')
        lst.append(NodeNotifyDesc(
            when=when,
            custom_message=custom_message,
            send_image=send_image,
            capture=capture,
            finished=finished,
            # set_app_image 已移除
        ))
        return func

    return decorator


def send_node_notify(
        app: 'Application',
        node_name: str,
        success: Optional[bool],
        desc: NodeNotifyDesc,
        image: Optional[BytesIO] = None,
        status: Optional[str] = None,
):
    """发送节点级通知。"""
    if not hasattr(app.ctx, 'notify_config'):
        return
    notify_cfg = app.ctx.notify_config
    if not getattr(notify_cfg, 'enable_notify', False):
        return
    if not getattr(notify_cfg, 'enable_before_notify', False) and desc.when == NodeNotifyDesc.WHEN_BEFORE:
        return

    # 节点级别目前沿用应用配置（是否启用具体 app_id）
    if not getattr(notify_cfg, getattr(app, 'app_id', ''), False):
        return

    # 判定是否需要发送（after_success / after_fail 需要匹配）
    if desc.when == NodeNotifyDesc.WHEN_AFTER_SUCCESS and success is not True:
        return
    if desc.when == NodeNotifyDesc.WHEN_AFTER_FAIL and success is not False:
        return

    phase = ''
    if desc.when == NodeNotifyDesc.WHEN_BEFORE:
        phase = gt('开始')
    elif desc.when in (NodeNotifyDesc.WHEN_AFTER, NodeNotifyDesc.WHEN_AFTER_SUCCESS, NodeNotifyDesc.WHEN_AFTER_FAIL):
        if success is True:
            phase = gt('成功')
        elif success is False:
            phase = gt('失败')
        else:
            phase = gt('结束')

    finish_text = gt('，已完成') if desc.finished and success is True else ''
    status_text = '' if status is None else f" [{status}]"
    msg = f"{gt('任务「')}{getattr(app, 'op_name', '')}{gt('」节点「')}{node_name}{gt('」')}{phase}{finish_text}{status_text}\n"
    if desc.custom_message:
        msg += desc.custom_message + '\n'

    # 图片策略
    send_image_global = getattr(app.ctx.push_config, 'send_image', False)
    should_send_image = desc.send_image if desc.send_image is not None else send_image_global
    img = image if should_send_image else None

    pusher = Push(app.ctx)
    _node_notify_executor.submit(pusher.send, msg, img)


def process_node_notifications(op, phase: str, round_result=None):
    """集中处理一个节点的所有通知。

    Args:
        op: Operation 或其子类（含 ctx / save_screenshot_bytes 等方法）
        phase: 'before' 或 'after'
        round_result: OperationRoundResult 或 None (before 阶段)
    """
    # 当前节点或方法不存在时直接返回
    current_node = getattr(op, '_current_node', None)
    if current_node is None or current_node.op_method is None:
        return
    notify_list: list[NodeNotifyDesc] = getattr(current_node.op_method, 'operation_notify_annotation', [])
    if not notify_list:
        return

    # 预处理：before 阶段捕获需要的 BEFORE 图；after 阶段读取之前的并视需要捕获 AFTER 图
    if phase == 'before':
        if any(d.capture == NodeNotifyDesc.CAPTURE_BEFORE for d in notify_list):
            setattr(op, '_node_notify_before_image', op.save_screenshot_bytes())
        before_image = getattr(op, '_node_notify_before_image', None)
        for desc in notify_list:
            if desc.when == NodeNotifyDesc.WHEN_BEFORE:
                img = before_image if desc.capture == NodeNotifyDesc.CAPTURE_BEFORE else None
                send_node_notify(op, current_node.cn, None, desc, image=img)
    elif phase == 'after':
        # round_result 为空不处理
        if round_result is None:
            return
        before_image = getattr(op, '_node_notify_before_image', None)
        after_image = None
        if any(d.capture == NodeNotifyDesc.CAPTURE_AFTER for d in notify_list):
            after_image = op.save_screenshot_bytes()
        # 发送 after/after_success/after_fail
        for desc in notify_list:
            if desc.when != NodeNotifyDesc.WHEN_BEFORE:
                # success 判定：只有 SUCCESS / FAIL 阶段才有 True/False，其余 None
                success_flag = None
                from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
                if round_result.result in (OperationRoundResultEnum.SUCCESS, OperationRoundResultEnum.FAIL):
                    success_flag = (round_result.result == OperationRoundResultEnum.SUCCESS)
                if desc.when == NodeNotifyDesc.WHEN_AFTER_SUCCESS and success_flag is not True:
                    continue
                if desc.when == NodeNotifyDesc.WHEN_AFTER_FAIL and success_flag is not False:
                    continue
                img = None
                if desc.capture == NodeNotifyDesc.CAPTURE_AFTER:
                    img = after_image
                elif desc.capture == NodeNotifyDesc.CAPTURE_BEFORE:
                    img = before_image
                send_node_notify(op, current_node.cn, success_flag, desc, image=img, status=round_result.status)
        # 清理缓存的 before 图片
        if hasattr(op, '_node_notify_before_image'):
            delattr(op, '_node_notify_before_image')
