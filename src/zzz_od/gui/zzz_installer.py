import os
import sys
import shutil

from pathlib import Path
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme
from one_dragon_qt.app.directory_picker import DirectoryPickerWindow


if __name__ == '__main__':
    app = QApplication(sys.argv)
    setTheme(Theme['AUTO'])

    if hasattr(sys, '_MEIPASS'):
        icon_path = Path(sys._MEIPASS) / 'resources/assets/ui/logo.ico'
    else:
        icon_path = Path.cwd() / 'assets/ui/logo.ico'
    installer_dir = Path(sys.argv[0]).resolve().parent

    picker_window = DirectoryPickerWindow(icon_path=icon_path)
    picker_window.exec()
    work_dir = picker_window.selected_directory
    if not work_dir:
        sys.exit(0)
    os.chdir(work_dir)

    # 解压资源
    if hasattr(sys, '_MEIPASS'):
        resources_path = Path(sys._MEIPASS) / 'resources'
        shutil.copytree(resources_path, work_dir, dirs_exist_ok=True)

    # 延迟导入
    from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
    from one_dragon.utils.i18_utils import gt, detect_and_set_default_language
    from zzz_od.gui.zzz_installer_window import ZInstallerWindow

    _ctx = OneDragonEnvContext()
    _ctx.installer_dir = installer_dir
    _ctx.async_update_gh_proxy()
    detect_and_set_default_language()
    w = ZInstallerWindow(_ctx, gt(f'{_ctx.project_config.project_name}-installer'))
    w.show()
    app.exec()
    _ctx.after_app_shutdown()
