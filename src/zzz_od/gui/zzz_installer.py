import os, sys, shutil
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme
from one_dragon_qt.app.directory_picker import DirectoryPickerWindow

def _unpack_resources():
    if hasattr(sys, '_MEIPASS'):
        work_dir = os.getcwd()
        resources_path = os.path.join(sys._MEIPASS, 'resources')
        if os.path.exists(resources_path):
            for root, dirs, files in os.walk(resources_path):
                rel_path = os.path.relpath(root, resources_path)
                dest_dir = os.path.join(work_dir, rel_path) if rel_path != '.' else work_dir
                os.makedirs(dest_dir, exist_ok=True)
                for file in files:
                    src_file = os.path.join(root, file)
                    dest_file = os.path.join(dest_dir, file)
                    shutil.move(src_file, dest_file)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    setTheme(Theme['AUTO'])

    if hasattr(sys, '_MEIPASS'):
        icon_path = os.path.join(sys._MEIPASS, 'resources', 'assets', 'ui', 'installer_logo.ico')
    else:
        icon_path = os.path.join(os.getcwd(), 'assets', 'ui', 'installer_logo.ico')
    picker_window = DirectoryPickerWindow(win_title="", icon_path=icon_path)
    picker_window.exec()
    work_dir = picker_window.selected_directory
    if not work_dir:
        sys.exit(0)
    os.chdir(work_dir)

    # 延迟导入
    from zzz_od.gui.zzz_installer_window import ZInstallerWindow
    from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
    from one_dragon.utils.i18_utils import gt, detect_and_set_default_language

    _unpack_resources()
    _ctx = OneDragonEnvContext()
    _ctx.async_update_gh_proxy()
    detect_and_set_default_language()
    w = ZInstallerWindow(_ctx, gt(f'{_ctx.project_config.project_name}-installer'))
    w.show()
    app.exec()
    _ctx.after_app_shutdown()
