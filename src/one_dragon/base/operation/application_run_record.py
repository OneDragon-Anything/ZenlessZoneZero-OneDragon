import time
from datetime import datetime
from enum import Enum
from typing import Optional

from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.utils import os_utils


class AppRunRecordPeriod(Enum):

    DAILY = 1
    WEEKLY = 2


class AppRunRecord(YamlConfig):

    STATUS_WAIT = 0
    STATUS_SUCCESS = 1
    STATUS_FAIL = 2
    STATUS_RUNNING = 3

    def __init__(
            self, app_id: str,
            instance_idx: Optional[int] = None,
            game_refresh_hour_offset: int = 0,
            record_period: AppRunRecordPeriod = AppRunRecordPeriod.DAILY
    ):
        self.app_id: str = app_id
        self.dt: str = ''
        self.run_time: str = ''
        self.run_time_float: float = 0
        self.run_status: int = AppRunRecord.STATUS_WAIT  # 0=未运行 1=成功 2=失败 3=运行中
        self.game_refresh_hour_offset: int = game_refresh_hour_offset  # 游戏内每天刷新的偏移小时数 以凌晨12点为界限
        self.record_period: AppRunRecordPeriod = record_period
        super().__init__(app_id, instance_idx=instance_idx, sub_dir=['app_run_record'], sample=False)

        self._init_after_read_file()

    def _init_after_read_file(self):
        self.dt = self.get('dt', self.get_current_dt())
        self.run_time = self.get('run_time', '-')
        self.run_time_float = self.get('run_time_float', 0)
        self.run_status = self.get('run_status', AppRunRecord.STATUS_WAIT)

    def check_and_update_status(self):
        """
        检查并更新状态 各个app按需实现
        :return:
        """
        if self._should_reset_by_dt():
            self.reset_record()

    def update_status(self, new_status: int, only_status: bool = False):
        """
        更新状态
        :param new_status:
        :param only_status: 是否只更新状态
        :return:
        """
        self.run_status = new_status
        self.update('run_status', self.run_status, False)
        if not only_status:
            self.dt = self.get_current_dt()
            self.run_time = self.app_record_now_time_str()
            self.run_time_float = time.time()
            self.update('dt', self.dt, False)
            self.update('run_time', self.run_time, False)
            self.update('run_time_float', self.run_time_float, False)

        self.save()

    def reset_record(self):
        """
        运行记录重置 非公共部分由各app自行实现
        :return:
        """
        self.update_status(AppRunRecord.STATUS_WAIT, only_status=True)

    @property
    def run_status_under_now(self):
        """
        基于当前时间显示的运行状态
        :return:
        """
        if self._should_reset_by_dt():
            return AppRunRecord.STATUS_WAIT
        else:
            return self.run_status

    @property
    def is_done(self) -> bool:
        """
        是否已经完成
        """
        return self.run_status == AppRunRecord.STATUS_SUCCESS

    def _should_reset_by_dt(self) -> bool:
        """
        根据时间判断是否应该重置状态
        :return:
        """
        current_dt = self.get_current_dt()
        if self.record_period == AppRunRecordPeriod.DAILY:
            return self.dt != current_dt
        elif self.record_period == AppRunRecordPeriod.WEEKLY:
            return os_utils.get_sunday_dt(self.dt) != os_utils.get_sunday_dt(current_dt)
        else:
            return True

    def get_current_dt(self) -> str:
        """
        获取当前时间的dt
        :return:
        """
        return os_utils.get_dt(self.game_refresh_hour_offset)

    @staticmethod
    def app_record_now_time_str() -> str:
        """
        返回当前时间字符串
        :return: 例如 11-13 10:11
        """
        current_time = datetime.now()
        return current_time.strftime("%m-%d %H:%M")
