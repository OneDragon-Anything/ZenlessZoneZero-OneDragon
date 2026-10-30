from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.application.devtools.operation_debug import operation_debug_const


class OperationDebugConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id=operation_debug_const.APP_ID,
            instance_idx=instance_idx,
            group_id=group_id,
        )

    @property
    def operation_template(self) -> str:
        return self.get('operation_template', '安比-3A特殊攻击')

    @operation_template.setter
    def operation_template(self, new_value: str) -> None:
        self.update('operation_template', new_value)

    @property
    def repeat_enabled(self) -> bool:
        return self.get('repeat_enabled', True)

    @repeat_enabled.setter
    def repeat_enabled(self, new_value: bool) -> None:
        self.update('repeat_enabled', new_value)
