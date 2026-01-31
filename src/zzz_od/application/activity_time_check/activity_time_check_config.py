from enum import StrEnum

from one_dragon.base.operation.application.application_config import ApplicationConfig


class ActivityFilterType(StrEnum):
    """活动过滤类型"""
    NONE = 'none'  # 不过滤
    WHITELIST = 'whitelist'  # 白名单
    BLACKLIST = 'blacklist'  # 黑名单


class ActivityTimeCheckConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id='activity_time_check',
            instance_idx=instance_idx,
            group_id=group_id,
        )

    @property
    def filter_type(self) -> str:
        """过滤类型"""
        return self.get('filter_type', ActivityFilterType.NONE.value)

    @filter_type.setter
    def filter_type(self, new_value: str) -> None:
        self.update('filter_type', new_value)

    @property
    def filter_list(self) -> list[str]:
        """过滤列表（白名单或黑名单）"""
        return self.get('filter_list', [])

    @filter_list.setter
    def filter_list(self, new_value: list[str]) -> None:
        self.update('filter_list', new_value)

    def should_check_activity(self, activity_title: str) -> bool:
        """
        判断是否应该检查该活动
        :param activity_title: 活动标题
        :return: 是否应该检查
        """
        filter_type = self.filter_type
        filter_list = self.filter_list

        if filter_type == ActivityFilterType.NONE.value:
            return True
        elif filter_type == ActivityFilterType.WHITELIST.value:
            # 白名单模式：只检查在列表中的活动
            return any(item in activity_title for item in filter_list)
        elif filter_type == ActivityFilterType.BLACKLIST.value:
            # 黑名单模式：不检查在列表中的活动
            return not any(item in activity_title for item in filter_list)
        return True
