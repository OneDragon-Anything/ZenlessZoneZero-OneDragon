from pathlib import Path

import yaml

from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.redemption_code.redemption_code_config import RedemptionCodeConfig


class RedemptionCode:

    def __init__(self, code: str, end_dt: str):
        self.code: str = code  # 兑换码
        self.end_dt = end_dt  # 失效日期


class RedemptionCodeRunRecord(AppRunRecord):

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0):
        AppRunRecord.__init__(
            self,
            'redemption_code',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset
        )

        self.valid_code_list: list[RedemptionCode] = self._load_redemption_codes_from_file()

    def _parse_config_file(self, file_path: Path) -> list[RedemptionCode]:
        """解析单个配置文件

        Args:
            file_path: 配置文件路径

        Returns:
            兑换码列表
        """
        if not file_path.exists():
            return []

        try:
            with open(file_path, encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

            codes = []
            if isinstance(config_data, list):
                for item in config_data:
                    if isinstance(item, dict):
                        code = item.get('code')
                        end_dt = item.get('end_dt')
                        if code and end_dt:
                            codes.append(RedemptionCode(code, str(end_dt)))

            return codes
        except yaml.YAMLError:
            return []

    def _load_redemption_codes_from_file(self) -> list[RedemptionCode]:
        """从配置文件加载兑换码

        合并用户配置文件 (redemption_codes.yml) 和示例配置文件 (redemption_codes.sample.yml)

        Returns:
            兑换码列表
        """
        # 使用 RedemptionCodeConfig 的路径定义
        config = RedemptionCodeConfig()

        # 读取配置文件路径
        user_path = config.user_config_file_path
        sample_path = config.sample_config_file_path

        codes = []

        # 读取用户配置
        codes.extend(self._parse_config_file(user_path))

        # 读取示例配置
        codes.extend(self._parse_config_file(sample_path))

        return codes

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
    def used_code_list(self) -> list[str]:
        """
        已使用的兑换码
        :return:
        """
        return self.get('used_code_list', [])

    @used_code_list.setter
    def used_code_list(self, new_value: list[str]) -> None:
        """
        已使用的兑换码
        :return:
        """
        self.update('used_code_list', new_value)

    def get_unused_code_list(self, dt: str) -> list[str]:
        """
        按日期获取未使用的兑换码
        :return:
        """
        valid_code_strings = [
            i.code
            for i in self.valid_code_list
            if i.end_dt >= dt
        ]

        for used in self.used_code_list:
            if used in valid_code_strings:
                valid_code_strings.remove(used)

        return valid_code_strings

    def add_used_code(self, code: str) -> None:
        used = self.used_code_list
        used.append(code)
        self.used_code_list = used
