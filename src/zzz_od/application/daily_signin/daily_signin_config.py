from one_dragon.base.operation.application.application_config import ApplicationConfig


class DailySignInConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(self, 'daily_signin', instance_idx, group_id)

    @property
    def selected_sign(self) -> str:
        """选择签到的商店，默认为 hou_hou_bakery"""
        return self.get('selected_sign', 'hou_hou_bakery')

    @selected_sign.setter
    def selected_sign(self, value: str) -> None:
        self.update('selected_sign', value)
