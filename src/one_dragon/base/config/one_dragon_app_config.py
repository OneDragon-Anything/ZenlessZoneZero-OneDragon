from typing import List, Optional

from one_dragon.base.config.yaml_config import YamlConfig


class OneDragonAppConfig(YamlConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        YamlConfig.__init__(self, 'one_dragon_app', instance_idx=instance_idx, sample=False)
        self._temp_app_run_list: Optional[List[str]] = None

    def set_temp_app_run_list(self, app_run_list: Optional[List[str]]):
        """设置临时应用运行列表"""
        self._temp_app_run_list = app_run_list

    def clear_temp_app_run_list(self):
        """清除临时应用运行列表"""
        self._temp_app_run_list = None

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

    def move_down_app(self, app_id: str) -> None:
        """
        将一个app的执行顺序往后调一位
        :param app_id:
        :return:
        """
        old_app_orders = self.app_order
        idx = -1

        for i in range(len(old_app_orders)):
            if old_app_orders[i] == app_id:
                idx = i
                break

        if idx < 0 or idx >= len(old_app_orders) - 1:  # 无法交换
            return

        temp = old_app_orders[idx + 1]
        old_app_orders[idx + 1] = old_app_orders[idx]
        old_app_orders[idx] = temp

        self.app_order = old_app_orders

    def move_app_to_position(self, app_id: str, target_position: int) -> None:
        """
        将应用移动到指定位置（支持拖拽功能）
        :param app_id: 应用ID
        :param target_position: 目标位置索引
        :return:
        """
        old_app_orders = self.app_order.copy()
        current_idx = -1

        # 找到当前应用的位置
        for i in range(len(old_app_orders)):
            if old_app_orders[i] == app_id:
                current_idx = i
                break

        if current_idx == -1:  # 未找到应用
            return

        # 限制目标位置在有效范围内
        target_position = max(0, min(target_position, len(old_app_orders) - 1))

        if current_idx == target_position:  # 位置没有变化
            return

        # 移除当前位置的应用
        app_to_move = old_app_orders.pop(current_idx)
        
        # 插入到目标位置
        old_app_orders.insert(target_position, app_to_move)

        self.app_order = old_app_orders

    @property
    def app_run_list(self) -> List[str]:
        """
        应用运行列表
        如果设置了临时应用列表，则使用临时配置
        :return:
        """
        if self._temp_app_run_list is not None:
            return self._temp_app_run_list
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