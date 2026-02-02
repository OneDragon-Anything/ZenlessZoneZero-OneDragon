from dataclasses import dataclass

from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.base.operation.application_run_record import AppRunRecord
from zzz_od.application.redemption_code.redemption_code_config import (
    RedemptionCodeConfig,
)


@dataclass
class RedemptionCode:
    code: str  # 兑换码
    end_dt: str  # 失效日期


class RedemptionCodeRunRecord(AppRunRecord):

    def __init__(self, instance_idx: int | None = None, game_refresh_hour_offset: int = 0) -> None:
        AppRunRecord.__init__(
            self,
            'redemption_code',
            instance_idx=instance_idx,
            game_refresh_hour_offset=game_refresh_hour_offset
        )

        self.valid_code_list: list[RedemptionCode] = self._load_redemption_codes()

    def _get_codes_from_config(self, config: YamlConfig) -> dict[str, int]:
        """从配置中获取兑换码字典 {code: end_dt}"""
        codes = config.get('codes', {})
        if isinstance(codes, dict):
            return codes
        return {}

    def _load_redemption_codes(self) -> list[RedemptionCode]:
        """从配置文件加载兑换码

        合并用户配置和示例配置，用户配置优先

        Returns:
            兑换码列表
        """
        config = RedemptionCodeConfig()
        merged: dict[str, int] = {}

        # 先从 sample 配置读取
        merged.update(self._get_codes_from_config(config.sample_config))

        # 再用用户配置覆盖（用户配置优先）
        merged.update(self._get_codes_from_config(config.user_config))

        return [
            RedemptionCode(code, str(end_dt))
            for code, end_dt in merged.items()
        ]

    @property
    def run_status_under_now(self):
        current_dt = self.get_current_dt()
        unused_code_list = self.get_unused_code_list(current_dt)
        if len(unused_code_list) > 0 or self._should_reset_by_dt():
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
