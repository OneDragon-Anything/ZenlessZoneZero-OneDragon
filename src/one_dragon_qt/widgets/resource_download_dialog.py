from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    MessageBoxBase,
    SubtitleLabel,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.env_config import EnvConfig
from one_dragon.envs.repo_config import RepoConfig
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.services.download_queue_service import (
    DownloadQueueService,
    ResourceDownloadSpec,
    ResourceDownloadTaskState,
)
from one_dragon_qt.widgets.combo_box import ComboBox


def build_resource_source_options(env_config: EnvConfig) -> list[ConfigItem]:
    """构造资源下载源选项，自动项显示真实的首选源。"""
    repo_config = env_config.repo_config
    source_id = env_config.last_resource_source or env_config.get_recommended_resource_source()
    preferred = repo_config.get_resource_source(source_id) if source_id else None
    preferred_reason = gt('上次成功') if env_config.last_resource_source else gt('推荐')

    auto_label = gt('自动')
    if preferred is not None:
        auto_label = f'{auto_label} · {preferred_reason} {preferred.label}'
    options: list[ConfigItem] = [ConfigItem(auto_label, RepoConfig.AUTO_RESOURCE_SOURCE_VALUE)]
    options.extend(ConfigItem(source.label, source.source_id) for source in repo_config.resource_sources)
    return options


class ResourceUpdateDialog(MessageBoxBase):
    """选择要加入统一下载队列的资源。"""

    def __init__(
        self,
        ctx: OneDragonEnvContext,
        queue: DownloadQueueService,
        specs: list[ResourceDownloadSpec],
        title: str = '可用资源更新',
        show_remember: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """创建资源选择弹窗，下载源只在确认时保存。"""
        super().__init__(parent)
        self.ctx: OneDragonEnvContext = ctx
        self.queue: DownloadQueueService = queue
        self.specs: list[ResourceDownloadSpec] = specs
        self.yesButton.setText(gt('下载选中项'))
        self.cancelButton.setText(gt('稍后'))

        self.viewLayout.addWidget(SubtitleLabel(gt(title)))
        self.viewLayout.addSpacing(8)
        self._checks: dict[str, CheckBox] = {}
        grid = QGridLayout()
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        for row, spec in enumerate(specs):
            existing = queue.get_task(spec.task_key)
            retryable = existing is not None and existing.state in (
                ResourceDownloadTaskState.FAILED,
                ResourceDownloadTaskState.CANCELLED,
            )
            already_queued = existing is not None and not retryable
            check = CheckBox(spec.title)
            check.setChecked(not already_queued)
            check.setEnabled(not already_queued)
            check.stateChanged.connect(self._update_confirm_enabled)
            version = f'{spec.current_version or "未安装"} → {spec.target_version}'
            reason = (
                gt('已在队列')
                if already_queued
                else gt('重新下载')
                if retryable
                else (spec.note or gt('缺失或有新版本'))
            )
            grid.addWidget(check, row, 0)
            detail = QWidget()
            detail_layout = QHBoxLayout(detail)
            detail_layout.setContentsMargins(0, 0, 0, 0)
            detail_layout.addWidget(BodyLabel(version))
            detail_layout.addStretch(1)
            detail_layout.addWidget(CaptionLabel(reason))
            grid.addWidget(detail, row, 1)
            self._checks[spec.task_key] = check
        self.viewLayout.addLayout(grid)

        source_row = QHBoxLayout()
        source_row.addWidget(BodyLabel(gt('下载源')))
        self.source_combo = ComboBox()
        for option in build_resource_source_options(ctx.env_config):
            self.source_combo.addItem(option.label, userData=option.value)
        current_source = ctx.env_config.resource_source
        for index in range(self.source_combo.count()):
            if self.source_combo.itemData(index) == current_source:
                self.source_combo.setCurrentIndex(index)
                break
        source_row.addWidget(self.source_combo, 1)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addLayout(source_row)

        self.remember_check: CheckBox | None = None
        if show_remember:
            self.remember_check = CheckBox(gt('以后自动下载，不再询问'))
            self.remember_check.setChecked(False)
            self.viewLayout.addWidget(self.remember_check)

        self.widget.setMinimumWidth(560)
        self._update_confirm_enabled()

    @property
    def remember_choice(self) -> bool:
        """返回是否记住自动下载选择。"""
        return self.remember_check is not None and self.remember_check.isChecked()

    def selected_specs(self) -> list[ResourceDownloadSpec]:
        """返回当前勾选的资源。"""
        return [spec for spec in self.specs if self._checks[spec.task_key].isChecked()]

    def selected_source(self) -> str:
        """返回弹窗中的临时下载源。"""
        value = self.source_combo.currentData()
        return str(value) if value is not None else RepoConfig.AUTO_RESOURCE_SOURCE_VALUE

    def validate(self) -> bool:
        """确认时保存下载源，实际入队由调用方完成。"""
        if not self.selected_specs():
            return False
        self.ctx.env_config.resource_source = self.selected_source()
        return True

    def _update_confirm_enabled(self) -> None:
        """没有可选项时禁用确认按钮。"""
        self.yesButton.setEnabled(any(check.isChecked() for check in self._checks.values()))
