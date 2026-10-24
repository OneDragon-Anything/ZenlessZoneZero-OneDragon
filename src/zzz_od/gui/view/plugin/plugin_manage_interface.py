"""插件管理页。

只列本机已经安装（订阅）的第三方插件：可以导入 ZIP / 文件夹、打开插件目录、
更新到市场最新版本，或者取消订阅（卸载）。点卡片进入插件详情。
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import TypeVar

from packaging import version
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QResizeEvent
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
)

from one_dragon.base.operation.application.plugin_import_service import (
    ImportResult,
    PluginPreviewInfo,
)
from one_dragon.base.operation.application.plugin_info import PluginInfo
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.plugin_card import (
    BADGE_SUBSCRIBED,
    BADGE_UPDATE,
    PluginCard,
    PluginCardGrid,
    PluginPager,
)
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.plugin.plugin_operation_mixin import PluginOperationMixin

_T = TypeVar("_T")


class PluginManageInterface(PluginOperationMixin, VerticalScrollInterface):
    """插件管理页：本机已安装的插件。"""

    def __init__(
        self,
        ctx: ZContext,
        parent: QWidget | None = None,
    ) -> None:
        self.init_plugin_operation(ctx)

        VerticalScrollInterface.__init__(
            self,
            object_name='plugin_manage_interface',
            content_widget=None,
            parent=parent,
            nav_text_cn='插件管理',
        )
        self.connect_cover_signal()

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------

    def get_fixed_top_widget(self) -> QWidget:
        """顶部固定的搜索与操作栏。"""
        top = QWidget(self)
        layout = QHBoxLayout(top)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(8)

        self.search_edit = LineEdit(top)
        self.search_edit.setPlaceholderText(gt('搜索已安装插件'))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit, 1)

        self.import_btn = PrimaryPushButton(FluentIcon.ADD, gt('导入 ZIP'), top)
        self.import_btn.clicked.connect(self._on_import_clicked)
        layout.addWidget(self.import_btn)

        self.import_dir_btn = PushButton(FluentIcon.FOLDER_ADD, gt('导入文件夹'), top)
        self.import_dir_btn.clicked.connect(self._on_import_dir_clicked)
        layout.addWidget(self.import_dir_btn)

        self.open_dir_btn = PushButton(FluentIcon.FOLDER, gt('打开目录'), top)
        self.open_dir_btn.clicked.connect(self._on_open_dir_clicked)
        layout.addWidget(self.open_dir_btn)

        self.refresh_btn = PushButton(FluentIcon.SYNC, gt('刷新'), top)
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        layout.addWidget(self.refresh_btn)

        return top

    def get_content_widget(self) -> QWidget:
        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.status_label = CaptionLabel(content)
        self.status_label.setTextColor('#8a8a8a', '#9a9a9a')
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        self.card_grid = PluginCardGrid(content)
        layout.addWidget(self.card_grid)

        self.pager = PluginPager(content)
        layout.addWidget(self.pager, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)
        self.init_paging(self.card_grid, self.pager)
        return content

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.refresh_cards()
        if self.market_snapshot is None:
            self.load_market()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.close_plugin_operation()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # 卡片
    # ------------------------------------------------------------------

    def refresh_cards(self) -> None:
        """重建已安装插件卡片。"""
        self.card_grid.clear()
        self.reset_card_registry()

        plugins = self.ctx.factory_manager.third_party_plugins
        update_count = 0
        cards: list[PluginCard] = []
        for plugin_info in plugins:
            entry = self.find_market_entry(plugin_info)
            update_version = self.pending_update_version(plugin_info, entry)
            if update_version:
                update_count += 1
                badge_text = gt('可更新 v{version}').format(version=update_version)
                badge_kind = BADGE_UPDATE
            else:
                badge_text = gt('已订阅')
                badge_kind = BADGE_SUBSCRIBED

            meta_parts = []
            if plugin_info.version:
                meta_parts.append(f'v{plugin_info.version}')
            if plugin_info.author:
                meta_parts.append(plugin_info.author)

            plugin_id = entry.plugin_id if entry is not None else plugin_info.app_id
            card = self.make_card(
                title=plugin_info.app_name,
                meta_text=' · '.join(meta_parts),
                seed=plugin_id,
                cover=self.cover_for(
                    plugin_id,
                    entry.cover_url if entry is not None else '',
                    plugin_info,
                ),
                badge_text=badge_text,
                badge_kind=badge_kind,
                on_click=partial(self.open_installed_detail, plugin_info),
                parent=self.card_grid,
            )
            self.remember_card(
                card, plugin_id, entry.cover_url if entry is not None else ''
            )
            self.card_grid.add_card(card)
            cards.append(card)

        if plugins:
            text = gt('已订阅 {count} 个插件').format(count=len(plugins))
            if update_count:
                text += gt('，{count} 个可更新').format(count=update_count)
        else:
            text = gt('还没有订阅任何插件，去插件商店看看吧')
        self._set_status(text)
        self.set_cards(cards)

    def set_controls_enabled(self, enabled: bool) -> None:
        self.import_btn.setEnabled(enabled)
        self.import_dir_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)
        for card in self._all_cards:
            card.set_enabled_state(enabled)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update_paging()

    def _on_search_changed(self, text: str) -> None:
        self.set_card_filter(text)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    # ------------------------------------------------------------------
    # 导入 ZIP / 文件夹
    # ------------------------------------------------------------------

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

        self._start_plugin_task(
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
            self._finish_plugin_task()
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

        self._start_plugin_task(
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
                    title=gt('版本降级警告'),
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

                self._start_plugin_task(overwrite_task, self._finish_zip_import)
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

        self._start_plugin_task(
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
            self._finish_plugin_task()
            self._show_error(gt('没有找到可用插件'), gt('这个文件夹里没有找到可用插件'))
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
            self._finish_plugin_task()
            return

        def import_task() -> list[ImportResult]:
            return self.plugin_import_service.import_plugins_from_directory(
                dir_path,
                overwrite=False,
            )

        self._start_plugin_task(
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
                    title=gt('版本降级警告'),
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

                self._start_plugin_task(overwrite_task, self._finish_import_results)
                return

        self._finish_import_results(results)

    def _finish_import_results(self, results: list[ImportResult]) -> None:
        """汇总导入结果并刷新插件列表。"""
        self._finish_plugin_task()
        success_count = sum(1 for result in results if result.success)
        fail_count = len(results) - success_count
        if success_count > 0:
            self.ctx.refresh_application_registration()
            self.refresh_cards()
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
            self.refresh_cards()
            self.load_market(force=True)
            InfoBar.success(
                title=gt('刷新成功'),
                content=gt('已重新加载插件'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        except Exception as e:
            log.error(f'刷新插件失败: {e}', exc_info=True)
            self._show_error(gt('刷新失败'), str(e))

    def _on_open_dir_clicked(self) -> None:
        """打开插件目录"""
        plugins_dir = self.plugin_import_service.plugins_dir
        plugins_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(plugins_dir)))

    @staticmethod
    def _get_source_plugin_key(
        source_path: str | Path,
        plugin_name: str,
    ) -> tuple[str, str]:
        """返回来源路径和插件名组成的大小写不敏感匹配键。"""
        normalized_source = str(Path(source_path).resolve(strict=False)).casefold()
        return normalized_source, plugin_name.casefold()

    def _get_installed_plugins_by_package(self) -> dict[str, PluginInfo]:
        """按顶层插件目录索引已安装插件。"""
        installed_plugins: dict[str, PluginInfo] = {}
        package_depths: dict[str, int] = {}
        for plugin_info in self.ctx.factory_manager.third_party_plugins:
            package_dir = self.get_plugin_package_dir(plugin_info)
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
        """检查新版本是否低于旧版本"""
        if not new_ver or not old_ver:
            return False  # 无法比较时不认为是降级

        try:
            return version.parse(new_ver) < version.parse(old_ver)
        except version.InvalidVersion:
            return False
