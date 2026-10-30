from one_dragon.base.config.yaml_config import YamlConfig


class RedemptionCodeConfig:
    """兑换码配置类，管理全局兑换码数据的存储和操作

    包含两个 YamlConfig 实例：
    - user_config: 用户配置（可读写）
    - sample_config: 示例配置（只读 sample 文件）

    读取时合并两个配置，用户配置优先
    保存时只写入用户配置文件

    数据格式:
    codes:
      兑换码: 过期时间(YYYYMMDD)
    """

    def __init__(self) -> None:
        # 用户配置
        self.user_config = YamlConfig('redemption_codes')
        # 示例配置 - 使用 read_sample_only 始终读取 sample 文件
        self.sample_config = YamlConfig('redemption_codes', read_sample_only=True)

    def _get_codes_from_config(self, config: YamlConfig) -> dict[str, int]:
        """从配置中获取兑换码字典 {code: end_dt}，返回副本"""
        codes = config.get('codes', {})
        if isinstance(codes, dict):
            # 返回副本，避免直接修改原数据
            return dict(codes)
        return {}

    @property
    def sample_codes_dict(self) -> dict[str, int]:
        """获取 sample 配置的兑换码字典（只读）"""
        return self._get_codes_from_config(self.sample_config)

    @property
    def user_codes_dict(self) -> dict[str, int]:
        """获取用户配置的兑换码字典"""
        return self._get_codes_from_config(self.user_config)

    @property
    def codes_dict(self) -> dict[str, int]:
        """获取合并后的兑换码字典（用户配置优先）"""
        merged: dict[str, int] = {}

        # 先从 sample 配置读取
        merged.update(self._get_codes_from_config(self.sample_config))

        # 再用用户配置覆盖（用户配置优先）
        merged.update(self._get_codes_from_config(self.user_config))

        return merged

    @property
    def codes_list(self) -> list[str]:
        """获取合并后的兑换码列表"""
        return list(self.codes_dict.keys())

    def add_code(self, code: str, end_dt: int = 20990101) -> None:
        """添加单个兑换码到用户配置

        Args:
            code: 兑换码
            end_dt: 过期日期 (YYYYMMDD 格式)
        """
        code = code.strip()
        if not code:
            return

        # 获取当前用户配置的兑换码
        user_codes = self._get_codes_from_config(self.user_config)
        user_codes[code] = end_dt
        self.user_config.update('codes', user_codes)

    def update_code(self, old_code: str, new_code: str, end_dt: int) -> None:
        """更新兑换码（可修改兑换码和过期日期）

        Args:
            old_code: 原兑换码
            new_code: 新兑换码
            end_dt: 过期日期
        """
        user_codes = self._get_codes_from_config(self.user_config)

        # 如果是修改兑换码名称，先删除旧的
        if old_code != new_code and old_code in user_codes:
            del user_codes[old_code]

        # 添加/更新新的
        new_code = new_code.strip()
        if new_code:
            user_codes[new_code] = end_dt

        self.user_config.update('codes', user_codes)

    def delete_code(self, code: str) -> None:
        """删除兑换码

        Args:
            code: 要删除的兑换码
        """
        user_codes = self._get_codes_from_config(self.user_config)
        if code in user_codes:
            del user_codes[code]
            self.user_config.update('codes', user_codes)

    def add_sample_code(self, code: str, end_dt: int = 20990101) -> None:
        """添加兑换码到 sample 配置（供 CI 脚本使用）

        Args:
            code: 兑换码
            end_dt: 过期日期 (YYYYMMDD 格式)
        """
        code = code.strip()
        if not code:
            return

        sample_codes = self._get_codes_from_config(self.sample_config)
        sample_codes[code] = end_dt
        self.sample_config.update('codes', sample_codes)

    def delete_sample_code(self, code: str) -> None:
        """从 sample 配置删除兑换码（供 CI 脚本使用）

        Args:
            code: 要删除的兑换码
        """
        sample_codes = self._get_codes_from_config(self.sample_config)
        if code in sample_codes:
            del sample_codes[code]
            self.sample_config.update('codes', sample_codes)

    def clean_expired_sample_codes(self, today: int) -> int:
        """清理 sample 中过期的兑换码（供 CI 脚本使用）

        Args:
            today: 今天的日期 (YYYYMMDD 格式)

        Returns:
            删除的兑换码数量
        """
        sample_codes = self._get_codes_from_config(self.sample_config)
        original_count = len(sample_codes)
        sample_codes = {code: dt for code, dt in sample_codes.items() if dt >= today}
        expired_count = original_count - len(sample_codes)

        if expired_count > 0:
            self.sample_config.update('codes', sample_codes)

        return expired_count
