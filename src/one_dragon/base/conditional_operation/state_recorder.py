from typing import Optional, List


class StateRecord:

    def __init__(self, state_name: str,
                 trigger_time: float = 0,
                 value: Optional[int] = None, 
                 value_to_add: Optional[int] = None,
                 trigger_time_add: Optional[float] = None,
                 is_clear: bool = False,):
        """
        单次的状态记录
        """
        self.state_name: str = state_name
        self.is_clear: bool = is_clear  # 是否清除状态
        self.trigger_time: float = trigger_time
        self.trigger_time_add: float = trigger_time_add  # 时间修改
        self.value: int = value
        self.value_add: int = value_to_add

    def __str__(self):
        return f"StateRecord(state_name='{self.state_name}', trigger_time={self.trigger_time:.2f}, value={self.value}, value_add={self.value_add})"


class StateRecorder:

    def __init__(self, state_name: str, mutex_list: Optional[List[str]] = None):
        self.state_name: str = state_name
        self.mutex_list: List[str] = mutex_list  # 互斥的状态 这种状态出现的时候 就会将自身状态清空

        self.last_record_time: float = -1  # 上次记录这个状态的时间 -1代表还没有触发过 0代表被清除
        self.last_value: Optional[int] = None  # 上一次记录的值

    def update_state_record(self, record: StateRecord) -> None:
        """
        状态事件被触发时 记录触发的时间
        :param record:
        :return:
        """
        #不需要增减则照常处理
        if record.trigger_time_add is None or record.trigger_time_add == 0:
            self.last_record_time = record.trigger_time
        else:
            if self.last_record_time != -1:  #如果是不存在的状态则不做任何处理
                self.last_record_time -= record.trigger_time_add

        if self.last_value is None:
            self.last_value = 0

        if record.value is not None:
            self.last_value = record.value

        if record.value_add is not None:
            self.last_value += record.value_add

    def clear_state_record(self) -> None:
        """
        互斥事件发生时 清空
        """
        if self.last_record_time == -1:
            # 原来没有出现过的话 就不重置
            return
        self.last_record_time = 0
        self.last_value = None

    def dispose(self) -> None:
        """
        销毁时 解绑事件
        :return:
        """
        self.state_name = None
        self.mutex_list = None
        self.last_value = None
        self.last_value = None
