import contextlib
import os
import subprocess
import sys
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QWidget
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
    PluginImportService,
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


class PluginCard(MultiPushSettingCard):
    """单个插件的卡片"""

    def __init__(
        self,
        plugin_info: PluginInfo,
        on_delete: callable,
        on_open_homepage: callable,
        parent=None
    ):
        self.plugin_info = plugin_info
        self.on_delete_callback = on_delete
        self.on_open_homepage_callback = on_open_homepage

        # 创建按钮
        buttons = []

        # 主页按钮（如果有链接）
        if plugin_info.homepage:
            self.homepage_btn = PushButton(text=gt("主页"))
            self.homepage_btn.clicked.connect(self._on_homepage_clicked)
            buttons.append(self.homepage_btn)

        # 删除按钮
        self.delete_btn = ToolButton(FluentIcon.DELETE, parent=None)
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
        if hasattr(self, 'homepage_btn'):
            self.homepage_btn.setVisible(bool(plugin_info.homepage))


class SettingPluginInterface(VerticalScrollInterface):
    """插件管理界面"""

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        self.plugin_import_service = PluginImportService(ctx)
        self._plugin_cards: list[PluginCard] = []
        self._empty_card: MultiPushSettingCard | None = None

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
        content_widget.add_widget(self._init_plugin_list_group())

        return content_widget

    def _init_action_group(self) -> SettingCardGroup:
        """初始化操作按钮组"""
        action_group = SettingCardGroup(gt('操作'))

        # 导入 ZIP 按钮
        self.import_btn = PrimaryPushButton(FluentIcon.ADD, gt('导入 ZIP'))
        self.import_btn.clicked.connect(self._on_import_clicked)

        # 导入目录按钮
        self.import_dir_btn = PushButton(FluentIcon.FOLDER_ADD, gt('导入目录'))
        self.import_dir_btn.clicked.connect(self._on_import_dir_clicked)

        # 刷新按钮
        self.refresh_btn = PushButton(FluentIcon.SYNC, gt('刷新'))
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)

        # 打开目录按钮
        self.open_dir_btn = PushButton(FluentIcon.FOLDER, gt('打开目录'))
        self.open_dir_btn.clicked.connect(self._on_open_dir_clicked)

        # 创建操作卡片
        action_card = MultiPushSettingCard(
            btn_list=[self.import_btn, self.import_dir_btn, self.refresh_btn, self.open_dir_btn],
            title=gt('插件操作'),
            content=gt('导入 zip 格式或目录格式的插件'),
            icon=FluentIcon.APPLICATION,
        )
        action_group.addSettingCard(action_card)

        # 说明卡片
        self.help_card = HelpCard(
            url='',
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
            for card in self._plugin_cards:
                with contextlib.suppress(RuntimeError):
                    card.hide()
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
        """导入按钮点击"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            gt('选择插件压缩包'),
            '',
            'ZIP Files (*.zip)'
        )

        if not file_paths:
            return

        # 预览所有插件信息
        previews = []
        for fp in file_paths:
            preview = self.plugin_import_service.preview_plugin(fp)
            if preview:
                previews.append((fp, preview))
            else:
                previews.append((fp, None))

        # 构建预览信息
        preview_lines = []
        for fp, preview in previews:
            if preview:
                line = f"• {preview.plugin_name}"
                if preview.version:
                    line += f" (v{preview.version})"
                if preview.author:
                    line += f" - {preview.author}"
                preview_lines.append(line)
            else:
                from pathlib import Path
                preview_lines.append(f"• {Path(fp).stem} (无法读取信息)")

        # 显示预览确认对话框
        msg = MessageBox(
            title=gt('确认导入'),
            content=gt(f'即将导入以下插件：\n\n{chr(10).join(preview_lines)}'),
            parent=self
        )
        msg.yesButton.setText(gt('确认导入'))
        msg.cancelButton.setText(gt('取消'))

        if not msg.exec():
            return

        # 执行导入（不覆盖）
        results = self.plugin_import_service.import_plugins(file_paths, overwrite=False)

        # 找出因已存在而失败的插件
        existing_plugins = [
            (file_paths[i], r) for i, r in enumerate(results)
            if not r.success and r.plugin_dir is not None
        ]

        # 如果有已存在的插件，询问是否覆盖
        if existing_plugins:
            # 获取已安装插件的版本信息
            installed_plugins = {
                p.app_id: p for p in self.ctx.factory_manager.third_party_plugins
            }

            # 检查版本信息
            overwrite_info = []  # (file_path, plugin_name, new_ver, old_ver, is_downgrade)
            for fp, r in existing_plugins:
                preview = self.plugin_import_service.preview_plugin(fp)
                new_ver = preview.version if preview else None
                old_ver = installed_plugins.get(r.plugin_name, None)
                old_ver_str = old_ver.version if old_ver else None

                is_downgrade = self._is_version_lower(new_ver, old_ver_str)
                overwrite_info.append((fp, r.plugin_name, new_ver, old_ver_str, is_downgrade))

            # 区分正常覆盖和降级覆盖
            normal_overwrite = [(fp, name) for fp, name, _, _, is_down in overwrite_info if not is_down]
            downgrade_overwrite = [(fp, name, new_v, old_v) for fp, name, new_v, old_v, is_down in overwrite_info if is_down]

            overwrite_paths = []

            # 处理正常覆盖
            if normal_overwrite:
                names = [name for _, name in normal_overwrite]
                msg = MessageBox(
                    title=gt('插件已存在'),
                    content=gt(f'以下插件已存在，是否覆盖安装？\n\n{chr(10).join(names)}'),
                    parent=self
                )
                msg.yesButton.setText(gt('覆盖安装'))
                msg.cancelButton.setText(gt('跳过'))
                if msg.exec():
                    overwrite_paths.extend([fp for fp, _ in normal_overwrite])

            # 处理降级覆盖（单独警告）
            if downgrade_overwrite:
                warnings = [
                    f'{name}: {new_v or "未知"} ← {old_v or "未知"}'
                    for _, name, new_v, old_v in downgrade_overwrite
                ]
                msg = MessageBox(
                    title=gt('⚠️ 版本降级警告'),
                    content=gt(f'以下插件将降级安装，确定继续？\n\n{chr(10).join(warnings)}'),
                    parent=self
                )
                msg.yesButton.setText(gt('确认降级'))
                msg.cancelButton.setText(gt('取消'))
                if msg.exec():
                    overwrite_paths.extend([fp for fp, _, _, _ in downgrade_overwrite])

            # 执行覆盖安装
            if overwrite_paths:
                overwrite_results = self.plugin_import_service.import_plugins(
                    overwrite_paths, overwrite=True
                )
                # 更新结果
                for i, fp in enumerate(overwrite_paths):
                    idx = file_paths.index(fp)
                    results[idx] = overwrite_results[i]

        # 统计结果
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count

        # 显示结果
        if success_count > 0:
            # 刷新应用注册
            self.ctx.refresh_application_registration()
            self._refresh_plugin_list()

            InfoBar.success(
                title=gt('导入成功'),
                content=gt(f'成功导入 {success_count} 个插件'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

        if fail_count > 0:
            fail_messages = [f"{r.plugin_name}: {r.message}" for r in results if not r.success]
            InfoBar.warning(
                title=gt('部分导入失败'),
                content='\n'.join(fail_messages),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def _on_import_dir_clicked(self) -> None:
        """导入目录按钮点击"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            gt('选择插件目录'),
            ''
        )

        if not dir_path:
            return

        # 预览插件信息
        preview = self.plugin_import_service.preview_directory(dir_path)

        if not preview:
            InfoBar.error(
                title=gt('无效的插件目录'),
                content=gt('该目录不包含有效的插件结构（缺少 *_factory.py 文件）'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            return

        # 构建预览信息
        preview_text = f"• {preview.plugin_name}"
        if preview.version:
            preview_text += f" (v{preview.version})"
        if preview.author:
            preview_text += f" - {preview.author}"

        # 显示预览确认对话框
        msg = MessageBox(
            title=gt('确认导入'),
            content=gt(f'即将导入以下插件：\n\n{preview_text}'),
            parent=self
        )
        msg.yesButton.setText(gt('确认导入'))
        msg.cancelButton.setText(gt('取消'))

        if not msg.exec():
            return

        # 尝试导入
        result = self.plugin_import_service.import_directory(dir_path, overwrite=False)

        if result.success:
            self.ctx.refresh_application_registration()
            self._refresh_plugin_list()
            InfoBar.success(
                title=gt('导入成功'),
                content=gt(f'插件 "{result.plugin_name}" 已导入'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        elif result.plugin_dir is not None:
            # 插件已存在，询问是否覆盖
            # 获取已安装版本
            installed = next(
                (p for p in self.ctx.factory_manager.third_party_plugins if p.app_id == result.plugin_name),
                None
            )
            old_ver = installed.version if installed else None
            new_ver = preview.version

            is_downgrade = self._is_version_lower(new_ver, old_ver)

            if is_downgrade:
                msg = MessageBox(
                    title=gt('⚠️ 版本降级警告'),
                    content=gt(f'插件 "{result.plugin_name}" 将从 {old_ver or "未知"} 降级到 {new_ver or "未知"}，确定继续？'),
                    parent=self
                )
                msg.yesButton.setText(gt('确认降级'))
            else:
                msg = MessageBox(
                    title=gt('插件已存在'),
                    content=gt(f'插件 "{result.plugin_name}" 已存在，是否覆盖安装？'),
                    parent=self
                )
                msg.yesButton.setText(gt('覆盖安装'))

            msg.cancelButton.setText(gt('取消'))

            if msg.exec():
                overwrite_result = self.plugin_import_service.import_directory(dir_path, overwrite=True)
                if overwrite_result.success:
                    self.ctx.refresh_application_registration()
                    self._refresh_plugin_list()
                    InfoBar.success(
                        title=gt('导入成功'),
                        content=gt(f'插件 "{overwrite_result.plugin_name}" 已覆盖安装'),
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                else:
                    InfoBar.error(
                        title=gt('导入失败'),
                        content=overwrite_result.message,
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                        parent=self
                    )
        else:
            InfoBar.error(
                title=gt('导入失败'),
                content=result.message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def _on_refresh_clicked(self) -> None:
        """刷新按钮点击"""
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

        if sys.platform == 'win32':
            os.startfile(plugins_dir)
        elif sys.platform == 'darwin':
            subprocess.run(['open', plugins_dir])
        else:
            subprocess.run(['xdg-open', plugins_dir])

    def _on_delete_plugin(self, plugin_info: PluginInfo) -> None:
        """删除插件"""
        # 确认对话框
        msg_box = MessageBox(
            gt('确认删除'),
            gt(f'确定要删除插件 "{plugin_info.app_name}" 吗？此操作不可恢复。'),
            self
        )
        msg_box.yesButton.setText(gt('删除'))
        msg_box.cancelButton.setText(gt('取消'))

        if not msg_box.exec():
            return

        # 执行删除
        if plugin_info.plugin_dir:
            result = self.plugin_import_service.delete_plugin(plugin_info.plugin_dir)
            if result.success:
                # 刷新应用注册
                self.ctx.refresh_application_registration()
                self._refresh_plugin_list()
                InfoBar.success(
                    title=gt('删除成功'),
                    content=gt(f'插件 "{plugin_info.app_name}" 已删除'),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
            else:
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
            from packaging.version import Version
            return Version(new_ver) < Version(old_ver)
        except Exception:
            # 简单字符串比较作为后备
            return new_ver < old_ver
