import os
import yaml
from typing import Optional, List

from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.config.game_account_config import GameRegionEnum
from one_dragon.utils import os_utils


class RedemptionCode:

    def __init__(self, code: str, end_dt: str, server: str = 'cn'):
        self.code: str = code  # 兑换码
        self.end_dt = end_dt  # 失效日期
        self.server: str = server  # 服务器类型


class RedemptionCodeRunRecord(AppRunRecord):

    def __init__(self, instance_idx: Optional[int] = None, game_refresh_hour_offset: int = 0, ctx=None):
        AppRunRecord.__init__(
            self,
            'redemption_code',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset
        )

        self.ctx = ctx
        self.valid_code_list: List[RedemptionCode] = self._load_redemption_codes_from_file()

    def _load_redemption_codes_from_file(self) -> List[RedemptionCode]:
        """
        从配置文件加载兑换码
        """
        codes_file_path = os.path.join(os_utils.get_path_under_work_dir('config'), 'redemption_codes.yml')
        if not os.path.exists(codes_file_path):
            print(f"错误：未找到兑换码配置文件：{codes_file_path}")
            return []

        with open(codes_file_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        codes = []
        if config_data and isinstance(config_data, list):
            for item in config_data:
                code = item.get('code')
                end_dt = item.get('end_dt')
                server = item.get('server', 'cn')  # 默认为国服
                if code and end_dt:
                    codes.append(RedemptionCode(code, str(end_dt), server))  # 确保end_dt是字符串

        return codes

    def _get_user_server_type(self) -> str:
        """
        获取用户设置的服务器类型
        :return: 'cn' 表示国服/B服, 'global' 表示国际服
        """
        if self.ctx is None:
            return 'cn'  # 默认国服/B服

        game_region = self.ctx.game_account_config.game_region
        if game_region == GameRegionEnum.CN.value.value:
            return 'cn'
        else:
            return 'global'

    @property
    def run_status_under_now(self):
        current_dt = self.get_current_dt()
        unused_code_list = self.get_unused_code_list(current_dt)
        if len(unused_code_list) > 0:
            return AppRunRecord.STATUS_WAIT
        elif self._should_reset_by_dt():
            return AppRunRecord.STATUS_WAIT
        else:
            return self.run_status

    def check_and_update_status(self):
        current_dt = self.get_current_dt()
        unused_code_list = self.get_unused_code_list(current_dt)
        if len(unused_code_list) > 0:
            self.reset_record()
        else:
            AppRunRecord.check_and_update_status(self)

    @property
    def used_code_list(self) -> List[str]:
        """
        已使用的兑换码
        :return:
        """
        return self.get('used_code_list', [])

    @used_code_list.setter
    def used_code_list(self, new_value: List[str]) -> None:
        """
        已使用的兑换码
        :return:
        """
        self.update('used_code_list', new_value)

    def get_unused_code_list(self, dt: str) -> List[str]:
        """
        按日期和服务器类型获取未使用的兑换码
        :param dt: 当前日期字符串，格式为 YYYYMMDD
        :return: 未使用的有效兑换码列表

        注意：兑换码在 end_dt 这一天的 23:59:59 失效
        例如 end_dt=20241225，则在 2024-12-25 23:59:59 之前都有效
        """
        user_server = self._get_user_server_type()

        valid_code_strings = [
            i.code
            for i in self.valid_code_list
            if i.end_dt >= dt and i.server == user_server
        ]

        for used in self.used_code_list:
            if used in valid_code_strings:
                valid_code_strings.remove(used)

        return valid_code_strings

    def add_used_code(self, code: str) -> None:
        used = self.used_code_list
        used.append(code)
        self.used_code_list = used
