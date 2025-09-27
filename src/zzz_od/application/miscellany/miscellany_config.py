from typing import List, Optional

from one_dragon.base.config.user_config import UserConfig


class MiscellanyConfig(UserConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        UserConfig.__init__(self, 'miscellany', instance_idx=instance_idx)

    @property
    def app_order(self) -> List[str]:
        """
        运行顺序
        :return:
        """
        return self.get("app_order", [])

    @app_order.setter
    def app_order(self, new_list: List[str]):
        self.update('app_order', new_list)

    def move_up_app(self, app_id: str) -> None:
        """
        将一个app的执行顺序往前调一位
        :param app_id:
        :return:
        """
        old_app_orders = self.app_order
        idx = -1

        for i in range(len(old_app_orders)):
            if old_app_orders[i] == app_id:
                idx = i
                break

        if idx <= 0:  # 无法交换
            return

        temp = old_app_orders[idx - 1]
        old_app_orders[idx - 1] = old_app_orders[idx]
        old_app_orders[idx] = temp

        self.app_order = old_app_orders

    @property
    def app_run_list(self) -> List[str]:
        """
        运行顺序
        :return:
        """
        return self.get("app_run_list", [])

    @app_run_list.setter
    def app_run_list(self, new_list: List[str]):
        self.update('app_run_list', new_list)

    def set_app_run(self, app_id: str, to_run: bool) -> None:
        app_run_list = self.app_run_list
        if to_run and app_id not in app_run_list:
            app_run_list.append(app_id)
        elif not to_run and app_id in app_run_list:
            app_run_list.remove(app_id)
        self.app_run_list = app_run_list
