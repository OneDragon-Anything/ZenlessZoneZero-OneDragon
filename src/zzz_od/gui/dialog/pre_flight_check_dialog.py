from __future__ import annotations

from PySide6.QtWidgets import QWidget
from qfluentwidgets import BodyLabel, MessageBoxBase, SubtitleLabel

from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext


class PreFlightCheckDialog(MessageBoxBase):

    def __init__(self, issues: list[str], parent: QWidget | None = None):
        MessageBoxBase.__init__(self, parent)
        self.yesButton.setText(gt('前往配置'))
        self.cancelButton.setText(gt('仍然继续'))

        self.titleLabel = SubtitleLabel(gt('运行前检查'))
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(8)

        self.viewLayout.addWidget(BodyLabel(gt('以下配置项未就绪，可能影响正常运行：')))
        self.viewLayout.addSpacing(4)

        for issue in issues:
            item = BodyLabel(f' ⚠ {issue}')
            item.setWordWrap(True)
            self.viewLayout.addWidget(item)

        self.widget.setMinimumWidth(420)


def check_pre_flight(ctx: ZContext) -> list[tuple[str, str, str | None]]:
    from one_dragon.utils import yolo_config_utils

    issues: list[tuple[str, str, str | None]] = []

    if not ctx.game_account_config.game_path:
        issues.append((
            '未设置游戏路径 - 请在「账户管理 → 多账户管理 → 当前账户设置」中配置',
            'app_accounts_interface',
            None,
        ))

    if not yolo_config_utils.is_model_existed('flash_classifier', ctx.model_config.flash_classifier):
        issues.append((
            '闪光识别模型未下载 - 请在「设置 → 资源下载」中下载',
            'app_setting_interface',
            'resource_download_interface',
        ))

    return issues
