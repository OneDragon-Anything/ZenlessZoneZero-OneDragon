from typing import List, Callable, Set

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_def import OperationDef
from one_dragon.base.conditional_operation.operation_template import OperationTemplate
from one_dragon.base.conditional_operation.scene_handler import SceneHandler
from one_dragon.base.conditional_operation.state_cal_tree import construct_state_cal_tree
from one_dragon.base.conditional_operation.state_handler import StateHandler
from one_dragon.base.conditional_operation.state_handler_template import StateHandlerTemplate
from one_dragon.base.conditional_operation.state_recorder import StateRecorder
from one_dragon.utils.log_utils import log  # 确保已经导入了log


def construct_scene_handler(
        scene_data: dict,
        state_getter: Callable[[str], StateRecorder],
        op_getter: Callable[[OperationDef], AtomicOp],
        scene_handler_getter: Callable[[str], StateHandlerTemplate],
        operation_template_getter: Callable[[str], OperationTemplate],
):
    interval_seconds = scene_data.get('interval', 0.5)

    state_handlers = _get_state_handlers(
        scene_data.get('handlers', []),
        state_getter, op_getter, scene_handler_getter, operation_template_getter,
        set()
    )

    priority = scene_data.get('priority', None)

    return SceneHandler(interval_seconds, state_handlers, priority)


def _get_state_handlers_by_template(
        template_name: str,
        state_getter: Callable[[str], StateRecorder],
        op_getter: Callable[[OperationDef], AtomicOp],
        scene_handler_getter: Callable[[str], StateHandlerTemplate],
        operation_template_getter: Callable[[str], OperationTemplate],
        usage_states_handler_templates: Set[str]
) -> List[StateHandler]:
    """
    根据模板加载
    :return:
    """
    if template_name in usage_states_handler_templates:
        raise ValueError('循环引入状态处理器模板 ' + template_name)
    if template_name is None or len(template_name) == 0:
        raise ValueError('状态处理器模板名称为空 handler_template')
    template: StateHandlerTemplate = scene_handler_getter(template_name)
    if template is None:
        raise ValueError('找不到状态处理器模板 ' + template_name)

    usage_states_handler_templates.add(template_name)
    state_handlers = _get_state_handlers(
        template.get('handlers', []),
        state_getter, op_getter, scene_handler_getter, operation_template_getter,
        usage_states_handler_templates
    )
    usage_states_handler_templates.remove(template_name)

    return state_handlers


def _get_state_handlers(
        handler_data_list: List[dict],
        state_getter: Callable[[str], StateRecorder],
        op_getter: Callable[[OperationDef], AtomicOp],
        scene_handler_getter: Callable[[str], StateHandlerTemplate],
        operation_template_getter: Callable[[str], OperationTemplate],
        usage_states_handler_templates: Set[str]
) -> List[StateHandler]:
    state_handlers = []

    for handler_data_item in handler_data_list:
        if 'state_template' in handler_data_item:
            template_state_handlers = _get_state_handlers_by_template(
                handler_data_item.get('state_template', ''),
                state_getter, op_getter, scene_handler_getter, operation_template_getter,
                usage_states_handler_templates)
            for i in template_state_handlers:
                state_handlers.append(i)
        else:
            state_handlers.append(construct_state_handler(
                handler_data_item, state_getter,
                op_getter, scene_handler_getter, operation_template_getter,
                usage_states_handler_templates
            ))

    return state_handlers


def construct_state_handler(
        state_data: dict,
        state_getter: Callable[[str], StateRecorder],
        op_getter: Callable[[OperationDef], AtomicOp],
        scene_handler_getter: Callable[[str], StateHandlerTemplate],
        operation_template_getter: Callable[[str], OperationTemplate],
        usage_scene_templates: Set[str],
) -> StateHandler:
    """
    构造一个场景处理器
    包含状态判断 + 对应指令
    :param state_data: 场景配置数据
    :param state_getter: 状态记录获取器
    :param op_getter: 指令获取器
    :param operation_template_getter: 指令模板获取器
    :return:
    """
    if 'states' not in state_data:
        raise ValueError('未有状态表达式字段 %s', state_data)
    states_expr = state_data.get('states', '')
    debug_name = state_data.get('debug_name', None)  # 从配置中获取debug_name
    if debug_name is not None:
        debug_name = f'[#{debug_name}]'  # 添加方括号

    state_cal_tree = construct_state_cal_tree(states_expr, state_getter, debug_name)
    interrupt_expr = state_data.get('interrupt_states', None)
    interrupt_cal_tree = None
    if interrupt_expr is not None and isinstance(interrupt_expr, str) and len(interrupt_expr) > 0:
        interrupt_cal_tree = construct_state_cal_tree(interrupt_expr, state_getter)
    # sub_states 是旧的 后续可以删除
    if 'sub_states' in state_data or 'sub_handlers' in state_data:
        if 'sub_states' in state_data:
            sub_state_data_list = state_data.get('sub_states', [])
        elif 'sub_handlers' in state_data:
            sub_state_data_list = state_data.get('sub_handlers', [])
        else:
            sub_state_data_list = []
        if len(sub_state_data_list) == 0:
            raise ValueError('状态( %s )下子状态为空', states_expr)
        sub_handler_list: List[StateHandler] = _get_state_handlers(
            sub_state_data_list,
            state_getter,
            op_getter,
            scene_handler_getter,
            operation_template_getter,
            usage_scene_templates
        )
        return StateHandler(states_expr, state_cal_tree,
                          sub_handlers=sub_handler_list,
                          interrupt_cal_tree=interrupt_cal_tree,
                          debug_name=debug_name)  # 新增：传入debug_name
    else:
        ops = get_ops_from_data(
            state_data.get('operations', []),
            op_getter, operation_template_getter,
            set())
        if len(ops) == 0:
            raise ValueError('状态( %s )下指令为空', states_expr)
        return StateHandler(states_expr, state_cal_tree,
                          operations=ops,
                          interrupt_cal_tree=interrupt_cal_tree,
                          debug_name=debug_name)  # 新增：传入debug_name


def get_ops_by_template(
        template_name: str,
        op_getter: Callable[[OperationDef], AtomicOp],
        operation_template_getter: Callable[[str], OperationTemplate],
        usage_operation_templates: Set[str]
) -> List[AtomicOp]:
    if template_name in usage_operation_templates:
        raise ValueError('循环引入指令模板 ' + template_name)
    if template_name is None or len(template_name) == 0:
        raise ValueError('指令模板名称为空 handler_template')
    template: OperationTemplate = operation_template_getter(template_name)
    if template is None:
        raise ValueError('找不到指令模板 ' + template_name)

    usage_operation_templates.add(template_name)
    ops = get_ops_from_data(template.get('operations', []),
                             op_getter, operation_template_getter,
                             usage_operation_templates)

    usage_operation_templates.remove(template_name)

    return ops


def get_ops_from_data(
        operation_data_list: List[dict],
        op_getter: Callable[[OperationDef], AtomicOp],
        operation_template_getter: Callable[[str], OperationTemplate],
        usage_templates: Set[str]
):
    ops = []
    for operation_data_item in operation_data_list:
        op_def = OperationDef(**operation_data_item)
        if op_def.operation_template is not None:
            template_ops = get_ops_by_template(
                op_def.operation_template,
                op_getter, operation_template_getter,
                usage_templates
            )
            for op in template_ops:
                ops.append(op)
        else:
            op = op_getter(op_def)
            ops.append(op)
    return ops
