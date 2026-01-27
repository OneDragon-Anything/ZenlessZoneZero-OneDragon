from pathlib import Path

import yaml

from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon.utils import os_utils
from zzz_od.application.redemption_code import redemption_code_const


class RedemptionCodeConfig(ApplicationConfig):
    """兑换码配置类，管理全局兑换码数据的存储和操作"""

    def __init__(self, instance_idx: int, group_id: str):
        super().__init__(
            app_id=redemption_code_const.APP_ID,
            instance_idx=instance_idx,
            group_id=group_id
        )
        # 全局配置文件路径
        self.global_config_file_path = Path(os_utils.get_path_under_work_dir('config')) / 'redemption_codes.yml'

    def _load_global_config(self) -> list[str]:
        """加载全局配置文件，直接返回兑换码列表"""
        if not self.global_config_file_path.exists():
            return []

        try:
            with open(self.global_config_file_path, encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

            # 只支持新格式：直接是兑换码列表
            if isinstance(config_data, list):
                codes = []
                for item in config_data:
                    if isinstance(item, dict):
                        code = item.get('code', '')
                        if code and code.strip():  # 确保code不为空且不是纯空白
                            codes.append(code.strip())
                return codes
            else:
                return []
        except yaml.YAMLError:
            # YAML 解析错误时返回空列表，可考虑添加日志记录
            return []

    def _save_global_config(self, codes_list: list[str]) -> None:
        """保存全局配置文件，保存兑换码列表"""
        try:
            self.global_config_file_path.parent.mkdir(parents=True, exist_ok=True)

            config_data = [
                {'code': code, 'end_dt': 20990101}
                for code in codes_list if code.strip()
            ]

            with open(self.global_config_file_path, 'w', encoding='utf-8') as f:
                # 写入注释说明
                f.write("# 兑换码列表\n")
                f.write("# 格式:\n")
                f.write("# - code: '兑换码'\n")
                f.write("#   end_dt: 过期时间\n")
                f.write("# 过期时间格式: YYYYMMDD 长期有效就填 20990101\n")

                # 手动写入YAML格式，确保格式正确
                for item in config_data:
                    f.write(f"- code: '{item['code']}'\n")
                    f.write(f"  end_dt: {item['end_dt']}\n")
        except Exception as e:
            raise Exception(f"保存配置文件失败: {e}") from e

    @property
    def codes_list(self) -> list[str]:
        """获取兑换码列表"""
        return self._load_global_config()

    @codes_list.setter
    def codes_list(self, new_value: list[str]) -> None:
        """设置兑换码列表"""
        self._save_global_config(new_value)

    def get_codes_text(self) -> str:
        """获取格式化的兑换码文本，用空格分开"""
        codes = self.codes_list
        return ' '.join(codes)

    def update_codes_from_text(self, text: str) -> None:
        """从文本更新兑换码列表，用空格分开，替换现有列表"""
        if not text or not text.strip():
            # 如果输入为空，清空列表
            self.codes_list = []
            return

        # 按空格分割，并过滤空白项
        codes = []
        for code in text.split():
            code = code.strip()
            if code:  # 忽略空白
                codes.append(code)

        # 用新的兑换码列表替换现有列表
        self.codes_list = codes
