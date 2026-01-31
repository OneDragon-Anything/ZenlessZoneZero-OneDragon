from pathlib import Path

import yaml

from one_dragon.utils import os_utils


class RedemptionCodeConfig:
    """兑换码配置类，管理全局兑换码数据的存储和操作

    注意：此类不继承ApplicationConfig，因为兑换码配置是全局配置，
    不应该依赖于instance_idx，配置文件直接保存在config/目录下
    """

    def __init__(self) -> None:
        # 示例配置文件路径（Git追踪，开发者维护）
        self.sample_config_file_path = Path(os_utils.get_path_under_work_dir('config')) / 'redemption_codes.sample.yml'

        # 用户配置文件路径（不被Git追踪，用户自定义）
        self.user_config_file_path = Path(os_utils.get_path_under_work_dir('config')) / 'redemption_codes.yml'

    def _load_config_from_file(self, file_path: Path) -> list[str]:
        """从指定文件路径加载配置

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

    def _load_global_config(self) -> list[str]:
        """加载全局配置文件（仅用于GUI显示）

        只读取用户配置文件，不读取示例配置
        用户配置不存在返回空列表

        Returns:
            兑换码列表
        """
        # 只读取用户配置
        return self._load_config_from_file(self.user_config_file_path)

    def _save_global_config(self, codes_list: list[str]) -> None:
        """保存全局配置文件到用户配置路径

        始终保存到 user_config_file_path (redemption_codes.yml)
        确保 config/ 目录存在
        添加用户配置文件注释说明

        Args:
            codes_list: 兑换码列表
        """
        try:
            # 确保 config/ 目录存在
            self.user_config_file_path.parent.mkdir(parents=True, exist_ok=True)

            config_data = [
                {'code': code, 'end_dt': 20990101}
                for code in codes_list if code.strip()
            ]

            with open(self.user_config_file_path, 'w', encoding='utf-8') as f:
                # 写入注释说明
                f.write("# 用户自定义兑换码列表\n")
                f.write("# 此文件不会被Git追踪，不会被自动更新覆盖\n")
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
