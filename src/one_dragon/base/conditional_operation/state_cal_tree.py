from enum import Enum
from typing import Optional, Callable

from one_dragon.base.conditional_operation.state_recorder import StateRecorder
from one_dragon.utils.log_utils import log


class StateCalNodeType(Enum):

    OP: int = 0
    STATE: int = 1
    TRUE: int =2


class StateCalOpType(Enum):

    AND: int = 0
    OR: int = 1
    NOT: int = 2


class StateCalNode:

    def __init__(self, node_type: StateCalNodeType,
                 op_type: Optional[StateCalOpType] = None,
                 left_child: Optional = None,
                 right_child: Optional = None,
                 state_recorder: Optional[StateRecorder] = None,
                 state_time_range_min: float = None,
                 state_time_range_max: float = None,
                 state_value_range_min: int = None,
                 state_value_range_max: int = None,
                 ):
        """
        状态计算树的一个节点
        叶子节点为具体的状态记录器
        子节点为运算符
        :param node_type: 节点类型
        :param op_type: 运算符节点的情况下有值 代表具体运算符
        :param left_child: 运算符节点的情况下有值 代表左子节点
        :param right_child: 运算符节点的情况下有值 代表右子节点
        :param state_recorder: 状态记录器节点的情况下有值 代表状态记录器
        :param state_time_range_min: 状态记录器节点的情况下有值 代表状态生效的时间区间最小值
        :param state_time_range_max: 状态记录器节点的情况下有值 代表状态生效的时间区间最大值
        :param state_value_range_min: 状态记录器节点的情况下有值 代表状态生效的值区间最小值
        :param state_value_range_max: 状态记录器节点的情况下有值 代表状态生效的值区间最大值
        """
        self.node_type: StateCalNodeType = node_type

        self.op_type: StateCalOpType = op_type
        self.left_child: StateCalNode = left_child
        self.right_child: StateCalNode = right_child

        self.state_recorder: StateRecorder = state_recorder
        self.state_time_range_min: float = state_time_range_min
        self.state_time_range_max: float = state_time_range_max
        self.state_value_range_min: int = state_value_range_min
        self.state_value_range_max: int = state_value_range_max

    def in_time_range(self, now: float) -> bool:
        """
        根据当前时间 判断是否在状态的生效时间范围内
        :param now: 当前时间
        :return:
        """
        if self.node_type == StateCalNodeType.OP:
            if self.op_type == StateCalOpType.AND:
                return self.left_child.in_time_range(now) and self.right_child.in_time_range(now)
            elif self.op_type == StateCalOpType.OR:
                return self.left_child.in_time_range(now) or self.right_child.in_time_range(now)
            elif self.op_type == StateCalOpType.NOT:
                return not self.left_child.in_time_range(now)
        elif self.node_type == StateCalNodeType.STATE:
            diff = now - self.state_recorder.last_record_time
            # log.debug('状态 [ %s ] 距离上次 %.2f, 要求区间 [%.2f, %.2f]' % (
            #     self.state_recorder.state_name,
            #     999 if diff > 999 else diff,
            #     self.state_time_range_min,
            #     self.state_time_range_max
            # ))
            time_valid = self.state_time_range_min <= diff <= self.state_time_range_max
            value_valid = True
            if self.state_value_range_min is not None and self.state_value_range_max is not None:
                # log.debug('状态 [ %s ] 当前值 %s, 值要求区间 [%d, %d]' % (
                #     self.state_recorder.state_name,
                #     self.state_recorder.last_value,
                #     self.state_value_range_min,
                #     self.state_value_range_max
                # ))
                if self.state_recorder.last_value is None:
                    value_valid = False
                else:
                    value_valid = self.state_value_range_min <= self.state_recorder.last_value <= self.state_value_range_max

            return time_valid and value_valid
        elif self.node_type == StateCalNodeType.TRUE:
            return True

    def get_usage_states(self) -> set[str]:
        """
        获取使用的状态
        :return:
        """
        states: set[str] = set()
        if self.state_recorder is not None:
            states.add(self.state_recorder.state_name)
        if self.left_child is not None:
            states = states.union(self.left_child.get_usage_states())
        if self.right_child is not None:
            states = states.union(self.right_child.get_usage_states())
        return states

    def dispose(self) -> None:
        """
        销毁时 将子节点都销毁了
        :return:
        """
        if self.node_type == StateCalNodeType.OP:
            if self.op_type in [StateCalOpType.AND, StateCalOpType.OR]:
                self.left_child.dispose()
                self.right_child.dispose()
            elif self.op_type == StateCalOpType.NOT:
                return self.left_child.dispose()
        elif self.node_type == StateCalNodeType.STATE:
            self.state_recorder.dispose()


def construct_state_cal_tree(expr_str: str, state_getter: Callable[[str], StateRecorder], debugname: Optional[str] = None) -> StateCalNode:
    """
    根据表达式 构造出状态判断树
    :param expr_str: 表达式字符串
    :param state_getter: 状态记录器获取方法
    :param debugname: 调试名称
    :return: 构造成功时，返回状态判断树的根节点；构造失败时，返回原因
    """
    if len(expr_str) == 0:
        return StateCalNode(StateCalNodeType.TRUE)
    log.debug('构造状态判断树 ' + (debugname or expr_str))  # 修改这里，优先使用debugname

    op_stack = []  # 运算符的压栈
    op_idx_stack = []  # 运算符下标
    node_stack = []  # 状态判断节点的压栈

    expr_len = len(expr_str)
    idx = 0
    while idx < expr_len:
        next_idx = idx + 1  # 下一个处理的下标位置
        display_idx = idx + 1
        c = expr_str[idx]
        pop_op: bool = False  # 最后是否尝试弹出运算符
        if c == ' ':  # 忽略空格字符串
            pass
        elif c == '(':  # 左括号
            if len(node_stack) > 0 and len(op_stack) == 0:
                # 只有在表达式开头(前方还没有任何状态判断)的左括号，前方可以没有运算符
                raise ValueError('位置 %d 的左括号 前方缺少运算符' % display_idx)

            op_stack.append(c)  # 压入左括号
            op_idx_stack.append(c)
        elif c == ')':  # 右括号
            if len(op_stack) == 0 or op_stack[len(op_stack) - 1] != '(':  # 找不到对应左括号
                raise ValueError('位置 %d 的右括号 找不到对应的左括号' % display_idx)
            elif len(node_stack) == 0:  # 括号中间没有任何状态判断节点
                raise ValueError('位置 %d 的右括号 前方没有任何状态判断' % display_idx)

            op_stack.pop(-1)  # 弹出左括号
            op_idx_stack.pop(-1)
            pop_op = True  # 计算完括号之后 可以尝试继续弹出前面的运算符
        elif c == '[':   # 状态判断的开始
            right_idx = expr_str.find(']', idx + 1)  # 状态判断的结束
            if right_idx == -1:
                raise ValueError('位置 %d 的左中括号 找不到对应的右中括号' % display_idx)
            state_str = expr_str[idx + 1:right_idx]
            state_split_arr = state_str.split(',')

            if len(state_split_arr) < 3:
                state_name = state_split_arr[0].strip()
                time_min = float(0)
                time_max = float(1)
            else:
                try:
                    state_name = state_split_arr[0].strip()
                    time_min = float(state_split_arr[1].strip())
                    time_max = float(state_split_arr[2].strip())
                except Exception as e:
                    raise ValueError('位置 %d 的左中括号 后方状态无法解析 %s' % (display_idx, e))

            value_min: Optional[int] = None
            value_max: Optional[int] = None
            brace_left_idx = right_idx + 1
            if brace_left_idx < expr_len and expr_str[brace_left_idx] == '{':  # 有大括号
                brace_right_idx = expr_str.find('}', brace_left_idx + 1)
                if brace_right_idx == -1:
                    raise ValueError('位置 %d 的左大括号 找不到对应的大中括号' % (brace_left_idx + 1))
                value_range_str = expr_str[brace_left_idx + 1:brace_right_idx]
                value_split_arr = value_range_str.split(',')
                try:
                    value_min = int(value_split_arr[0])
                    if len(value_split_arr) > 1:
                        value_max = int(value_split_arr[1])
                    else:
                        value_max = value_min
                except Exception as e:
                    raise ValueError('位置 %d 的左大括号 后方状态无法解析 %s' % (brace_left_idx + 1, e))

                right_idx = brace_right_idx

            state_recorder: StateRecorder = state_getter(state_name)
            if state_recorder is None:
                raise ValueError('位置 %d 的左中括号 后方状态不合法 %s' % (display_idx, state_name))

            node = StateCalNode(
                node_type=StateCalNodeType.STATE,
                state_recorder=state_recorder,
                state_time_range_min=time_min,
                state_time_range_max=time_max,
                state_value_range_min=value_min,
                state_value_range_max=value_max,
            )
            node_stack.append(node)
            pop_op = True  # 有新的状态节点压入 可以尝试
            next_idx = right_idx + 1  # 从右括号下一个开始处理
        elif c in ['&', '|', '!']:
            op_stack.append(c)  # 运算符直接压入
            op_idx_stack.append(idx)
        else:
            raise ValueError('位置 %d 的出现非法字符 %s' % (display_idx, c))

        idx = next_idx

        while pop_op:  # 尝试弹出运算符
            if len(op_stack) == 0:
                break
            last_op = op_stack[-1]
            last_op_display_dix = op_idx_stack[-1]  # 在表达式中的位置

            if last_op == '!':
                if len(node_stack) == 0:
                    raise ValueError('位置 %d 的 ! 后方缺少状态' % last_op_display_dix)

                left_child = node_stack.pop(-1)
                op_node = StateCalNode(
                    node_type=StateCalNodeType.OP,
                    op_type=StateCalOpType.NOT,
                    left_child=left_child
                )
                op_stack.pop(-1)
                op_idx_stack.pop(-1)
                node_stack.append(op_node)
            elif last_op in ['&', '|']:
                if len(node_stack) == 0:
                    raise ValueError('位置 %d 的 %s 前方缺少状态' % (last_op_display_dix, last_op))
                elif len(node_stack) == 1:
                    raise ValueError('位置 %d 的 %s 后方缺少状态' % (last_op_display_dix, last_op))

                right_child = node_stack.pop(-1)
                left_child = node_stack.pop(-1)
                op_node = StateCalNode(
                    node_type=StateCalNodeType.OP,
                    op_type=StateCalOpType.AND if last_op == '&' else StateCalOpType.OR,
                    left_child=left_child,
                    right_child=right_child
                )
                op_stack.pop(-1)
                op_idx_stack.pop(-1)
                node_stack.append(op_node)
            else:  # 其他符号 应该只有左括号会命中这种情况
                break

    if len(node_stack) > 1:
        raise ValueError('有多段表达式 未使用运算符连接')
    else:
        return node_stack[0]


def __debug():
    expr = "( [闪避识别-黄光, 0, 1] | [闪避识别-红光, 0, 1] ) & ![按键-闪避, 0, 1]{0, 1}"
    ctx = None
    sr1 = StateRecorder('闪避识别-黄光')
    sr1.last_record_time = 1
    sr2 = StateRecorder('闪避识别-红光')
    sr2.last_record_time = 2
    sr3 = StateRecorder('按键-闪避')
    sr3.last_record_time = 1
    node = construct_state_cal_tree(expr, [sr1, sr2, sr3])
    assert node.in_time_range(2)  # True
    sr3.last_value = 1
    assert not node.in_time_range(2)  # False


if __name__ == '__main__':
    __debug()
