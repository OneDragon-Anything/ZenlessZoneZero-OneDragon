import contextlib
import webbrowser
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import TypeVar

from packaging import version
from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget
from qfluentwidgets import (
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    SettingCardGroup,
    ToolButton,
)

from one_dragon.base.operation.application.plugin_import_service import (
    ImportResult,
    PluginImportService,
    PluginPreviewInfo,
)
from one_dragon.base.operation.application.plugin_info import PluginInfo
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.context.zzz_context import ZContext

_T = TypeVar("_T")


class PluginImportRunner(QThread):
    """在后台线程执行插件导入任务。"""

    import_finished = Signal(object)
    import_failed = Signal(str)

    def __init__(
        self,
        task: Callable[[], object],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._task: Callable[[], object] = task

    def run(self) -> None:
        """执行任务并把结果或异常发回界面线程。"""
        try:
            result = self._task()
        except Exception as e:
            log.error(f"插件导入任务异常: {e}", exc_info=True)
            self.import_failed.emit(str(e))
            return
        self.import_finished.emit(result)


class PluginCard(MultiPushSettingCard):
    """单个插件的卡片"""

    def __init__(
        self,
        plugin_info: PluginInfo,
        on_delete: Callable[[PluginInfo], None],
        on_open_homepage: Callable[[PluginInfo], None],
        parent: QWidget | None = None,
    ) -> None:
        self.plugin_info: PluginInfo = plugin_info
        self.on_delete_callback: Callable[[PluginInfo], None] = on_delete
        self.on_open_homepage_callback: Callable[[PluginInfo], None] = on_open_homepage

        # 创建按钮
        buttons: list[QWidget] = []

        # 主页按钮（如果有链接）
        self.homepage_btn: PushButton = PushButton(text=gt("主页"))
        self.homepage_btn.clicked.connect(self._on_homepage_clicked)
        self.homepage_btn.setVisible(bool(plugin_info.homepage))
        buttons.append(self.homepage_btn)

        # 删除按钮
        self.delete_btn: ToolButton = ToolButton(FluentIcon.DELETE, parent=None)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        buttons.append(self.delete_btn)

        # 构建描述文本
        content_parts = []
        if plugin_info.version:
            content_parts.append(f"v{plugin_info.version}")
        if plugin_info.author:
            content_parts.append(f"作者: {plugin_info.author}")
        if plugin_info.description:
            content_parts.append(plugin_info.description)

        content = " | ".join(content_parts) if content_parts else ""

        MultiPushSettingCard.__init__(
            self,
            btn_list=buttons,
            title=plugin_info.app_name,
            content=content,
            icon=FluentIcon.LIBRARY,
            parent=parent,
        )

    def _on_homepage_clicked(self) -> None:
        if self.on_open_homepage_callback:
            self.on_open_homepage_callback(self.plugin_info)

    def _on_delete_clicked(self) -> None:
        if self.on_delete_callback:
            self.on_delete_callback(self.plugin_info)

    def update_plugin_info(self, plugin_info: PluginInfo) -> None:
        """更新插件信息

        Args:
            plugin_info: 新的插件信息
        """
        self.plugin_info = plugin_info

        # 更新标题
        self.titleLabel.setText(plugin_info.app_name)

        # 更新描述
        content_parts = []
        if plugin_info.version:
            content_parts.append(f"v{plugin_info.version}")
        if plugin_info.author:
            content_parts.append(f"作者: {plugin_info.author}")
        if plugin_info.description:
            content_parts.append(plugin_info.description)

        content = " | ".join(content_parts) if content_parts else ""
        self.contentLabel.setText(content)

        # 更新主页按钮可见性
        self.homepage_btn.setVisible(bool(plugin_info.homepage))


class SettingPluginInterface(VerticalScrollInterface):
    """插件管理界面"""

    def __init__(self, ctx: ZContext, parent: QWidget | None = None) -> None:
        self.ctx: ZContext = ctx
        self.plugin_import_service: PluginImportService = PluginImportService(ctx)
        self._plugin_cards: list[PluginCard] = []
        self._empty_card: MultiPushSettingCard | None = None
        self._import_runner: PluginImportRunner | None = None
        self._import_busy: bool = False

        VerticalScrollInterface.__init__(
            self,
            object_name='setting_plugin_interface',
            content_widget=None,
            parent=parent,
            nav_text_cn='插件管理'
        )

    def get_content_widget(self) -> QWidget:
        content_widget = Column(self)

        content_widget.add_widget(self._init_action_group())
        content_widget.add_widget(self._init_plugin_list_group(), stretch=1)

        return content_widget

    def _init_action_group(self) -> SettingCardGroup:
        """初始化操作按钮组"""
        action_group = SettingCardGroup(gt('操作'))

        # 导入 ZIP 按钮
        self.import_btn = PrimaryPushButton(FluentIcon.ADD, gt('导入 ZIP'))
        self.import_btn.clicked.connect(self._on_import_clicked)

        # 导入文件夹按钮
        self.import_dir_btn = PushButton(FluentIcon.FOLDER_ADD, gt('导入文件夹'))
        self.import_dir_btn.clicked.connect(self._on_import_dir_clicked)

        # 刷新按钮
        self.refresh_btn = PushButton(FluentIcon.SYNC, gt('刷新'))
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)

        # 打开目录按钮
        self.open_dir_btn = PushButton(FluentIcon.FOLDER, gt('打开目录'))
        self.open_dir_btn.clicked.connect(self._on_open_dir_clicked)

        self.open_market_btn = PushButton(FluentIcon.SHOPPING_CART, gt('插件市场'))
        self.open_market_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl('https://onedragon-anyone.github.io/plugin-registry/')
            )
        )

        # 创建操作卡片
        action_card = MultiPushSettingCard(
            btn_list=[self.import_btn, self.import_dir_btn, self.refresh_btn, self.open_dir_btn, self.open_market_btn],
            title=gt('插件操作'),
            content=gt('导入 zip 格式或目录格式的插件'),
            icon=FluentIcon.APPLICATION,
        )
        action_group.addSettingCard(action_card)

        # 说明卡片
        self.help_card = HelpCard(
            url=(
                'https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon/'
                'blob/main/docs/develop/guides/application_plugin_guide.md'
            ),
            title='插件开发说明',
            content='第三方插件需要包含 *_const.py 和 *_factory.py 文件，详见 plugins 目录下的 README.md'
        )
        action_group.addSettingCard(self.help_card)

        return action_group

    def _init_plugin_list_group(self) -> SettingCardGroup:
        """初始化插件列表组"""
        self.plugin_list_group = SettingCardGroup(gt('已安装插件'))

        # 创建空状态卡片（始终存在，仅通过显示/隐藏控制）
        self._empty_card = MultiPushSettingCard(
            btn_list=[],
            title=gt('暂无第三方插件'),
            content=gt('点击"导入插件"按钮添加新插件'),
            icon=FluentIcon.INFO,
        )
        self.plugin_list_group.addSettingCard(self._empty_card)

        return self.plugin_list_group

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self._refresh_plugin_list()

    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭前等待插件导入线程结束。"""
        self._wait_for_plugin_import()
        super().closeEvent(event)

    def _clear_plugin_cards(self) -> None:
        """清除旧的插件卡片（不删除 empty_card）

        注意：此方法只隐藏卡片，不真正删除。
        真正的删除在 _update_plugin_cards 中通过复用逻辑处理。
        """
        for card in self._plugin_cards:
            with contextlib.suppress(RuntimeError):
                card.hide()

    def _refresh_plugin_list(self) -> None:
        """刷新插件列表显示

        使用复用逻辑：
        - 如果插件数量增加，创建新卡片
        - 如果插件数量减少，隐藏多余卡片
        - 更新现有卡片的内容
        """
        # 获取第三方插件
        third_party_plugins = self.ctx.factory_manager.third_party_plugins

        if not third_party_plugins:
            # 隐藏所有插件卡片，显示空状态
            self._clear_plugin_cards()
            self._empty_card.show()
            self.plugin_list_group.adjustSize()
            return

        # 隐藏空状态
        self._empty_card.hide()

        # 更新卡片数量
        current_count = len(self._plugin_cards)
        new_count = len(third_party_plugins)

        if new_count > current_count:
            # 需要添加新卡片
            for i in range(current_count, new_count):
                card = PluginCard(
                    plugin_info=third_party_plugins[i],
                    on_delete=self._on_delete_plugin,
                    on_open_homepage=self._on_open_homepage,
                    parent=self
                )
                self._plugin_cards.append(card)
                self.plugin_list_group.addSettingCard(card)
        elif new_count < current_count:
            # 隐藏多余卡片
            for i in range(new_count, current_count):
                with contextlib.suppress(RuntimeError):
                    self._plugin_cards[i].hide()

        # 更新所有可见卡片的内容
        for i, plugin_info in enumerate(third_party_plugins):
            card = self._plugin_cards[i]
            card.update_plugin_info(plugin_info)
            card.show()

        # 调整组大小
        self.plugin_list_group.adjustSize()

    def _on_import_clicked(self) -> None:
        """导入 ZIP 来源。"""
        if self._import_busy:
            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            gt('选择插件压缩包'),
            '',
            'ZIP Files (*.zip)'
        )

        if not file_paths:
            return

        def preview_task() -> list[tuple[str, PluginPreviewInfo | None]]:
            previews: list[tuple[str, PluginPreviewInfo | None]] = []
            for file_path in file_paths:
                source_previews = self.plugin_import_service.preview_plugins_from_zip(
                    file_path
                )
                if source_previews:
                    previews.extend((file_path, preview) for preview in source_previews)
                else:
                    previews.append((file_path, None))
            return previews

        self._start_plugin_import(
            preview_task,
            partial(self._confirm_zip_import, file_paths),
        )

    def _confirm_zip_import(
        self,
        file_paths: list[str],
        previews: list[tuple[str, PluginPreviewInfo | None]],
    ) -> None:
        """确认 ZIP 预览后启动首次导入。"""
        preview_lines: list[str] = []
        for file_path, preview in previews:
            if preview is None:
                preview_lines.append(f"• {Path(file_path).stem} (无法读取信息)")
                continue

            line = f"• {preview.plugin_name}"
            if preview.version:
                line += f" (v{preview.version})"
            if preview.author:
                line += f" - {preview.author}"
            preview_lines.append(line)

        msg = MessageBox(
            title=gt('确认导入'),
            content=f'{gt("即将导入以下插件：")}\n\n{chr(10).join(preview_lines)}',
            parent=self.window()
        )
        msg.yesButton.setText(gt('确认导入'))
        msg.cancelButton.setText(gt('取消'))
        if not msg.exec():
            self._finish_import_operation()
            return

        def import_task() -> list[tuple[str, ImportResult]]:
            results: list[tuple[str, ImportResult]] = []
            for file_path in file_paths:
                source_results = self.plugin_import_service.import_plugins_from_zip(
                    file_path,
                    overwrite=False,
                )
                results.extend((file_path, result) for result in source_results)
            return results

        self._start_plugin_import(
            import_task,
            partial(self._handle_zip_import_results, previews),
        )

    def _handle_zip_import_results(
        self,
        previews: list[tuple[str, PluginPreviewInfo | None]],
        results: list[tuple[str, ImportResult]],
    ) -> None:
        """处理 ZIP 导入结果，并在需要时继续询问覆盖。"""
        existing_plugins = [
            (file_path, result)
            for file_path, result in results
            if not result.success and result.plugin_dir is not None
        ]
        if existing_plugins:
            preview_by_key = {
                self._get_source_plugin_key(file_path, preview.plugin_name): preview
                for file_path, preview in previews
                if preview is not None
            }
            installed_plugins = {
                name.casefold(): plugin
                for name, plugin in self._get_installed_plugins_by_package().items()
            }
            overwrite_info: list[tuple[str, str, str | None, str | None, bool]] = []
            for file_path, result in existing_plugins:
                preview = preview_by_key.get(
                    self._get_source_plugin_key(file_path, result.plugin_name)
                )
                new_version = preview.version if preview else None
                installed_plugin = installed_plugins.get(result.plugin_name.casefold())
                old_version = installed_plugin.version if installed_plugin else None
                overwrite_info.append(
                    (
                        file_path,
                        result.plugin_name,
                        new_version,
                        old_version,
                        self._is_version_lower(new_version, old_version),
                    )
                )

            normal_overwrite = [
                (file_path, name)
                for file_path, name, _, _, is_downgrade in overwrite_info
                if not is_downgrade
            ]
            downgrade_overwrite = [
                (file_path, name, new_version, old_version)
                for file_path, name, new_version, old_version, is_downgrade in overwrite_info
                if is_downgrade
            ]
            selected_overwrites: dict[str, set[str]] = {}

            if normal_overwrite:
                names = [name for _, name in normal_overwrite]
                msg = MessageBox(
                    title=gt('插件已存在'),
                    content=f'{gt("以下插件已存在，是否覆盖安装？")}\n\n{chr(10).join(names)}',
                    parent=self.window()
                )
                msg.yesButton.setText(gt('覆盖安装'))
                msg.cancelButton.setText(gt('跳过'))
                if msg.exec():
                    for file_path, name in normal_overwrite:
                        selected_overwrites.setdefault(file_path, set()).add(name)

            if downgrade_overwrite:
                warnings = [
                    f'{name}: {new_version or "未知"} ← {old_version or "未知"}'
                    for _, name, new_version, old_version in downgrade_overwrite
                ]
                msg = MessageBox(
                    title=gt('⚠️ 版本降级警告'),
                    content=f'{gt("以下插件将降级安装，确定继续？")}\n\n{chr(10).join(warnings)}',
                    parent=self.window()
                )
                msg.yesButton.setText(gt('确认降级'))
                msg.cancelButton.setText(gt('取消'))
                if msg.exec():
                    for file_path, name, _, _ in downgrade_overwrite:
                        selected_overwrites.setdefault(file_path, set()).add(name)

            if selected_overwrites:
                selected_keys = {
                    self._get_source_plugin_key(file_path, name)
                    for file_path, names in selected_overwrites.items()
                    for name in names
                }
                remaining_results = [
                    (file_path, result)
                    for file_path, result in results
                    if self._get_source_plugin_key(file_path, result.plugin_name)
                    not in selected_keys
                ]

                def overwrite_task() -> list[tuple[str, ImportResult]]:
                    merged_results = list(remaining_results)
                    for file_path, names in selected_overwrites.items():
                        overwrite_results = self.plugin_import_service.import_plugins_from_zip(
                            file_path,
                            overwrite=True,
                            selected_plugin_names=names,
                        )
                        merged_results.extend(
                            (file_path, result) for result in overwrite_results
                        )
                    return merged_results

                self._start_plugin_import(overwrite_task, self._finish_zip_import)
                return

        self._finish_zip_import(results)

    def _finish_zip_import(self, results: list[tuple[str, ImportResult]]) -> None:
        """完成 ZIP 导入并刷新插件列表。"""
        self._finish_import_results([result for _, result in results])

    def _on_import_dir_clicked(self) -> None:
        """导入松散目录来源。"""
        if self._import_busy:
            return

        dir_path = QFileDialog.getExistingDirectory(
            self,
            gt('选择插件文件夹'),
            ''
        )

        if not dir_path:
            return

        self._start_plugin_import(
            lambda: self.plugin_import_service.preview_plugins_from_directory(dir_path),
            partial(self._confirm_dir_import, dir_path),
        )

    def _confirm_dir_import(
        self,
        dir_path: str,
        previews: list[PluginPreviewInfo],
    ) -> None:
        """确认目录预览后启动首次导入。"""
        if not previews:
            self._finish_import_operation()
            InfoBar.error(
                title=gt('没有找到可用插件'),
                content=gt('这个文件夹里没有找到可用插件'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            return

        preview_lines: list[str] = []
        for preview in previews:
            line = f"• {preview.plugin_name}"
            if preview.version:
                line += f" (v{preview.version})"
            if preview.author:
                line += f" - {preview.author}"
            preview_lines.append(line)

        msg = MessageBox(
            title=gt('确认导入'),
            content=f'{gt("即将导入以下插件：")}\n\n{chr(10).join(preview_lines)}',
            parent=self.window()
        )
        msg.yesButton.setText(gt('确认导入'))
        msg.cancelButton.setText(gt('取消'))
        if not msg.exec():
            self._finish_import_operation()
            return

        def import_task() -> list[ImportResult]:
            return self.plugin_import_service.import_plugins_from_directory(
                dir_path,
                overwrite=False,
            )

        self._start_plugin_import(
            import_task,
            partial(self._handle_dir_import_results, dir_path, previews),
        )

    def _handle_dir_import_results(
        self,
        dir_path: str,
        previews: list[PluginPreviewInfo],
        results: list[ImportResult],
    ) -> None:
        """处理目录导入结果，并在需要时继续询问覆盖。"""
        existing_plugins = [
            result
            for result in results
            if not result.success and result.plugin_dir is not None
        ]
        if existing_plugins:
            preview_by_name = {
                preview.plugin_name.casefold(): preview
                for preview in previews
            }
            installed_plugins = {
                name.casefold(): plugin
                for name, plugin in self._get_installed_plugins_by_package().items()
            }
            overwrite_info: list[tuple[str, str | None, str | None, bool]] = []
            for result in existing_plugins:
                preview = preview_by_name.get(result.plugin_name.casefold())
                new_version = preview.version if preview else None
                installed_plugin = installed_plugins.get(result.plugin_name.casefold())
                old_version = installed_plugin.version if installed_plugin else None
                overwrite_info.append(
                    (
                        result.plugin_name,
                        new_version,
                        old_version,
                        self._is_version_lower(new_version, old_version),
                    )
                )

            normal_overwrite = [
                name
                for name, _, _, is_downgrade in overwrite_info
                if not is_downgrade
            ]
            downgrade_overwrite = [
                (name, new_version, old_version)
                for name, new_version, old_version, is_downgrade in overwrite_info
                if is_downgrade
            ]
            selected_names: set[str] = set()

            if normal_overwrite:
                msg = MessageBox(
                    title=gt('插件已存在'),
                    content=f'{gt("以下插件已存在，是否覆盖安装？")}\n\n{chr(10).join(normal_overwrite)}',
                    parent=self.window()
                )
                msg.yesButton.setText(gt('覆盖安装'))
                msg.cancelButton.setText(gt('跳过'))
                if msg.exec():
                    selected_names.update(normal_overwrite)

            if downgrade_overwrite:
                warnings = [
                    f'{name}: {new_version or "未知"} ← {old_version or "未知"}'
                    for name, new_version, old_version in downgrade_overwrite
                ]
                msg = MessageBox(
                    title=gt('⚠️ 版本降级警告'),
                    content=f'{gt("以下插件将降级安装，确定继续？")}\n\n{chr(10).join(warnings)}',
                    parent=self.window()
                )
                msg.yesButton.setText(gt('确认降级'))
                msg.cancelButton.setText(gt('取消'))
                if msg.exec():
                    selected_names.update(name for name, _, _ in downgrade_overwrite)

            if selected_names:
                selected_name_keys = {name.casefold() for name in selected_names}
                remaining_results = [
                    result
                    for result in results
                    if result.plugin_name.casefold() not in selected_name_keys
                ]

                def overwrite_task() -> list[ImportResult]:
                    merged_results = list(remaining_results)
                    merged_results.extend(
                        self.plugin_import_service.import_plugins_from_directory(
                            dir_path,
                            overwrite=True,
                            selected_plugin_names=selected_names,
                        )
                    )
                    return merged_results

                self._start_plugin_import(overwrite_task, self._finish_import_results)
                return

        self._finish_import_results(results)

    def _start_plugin_import(
        self,
        task: Callable[[], _T],
        on_finished: Callable[[_T], None],
    ) -> None:
        """在后台线程执行一次导入任务。"""
        if self._import_runner is not None:
            return

        runner = PluginImportRunner(task, self)
        runner.import_finished.connect(on_finished)
        runner.import_failed.connect(self._on_plugin_import_failed)
        runner.finished.connect(lambda: self._cleanup_import_runner(runner))
        self._import_runner = runner
        self._set_import_operation_enabled(False)
        runner.start()

    def _cleanup_import_runner(self, runner: PluginImportRunner) -> None:
        """清理已结束的导入线程引用。"""
        if self._import_runner is runner:
            self._import_runner = None
        runner.deleteLater()

    def _wait_for_plugin_import(self) -> None:
        """等待当前导入线程结束，避免界面销毁时线程仍在运行。"""
        runner = self._import_runner
        if runner is None or not runner.isRunning():
            return

        while runner.isRunning():
            runner.wait(50)
            QApplication.processEvents()

    def _on_plugin_import_failed(self, message: str) -> None:
        """处理后台导入异常。"""
        self._finish_import_operation()
        InfoBar.error(
            title=gt('导入失败'),
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )

    def _set_import_operation_enabled(self, enabled: bool) -> None:
        """设置导入期间会冲突的界面操作是否可用。"""
        self._import_busy = not enabled
        self.import_btn.setEnabled(enabled)
        self.import_dir_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
        for card in self._plugin_cards:
            card.delete_btn.setEnabled(enabled)

    def _finish_import_operation(self) -> None:
        """结束一次导入流程并恢复界面操作。"""
        self._set_import_operation_enabled(True)

    def _finish_import_results(self, results: list[ImportResult]) -> None:
        """汇总导入结果并刷新插件列表。"""
        self._finish_import_operation()
        success_count = sum(1 for result in results if result.success)
        fail_count = len(results) - success_count
        if success_count > 0:
            self.ctx.refresh_application_registration()
            self._refresh_plugin_list()
            InfoBar.success(
                title=gt('导入成功'),
                content=gt('成功导入 {count} 个插件').format(count=success_count),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

        if fail_count > 0:
            fail_messages = [
                f"{result.plugin_name}: {result.message}"
                for result in results
                if not result.success
            ]
            InfoBar.warning(
                title=gt('部分导入失败'),
                content='\n'.join(fail_messages),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def _on_refresh_clicked(self) -> None:
        """刷新按钮点击"""
        if self._import_busy:
            return

        try:
            self.ctx.refresh_application_registration()
            self._refresh_plugin_list()
            InfoBar.success(
                title=gt('刷新成功'),
                content=gt('已重新加载所有插件'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        except Exception as e:
            log.error(f'刷新插件失败: {e}', exc_info=True)
            InfoBar.error(
                title=gt('刷新失败'),
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def _on_open_dir_clicked(self) -> None:
        """打开插件目录"""
        plugins_dir = self.plugin_import_service.plugins_dir
        plugins_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(plugins_dir)))

    def _on_delete_plugin(self, plugin_info: PluginInfo) -> None:
        """删除插件"""
        if self._import_busy:
            return

        # 确认对话框
        msg_box = MessageBox(
            gt('确认删除'),
            gt('确定要删除插件 "{name}" 吗？此操作不可恢复。').format(
                name=plugin_info.app_name
            ),
            self.window()
        )
        msg_box.yesButton.setText(gt('删除'))
        msg_box.cancelButton.setText(gt('取消'))

        if not msg_box.exec():
            return

        # 执行删除
        plugin_package_dir = self._get_plugin_package_dir(plugin_info)
        if plugin_package_dir is None:
            InfoBar.error(
                title=gt('删除失败'),
                content=gt('无法定位插件目录，只能删除 plugins 目录下的插件'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            return

        if self._is_plugin_running(plugin_package_dir):
            InfoBar.error(
                title=gt('删除失败'),
                content=gt('插件正在运行，请先停止后再删除'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            return

        self._start_plugin_import(
            lambda: self.plugin_import_service.delete_plugin(plugin_package_dir),
            partial(self._finish_delete_plugin, plugin_info),
        )

    def _finish_delete_plugin(self, plugin_info: PluginInfo, result: ImportResult) -> None:
        """在界面线程处理插件删除结果。"""
        self._finish_import_operation()
        if result.success:
            self.ctx.refresh_application_registration()
            self._refresh_plugin_list()
            InfoBar.success(
                title=gt('删除成功'),
                content=gt('插件 "{name}" 已删除').format(name=plugin_info.app_name),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        InfoBar.error(
            title=gt('删除失败'),
            content=result.message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )

    def _on_open_homepage(self, plugin_info: PluginInfo) -> None:
        """打开插件主页"""
        if plugin_info.homepage:
            webbrowser.open(plugin_info.homepage)

    @staticmethod
    def _get_source_plugin_key(
        source_path: str | Path,
        plugin_name: str,
    ) -> tuple[str, str]:
        """返回来源路径和插件名组成的大小写不敏感匹配键。"""
        normalized_source = str(Path(source_path).resolve(strict=False)).casefold()
        return normalized_source, plugin_name.casefold()

    def _get_plugin_package_dir(self, plugin_info: PluginInfo) -> Path | None:
        """获取插件所属的顶层插件目录。"""
        if plugin_info.plugin_dir is None:
            return None

        plugins_root = self.plugin_import_service.plugins_dir.resolve(strict=False)
        plugin_dir = plugin_info.plugin_dir.resolve(strict=False)
        if plugin_dir == plugins_root or not plugin_dir.is_relative_to(plugins_root):
            return None

        relative_path = plugin_dir.relative_to(plugins_root)
        return plugins_root / relative_path.parts[0]

    def _is_plugin_running(self, plugin_package_dir: Path) -> bool:
        """判断插件包中是否有应用正在运行。"""
        run_context = self.ctx.run_context
        # 停止请求会先把状态改为 STOP，但应用线程退出前 current_app_id 仍有效。
        if run_context.current_app_id is None:
            return False

        current_plugin = self.ctx.factory_manager.get_plugin_info(
            run_context.current_app_id
        )
        if current_plugin is None or not current_plugin.is_third_party:
            return False

        current_package_dir = self._get_plugin_package_dir(current_plugin)
        if current_package_dir is None:
            return False
        return current_package_dir.resolve(strict=False) == plugin_package_dir.resolve(
            strict=False
        )

    def _get_installed_plugins_by_package(self) -> dict[str, PluginInfo]:
        """按顶层插件目录索引已安装插件。"""
        installed_plugins: dict[str, PluginInfo] = {}
        package_depths: dict[str, int] = {}
        for plugin_info in self.ctx.factory_manager.third_party_plugins:
            package_dir = self._get_plugin_package_dir(plugin_info)
            if package_dir is None or plugin_info.plugin_dir is None:
                continue

            package_name = package_dir.name
            plugin_dir = plugin_info.plugin_dir.resolve(strict=False)
            depth = len(plugin_dir.relative_to(package_dir).parts)
            if package_name not in installed_plugins or depth < package_depths[package_name]:
                installed_plugins[package_name] = plugin_info
                package_depths[package_name] = depth

        return installed_plugins

    def _is_version_lower(self, new_ver: str | None, old_ver: str | None) -> bool:
        """检查新版本是否低于旧版本

        Args:
            new_ver: 新版本号
            old_ver: 旧版本号

        Returns:
            bool: 如果新版本低于旧版本返回 True
        """
        if not new_ver or not old_ver:
            return False  # 无法比较时不认为是降级

        try:
            return version.parse(new_ver) < version.parse(old_ver)
        except version.InvalidVersion:
            return False
