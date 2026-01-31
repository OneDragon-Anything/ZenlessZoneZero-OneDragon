from pathlib import Path

import yaml

from one_dragon.utils import os_utils


class RedemptionCodeConfig:
    """兑换码配置类，管理全局兑换码数据的存储和操作

    使用 YamlOperator 的设计模式，但独立实现以支持列表数据格式
    注意：此类不继承 ApplicationConfig，因为兑换码配置是全局配置，
    不应该依赖于 instance_idx，配置文件直接保存在 config/ 目录下
    """

    def __init__(self) -> None:
        # 配置文件路径
        config_dir = Path(os_utils.get_path_under_work_dir('config'))
        self.user_config_file_path = config_dir / 'redemption_codes.yml'
        self.sample_config_file_path = config_dir / 'redemption_codes.sample.yml'

        # 使用用户配置文件路径
        self.file_path = self.user_config_file_path
        self.data: list[dict[str, str | int]] = []
        self._read_from_file()

    def _read_from_file(self) -> None:
        """从 YAML 文件读取数据"""
        if not self.file_path.exists():
            return
        with open(self.file_path, encoding='utf-8') as f:
            loaded = yaml.safe_load(f)
            if not isinstance(loaded, list):
                return
            # 过滤非字典条目，防止用户手工编辑错误导致运行时异常
            for item in loaded:
                if isinstance(item, dict):
                    self.data.append(item)

    def _extract_codes(self) -> list[str]:
        """从 data 中提取兑换码列表"""
        codes: list[str] = []
        for item in self.data:
            code = item.get('code', '')
            if code and str(code).strip():
                codes.append(str(code).strip())
        return codes

    def save(self) -> None:
        """保存数据到文件，带注释"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.file_path, 'w', encoding='utf-8') as f:
            # 写入注释说明
            f.write("# 用户自定义兑换码列表\n")
            f.write("# 此文件不会被Git追踪，不会被自动更新覆盖\n")
            f.write("# 格式:\n")
            f.write("# - code: '兑换码'\n")
            f.write("#   end_dt: 过期时间\n")
            f.write("# 过期时间格式: YYYYMMDD 长期有效就填 20990101\n")

            # 写入数据
            for item in self.data:
                if 'code' in item:
                    f.write(f"- code: '{item['code']}'\n")
                    f.write(f"  end_dt: {item.get('end_dt', 20990101)}\n")

    @property
    def codes_list(self) -> list[str]:
        """获取兑换码列表"""
        return self._extract_codes()

    @codes_list.setter
    def codes_list(self, new_value: list[str]) -> None:
        """设置兑换码列表"""
        self.data = [
            {'code': code, 'end_dt': 20990101}
            for code in new_value if code.strip()
        ]
        self.save()

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
        codes: list[str] = []
        for code in text.split():
            code = code.strip()
            if code:  # 忽略空白
                codes.append(code)

        # 用新的兑换码列表替换现有列表
        self.codes_list = codes
