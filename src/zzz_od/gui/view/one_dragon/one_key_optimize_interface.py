from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon.utils.log_utils import log
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.agent_combo_box_helper import agent_combo_box_helper
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.application.one_key_optimize import one_key_optimize_const
from zzz_od.context.zzz_context import ZContext


class OneKeyOptimizeInterface(AppRunInterface):
    """一键调优界面"""

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=one_key_optimize_const.APP_ID,
            object_name="one_key_optimize_interface",
            nav_text_cn="一键调优",
            nav_icon=FluentIcon.HOME,
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        """构建顶部内容区域"""
        from one_dragon_qt.widgets.column import Column

        top = Column()

        help_card = HelpCard(
            title="功能说明",
            content="自动识别并装备指定代理人的最大评分驱动盘，提升战斗能力。",
        )
        top.add_widget(help_card)

        # 代理人选择下拉框
        self.agent_select_opt = ComboBoxSettingCard(
            icon=FluentIcon.PEOPLE,
            title="选择代理人",
            content="选择要导航到的代理人"
        )
        top.add_widget(self.agent_select_opt)

        # 驱动盘套装选择下拉框
        self.drive_disk_set_opt = ComboBoxSettingCard(
            icon=FluentIcon.PALETTE,
            title="选择驱动盘套装（可选）",
            content="选择要筛选的驱动盘套装，留空则不进行筛选"
        )
        top.add_widget(self.drive_disk_set_opt)

        return top

    def _update_agent_options(self) -> None:
        """更新代理人选项"""
        if hasattr(self, "agent_select_opt"):
            agent_combo_box_helper.update_agent_options(self.agent_select_opt)

    def _update_drive_disk_set_options(self) -> None:
        """更新驱动盘套装选项"""
        if hasattr(self, "drive_disk_set_opt"):
            agent_combo_box_helper.update_drive_disk_options(self.drive_disk_set_opt)

    def on_interface_shown(self) -> None:
        """在界面显示时调用"""
        super().on_interface_shown()
        # 更新代理人选项和驱动盘套装选项
        self._update_agent_options()
        self._update_drive_disk_set_options()

    def _on_start_clicked(self) -> None:
        """在启动应用前保存用户选择的配置"""
        # 保存选择的代理人代码
        if hasattr(self, "agent_select_opt") and self.agent_select_opt:
            selected_value = self.agent_select_opt.getValue()
            self.ctx._one_key_optimize_agent_code = selected_value
            log.info(f"一键调优：选择的代理人: {selected_value}")
        else:
            self.ctx._one_key_optimize_agent_code = None
            log.info("一键调优：未选择代理人")

        # 保存选择的驱动盘套装
        if hasattr(self, "drive_disk_set_opt") and self.drive_disk_set_opt:
            selected_set = self.drive_disk_set_opt.getValue()
            self.ctx._one_key_optimize_drive_disk_set = selected_set
            log.info(f"一键调优：选择的驱动盘套装: {selected_set}")
        else:
            self.ctx._one_key_optimize_drive_disk_set = None
            log.info("一键调优：未选择驱动盘套装")

        # 调用父类方法启动应用
        AppRunInterface._on_start_clicked(self)
