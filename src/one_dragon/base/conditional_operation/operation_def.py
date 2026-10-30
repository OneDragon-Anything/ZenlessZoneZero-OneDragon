from typing import Any


class OperationDef:

    def __init__(
        self,
        data: dict[str, Any]
    ):
        self.original_data: dict[str, Any] = data
        self.op_name: str | None = data.get("op_name")  # 指令名称

        self.data: list[str] | None = data.get("data")  # TODO 旧字段 后续需要删除
        self.operation_template: str | None = data.get("operation_template")  # 引用另外一个指令模板

        # 通用
        self.pre_delay: float = data.get("pre_delay", 0)  # 执行指令前的等待时间
        self.post_delay: float = data.get("post_delay", 0)  # 执行指令完成后的等待时间

        # 按键特有的属性
        self.btn_way: str | None = data.get("way")  # 按键方式
        self.btn_press: float | None = data.get("press")  # 按键持续时间(秒)
        self.btn_repeat_times: int = data.get("repeat", 1)  # 按键重复次数

        # 等待秒数
        self.wait_seconds: float = data.get("seconds", 0)  # 等待秒数

        # 状态
        self.state_name: str | None = data.get("state")  # 状态名称 制定作用的状态
        self.state_name_list: list[str] | None = data.get("state_list")  # 状态名称列表 指令作用的状态列表
        self.state_seconds: float = data.get("seconds", 0)  # 设置状态触发时间
        self.state_seconds_add: float = data.get("seconds_add", 0)  # 按这个偏移量(秒) 更新状态的触发时间
        self.state_value: int | None = data.get("value")  # 设置的状态值
        self.state_value_add: int | None = data.get("add")  # 设置的状态值偏移量 state_value存在时不生效

        # TODO 调试代码 后续删除
        for k in data.keys():
            if k not in [
                "op_name", "data", "operation_template",
                "pre_delay", "post_delay",
                "way", "press", "repeat",
                "seconds",
                "state", "state_list", "seconds", "seconds_add", "value", "add",
                "agent_name"
            ]:
                raise ValueError(f"未知字段 {k}")
