import os, sys, shutil
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme
from one_dragon_qt.app.directory_picker import DirectoryPickerWindow


if __name__ == '__main__':
    app = QApplication(sys.argv)
    setTheme(Theme['AUTO'])

    if hasattr(sys, '_MEIPASS'):
        icon_path = os.path.join(sys._MEIPASS, 'resources', 'assets', 'ui', 'logo.ico')
    else:
        icon_path = os.path.join(os.getcwd(), 'assets', 'ui', 'logo.ico')
    installer_dir = os.getcwd()
    picker_window = DirectoryPickerWindow(icon_path=icon_path)
    picker_window.exec()
    work_dir = picker_window.selected_directory
    if not work_dir:
        sys.exit(0)
    os.makedirs(work_dir, exist_ok=True)
    os.chdir(work_dir)

    # 解压资源
    if hasattr(sys, '_MEIPASS'):
        resources_path = os.path.join(sys._MEIPASS, 'resources')
        shutil.copytree(resources_path, work_dir, dirs_exist_ok=True)

    # 延迟导入
    from zzz_od.gui.zzz_installer_window import ZInstallerWindow
    from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
    from one_dragon.utils.i18_utils import gt, detect_and_set_default_language

    _ctx = OneDragonEnvContext()
    _ctx.installer_dir = installer_dir
    _ctx.async_update_gh_proxy()
    detect_and_set_default_language()
    w = ZInstallerWindow(_ctx, gt(f'{_ctx.project_config.project_name}-installer'))
    w.show()
    app.exec()
    _ctx.after_app_shutdown()
