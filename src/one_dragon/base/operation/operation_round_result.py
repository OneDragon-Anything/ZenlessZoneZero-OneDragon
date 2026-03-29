from enum import Enum
from typing import Any


class OperationRoundResultEnum(Enum):
    RETRY = 0  # 重试
    SUCCESS = 1  # 成功
    WAIT = 2  # 等待 本轮不计入
    FAIL = -1  # 失败


class OperationRoundResult:

    def __init__(self, result: OperationRoundResultEnum, status: str | None = None, data: Any = None):
        """
        指令单轮执行的结果
        :param result: 结果
        :param status: 附带状态
        """
        self.result: OperationRoundResultEnum = result
        """单轮执行结果 - 框架固定"""
        self.status: str | None = status
        """结果状态 - 每个指令独特"""
        self.data: Any = data
        """返回数据"""

    @property
    def is_success(self) -> bool:
        return self.result == OperationRoundResultEnum.SUCCESS

    @property
    def is_fail(self) -> bool:
        return self.result == OperationRoundResultEnum.FAIL

    @property
    def status_display(self) -> str:
        if self.result == OperationRoundResultEnum.SUCCESS:
            return '成功'
        elif self.result == OperationRoundResultEnum.RETRY:
            return '重试'
        elif self.result == OperationRoundResultEnum.WAIT:
            return '等待'
        elif self.result == OperationRoundResultEnum.FAIL:
            return '失败'
        else:
            return '未知'
