from functools import cached_property

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from zzz_od.config.model_config import ModelConfig


class RecoveryContext(OneDragonEnvContext):
    """恢复界面使用的轻量上下文，不创建任何自动化运行资源。"""

    @cached_property
    def model_config(self) -> ModelConfig:
        return ModelConfig(self.repo_config)

    def init_ocr(self) -> None:
        """恢复模式只保存 OCR 配置，不创建 OCR session。"""
