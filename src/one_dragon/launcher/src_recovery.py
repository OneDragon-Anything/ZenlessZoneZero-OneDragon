"""src/ 目录损坏时的恢复逻辑与降级「资源更新模式」界面。

集成启动器（RuntimeLauncher）的正常运行依赖安装目录的 src/（git 同步的完整源码）。
当 src/ 缺失或损坏时，启动器无法加载任何业务代码，只能使用冻结在 exe 里的启动器代码。

本模块提供三条能力（全部只依赖冻结代码与 .runtime/，不读取 src/）：
1. 健康检查：只做文件存在性检查，不导入业务代码（半损坏的 src/ 在导入时会抛异常）；
2. 降级「资源更新模式」界面：一个最小 PySide6 窗口，只提供两种恢复手段：
   - 恢复内置代码：解压编译期打包进 .runtime 的 src_embedded.zip（与当前启动器版本匹配，离线可用）；
   - 下载最新版本：下载 GitHub Release 的 WithRuntime 包，校验模块清单兼容后提取其中的 src/ 恢复；
3. 恢复成功后重新启动启动器进程，让恢复出的代码走完整的正常启动流程。
"""

import contextlib
import ctypes
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path

# 健康检查的关键文件（相对 src/ 的路径）。覆盖每个顶层包的核心入口，
# 任一缺失或为空即判定 src/ 不完整。注意 __init__.py 经常是空文件，
# 所以这里只选用有实际内容的非空文件。
SRC_REQUIRED_RELATIVE_PATHS: tuple[str, ...] = (
    'one_dragon/envs/git_service.py',
    'one_dragon/envs/env_config.py',
    'one_dragon/base/operation/one_dragon_env_context.py',
    'one_dragon/utils/log_utils.py',
    'one_dragon_qt/windows/main_app_window_base.py',
    'zzz_od/win_exe/runtime_launcher.py',
    'zzz_od/gui/app.py',
    'onnxocr/onnx_paddleocr.py',
)

# 下载的临时目录（相对安装目录）
RECOVERY_TEMP_DIR_NAME = '.install/src_recovery'

ProgressCallback = Callable[[float, str], None]


# ================== 健康检查 ==================

def is_src_healthy(src_dir: Path) -> tuple[bool, str]:
    """检查 src/ 目录是否完整可用。

    只做轻量的文件存在性检查：src/ 半损坏时（如被杀毒软件删除部分文件），
    导入业务代码会抛异常，因此不能通过导入来验证。

    Returns:
        (是否完整, 不完整时的原因)
    """
    if not src_dir.is_dir():
        return False, f'src 目录不存在: {src_dir}'

    missing: list[str] = []
    for relative_path in SRC_REQUIRED_RELATIVE_PATHS:
        path = src_dir / relative_path
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(relative_path)
    if missing:
        return False, f'src 目录缺少关键文件: {", ".join(missing)}'
    return True, ''


# ================== 内嵌源码与配置读取 ==================

def _get_meipass_dir() -> Path:
    """PyInstaller 解包目录（frozen 时）；开发环境（未打包）返回空路径。"""
    return Path(getattr(sys, '_MEIPASS', '') or '')


def _find_embedded_src_zip() -> Path | None:
    """定位编译期打包的内嵌源码 zip，不存在时返回 None。"""
    embedded_zip = _get_meipass_dir() / 'src_embedded.zip'
    if embedded_zip.is_file():
        return embedded_zip
    return None


def _read_project_config() -> dict[str, str] | None:
    """从 .runtime 读取打包时写入的 project.yml，失败时返回 None。

    Returns:
        包含 project_name 与 github_homepage 的字典
    """
    project_yml = _get_meipass_dir() / 'resources' / 'config' / 'project.yml'
    if not project_yml.is_file():
        return None
    try:
        import yaml
        data = yaml.safe_load(project_yml.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    result: dict[str, str] = {}
    for key in ('project_name', 'github_homepage'):
        value = data.get(key)
        if isinstance(value, str) and value:
            result[key] = value
    # 任一必需键缺失都视为配置无效，避免调用方取键时抛 KeyError
    if len(result) != 2:
        return None
    return result


# ================== 恢复逻辑 ==================

def _backup_src_dir(src_dir: Path) -> tuple[Path | None, str]:
    """把损坏的 src/ 改名备份为 src.corrupted.<时间戳>。

    Returns:
        (备份路径, 错误消息)；备份路径为 None 且错误消息为空时表示 src 不存在（无需备份）。
    """
    if not src_dir.exists():
        return None, ''

    timestamp = time.strftime('%Y%m%d_%H%M%S')
    backup_dir = src_dir.with_name(f'{src_dir.name}.corrupted.{timestamp}')
    if backup_dir.exists():
        backup_dir = src_dir.with_name(f'{src_dir.name}.corrupted.{timestamp}.{uuid.uuid4().hex[:8]}')
    try:
        src_dir.rename(backup_dir)
        return backup_dir, ''
    except Exception as error:
        return None, f'备份旧 src 目录失败: {error}'


def _extract_src_members(
    zip_file: zipfile.ZipFile,
    install_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> int:
    """把 zip 内 src/ 前缀的条目安全解压到安装目录，返回解压的文件数。

    条目路径保留 src/ 前缀（解压后自然形成安装目录下的 src/）。
    只接受条目路径解析后仍位于安装目录内的文件，防止压缩包路径穿越。
    """
    src_prefix = 'src/'
    members = [member for member in zip_file.infolist() if member.filename.startswith(src_prefix)]
    dest_root = install_dir.resolve()
    file_count = 0

    for index, member in enumerate(members):
        target = (install_dir / member.filename).resolve()
        if not target.is_relative_to(dest_root):
            raise ValueError(f'压缩包内存在非法路径: {member.filename}')
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zip_file.open(member) as source, target.open('wb') as dest:
            shutil.copyfileobj(source, dest)
        file_count += 1
        if progress_callback is not None and (index + 1) % 100 == 0:
            progress_callback((index + 1) / len(members), f'正在解压 {member.filename[len(src_prefix):]}')

    return file_count


def _recover_src_from_zip(
    zip_path: Path,
    src_dir: Path,
    source_name: str,
    progress_callback: ProgressCallback | None = None,
) -> tuple[bool, str]:
    """备份损坏的 src/ 后从 zip 恢复 src/，恢复失败时保留备份现场。

    Args:
        zip_path: 源码 zip（条目带 src/ 前缀）
        src_dir: 安装目录下的 src/ 路径
        source_name: 来源描述（如「内置代码」「最新版本」），用于提示文案
    """
    if progress_callback is not None:
        progress_callback(-1, '正在备份损坏的 src 目录')
    backup_dir, error = _backup_src_dir(src_dir)
    if error:
        return False, error

    install_dir = src_dir.parent
    try:
        with zipfile.ZipFile(zip_path) as zip_file:
            _extract_src_members(zip_file, install_dir, progress_callback)
    except Exception as error:
        backup_tip = f'（旧目录已备份于 {backup_dir}）' if backup_dir is not None else ''
        return False, f'解压{source_name}失败: {error}{backup_tip}'
    backup_tip = f'（旧目录已备份于 {backup_dir}）' if backup_dir is not None else ''
    return True, f'已恢复{source_name}{backup_tip}'


def recover_from_embedded_src(
    src_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> tuple[bool, str]:
    """从内嵌源码包恢复 src/（与当前启动器版本匹配，离线可用）。

    恢复出的 src/ 不含 .git，重新启动后会自动走首次 clone 流程。
    """
    embedded_zip = _find_embedded_src_zip()
    if embedded_zip is None:
        return False, '未找到内嵌源码包，无法恢复；请尝试下载最新版本，或重新解压完整的 WithRuntime 压缩包'
    return _recover_src_from_zip(embedded_zip, src_dir, '内置代码', progress_callback)


def _download_file(
    url: str,
    dest_path: Path,
    proxy: str | None,
    progress_callback: ProgressCallback | None,
) -> None:
    """下载文件到指定路径，代理可空（直连）。"""
    proxy_address = (proxy or '').strip()
    if proxy_address and not proxy_address.startswith(('http://', 'https://')):
        proxy_address = f'http://{proxy_address}'
    proxies = {'http': proxy_address, 'https': proxy_address} if proxy_address else {}

    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
    except ValueError:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, headers={'User-Agent': 'OneDragon-RuntimeLauncher'})
    with opener.open(request, timeout=30) as response:
        total = int(response.headers.get('Content-Length') or 0)
        received = 0
        last_reported = 0
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with dest_path.open('wb') as dest:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                dest.write(chunk)
                received += len(chunk)
                if progress_callback is not None:
                    if total > 0:
                        progress_callback(received / total, f'正在下载 {received / 1024 / 1024:.1f} MB')
                    elif received - last_reported >= 512 * 1024:
                        last_reported = received
                        progress_callback(-1, f'正在下载 {received / 1024 / 1024:.1f} MB')


def _get_manifest_path_in_zip(zip_file: zipfile.ZipFile) -> str:
    """从下载包内 src/config/project.yml 读取模块清单路径，失败时用默认值。"""
    try:
        import yaml
        raw = zip_file.read('src/config/project.yml').decode('utf-8')
        data = yaml.safe_load(raw)
        path = data.get('manifest_path') if isinstance(data, dict) else None
        if isinstance(path, str) and path:
            return path
    except Exception:
        pass
    return 'deploy/module_manifest.py'


def _check_downloaded_manifest_compatible(zip_path: Path) -> tuple[bool, str]:
    """对比下载包内 src 的模块清单与当前运行时的模块清单。

    最新版代码可能依赖 .runtime/ 中没有的新第三方库；直接恢复会让启动器
    在启动时崩溃。因此下载前先校验，不兼容时拒绝恢复并提示先更新启动器。

    Returns:
        (是否兼容, 不兼容时的提示)
    """
    local_manifest_path = _get_meipass_dir() / 'module_manifest.py'
    if not local_manifest_path.is_file():
        return True, ''

    try:
        with zipfile.ZipFile(zip_path) as zip_file:
            remote_manifest = zip_file.read(f'src/{_get_manifest_path_in_zip(zip_file)}')
    except KeyError:
        return True, ''
    except zipfile.BadZipFile:
        return False, '下载的文件损坏或不是有效的压缩包，请重试或改用「恢复内置代码」'

    local_manifest = local_manifest_path.read_bytes()
    if local_manifest == remote_manifest:
        return True, ''

    # 兼容旧打包产物的 CRLF；先走 raw bytes 快路径，仅不一致时再归一化。
    if b'\r' in local_manifest or b'\r' in remote_manifest:
        normalized_local = local_manifest.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        normalized_remote = remote_manifest.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        if normalized_local == normalized_remote:
            return True, ''

    return False, '最新版本需要更新的启动器才能运行'


def download_latest_version(
    src_dir: Path,
    proxy: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[bool, str]:
    """下载最新版 WithRuntime 包，校验模块清单兼容后提取其中的 src/ 恢复。"""
    config = _read_project_config()
    if config is None:
        return False, '无法读取项目配置，无法确定下载地址'
    project_name = config['project_name']
    homepage = config['github_homepage'].rstrip('/')
    download_url = f'{homepage}/releases/latest/download/{project_name}-WithRuntime.zip'

    temp_dir = src_dir.parent / RECOVERY_TEMP_DIR_NAME
    zip_path = temp_dir / f'{project_name}-WithRuntime.zip'
    with contextlib.suppress(Exception):
        if zip_path.exists():
            zip_path.unlink()

    if progress_callback is not None:
        progress_callback(-1, f'正在下载 {download_url}')
    try:
        _download_file(download_url, zip_path, proxy, progress_callback)
    except Exception as error:
        return False, f'下载最新版本失败: {error}'

    if progress_callback is not None:
        progress_callback(-1, '正在检查版本兼容性')
    compatible, message = _check_downloaded_manifest_compatible(zip_path)
    if not compatible:
        with contextlib.suppress(Exception):
            zip_path.unlink()
        return False, f'{message}；请先使用「恢复内置代码」启动，再到「资源下载」页面更新启动器'

    try:
        return _recover_src_from_zip(zip_path, src_dir, '最新版本', progress_callback)
    finally:
        with contextlib.suppress(Exception):
            zip_path.unlink()


# ================== 进程重启 ==================

def _restart_launcher() -> None:
    """重新启动当前启动器进程（保留原始参数），并结束当前进程。"""
    subprocess.Popen([sys.executable, *sys.argv[1:]])
    sys.exit(0)


def _show_fallback_error(src_dir: Path) -> None:
    """PySide6 不可用时用系统弹窗提示用户。"""
    ctypes.windll.user32.MessageBoxW(
        None,
        f'src 目录不完整，且无法显示恢复界面:\n{src_dir}\n\n请重新解压完整的 WithRuntime 压缩包。',
        'OneDragon 集成启动器',
        0x10,  # MB_ICONERROR
    )


# ================== 降级「资源更新模式」界面 ==================

# PySide6 随 .runtime 分发给冻结环境；开发环境通常也可用。
# 仅当确实不可用时（极少见），_PYSIDE6_AVAILABLE 为 False，
# 界面入口退化为系统弹窗。
try:
    from PySide6.QtCore import QObject, QThread, Signal
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    _PYSIDE6_AVAILABLE = True
except Exception:
    _PYSIDE6_AVAILABLE = False


class _RecoveryWorker(QThread):
    """在后台线程执行恢复/下载任务，避免阻塞界面。"""

    progress_changed = Signal(float, str)
    task_finished = Signal(bool, str)

    def __init__(self, task: Callable[[ProgressCallback], tuple[bool, str]], parent: QObject | None = None) -> None:
        QThread.__init__(self, parent)
        self._task: Callable[[ProgressCallback], tuple[bool, str]] = task

    def run(self) -> None:
        try:
            success, message = self._task(self._report_progress)
        except Exception as error:
            success, message = False, f'发生异常: {error}'
        self.task_finished.emit(success, message)

    def _report_progress(self, progress: float, message: str) -> None:
        self.progress_changed.emit(progress, message)


class SrcRecoveryWindow(QWidget):
    """降级「资源更新模式」窗口：只提供程序代码恢复/下载功能。"""

    def __init__(self, src_dir: Path) -> None:
        super().__init__()
        self.src_dir: Path = src_dir
        self.recovered: bool = False
        self._worker: QThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle('OneDragon 资源更新')
        self.resize(600, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title_label = QLabel('程序文件不完整，已进入资源更新模式')
        title_label.setStyleSheet('font-size: 16px; font-weight: bold;')
        layout.addWidget(title_label)

        description_label = QLabel(
            '本模式仅提供程序代码的恢复与下载功能。恢复完成后将自动重新启动，'
            '请勿在恢复过程中关闭窗口或关闭电脑。'
        )
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        reason_label = QLabel(f'当前状态：{self.src_dir}')
        reason_label.setWordWrap(True)
        reason_label.setStyleSheet('color: gray;')
        layout.addWidget(reason_label)

        button_layout = QHBoxLayout()
        self.embedded_button = QPushButton('恢复内置代码')
        self.embedded_button.setToolTip('解压编译期打包的内置源码（与当前启动器版本匹配，无需联网）')
        self.download_button = QPushButton('下载最新版本')
        self.download_button.setToolTip('下载最新版完整包并恢复其中的源码（需要联网）')
        button_layout.addWidget(self.embedded_button)
        button_layout.addWidget(self.download_button)
        layout.addLayout(button_layout)

        proxy_layout = QHBoxLayout()
        proxy_label = QLabel('网络代理（可选，仅下载使用）')
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText('如 http://127.0.0.1:7890，留空为直连')
        proxy_layout.addWidget(proxy_label)
        proxy_layout.addWidget(self.proxy_input, stretch=1)
        layout.addLayout(proxy_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(500)
        layout.addWidget(self.log_text, stretch=1)

        self.embedded_button.clicked.connect(self._on_embedded_clicked)
        self.download_button.clicked.connect(self._on_download_clicked)

    def _append_log(self, message: str) -> None:
        self.log_text.appendPlainText(message)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.embedded_button.setEnabled(enabled)
        self.download_button.setEnabled(enabled)
        self.proxy_input.setEnabled(enabled)

    def _start_task(self, task: Callable[[ProgressCallback], tuple[bool, str]]) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._set_buttons_enabled(False)
        self._worker = _RecoveryWorker(task, parent=self)
        self._worker.progress_changed.connect(self._on_progress)
        self._worker.task_finished.connect(self._on_task_finished)
        self._worker.start()

    def _on_progress(self, progress: float, message: str) -> None:
        if progress < 0:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(round(progress * 100))
        self._append_log(message)

    def _on_task_finished(self, success: bool, message: str) -> None:
        self.progress_bar.setRange(0, 100)
        self._append_log(message)
        if success:
            self.recovered = True
            QMessageBox.information(self, '恢复完成', f'{message}\n\n正在重新启动...')
            self.close()
        else:
            QMessageBox.warning(self, '恢复失败', message)
            self._set_buttons_enabled(True)

    def _on_embedded_clicked(self) -> None:
        self._start_task(
            lambda callback: recover_from_embedded_src(self.src_dir, callback)
        )

    def _on_download_clicked(self) -> None:
        self._start_task(
            lambda callback: download_latest_version(
                self.src_dir,
                proxy=self.proxy_input.text(),
                progress_callback=callback,
            )
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.recovered and self._worker is not None and self._worker.isRunning():
            event.ignore()
            return
        super().closeEvent(event)


def show_src_recovery_gui(src_dir: Path) -> bool:
    """显示降级「资源更新模式」界面。

    界面只提供两种恢复手段：恢复内置代码、下载最新版本。
    恢复成功后会自动重启启动器进程（本函数不返回）；未恢复时返回 False。

    PySide6 不可用时退化为错误弹窗并返回 False。
    """
    if not _PYSIDE6_AVAILABLE:
        _show_fallback_error(src_dir)
        return False

    try:
        app = QApplication.instance() or QApplication(sys.argv)
    except Exception:
        _show_fallback_error(src_dir)
        return False

    window = SrcRecoveryWindow(src_dir)
    window.show()
    app.exec()
    if window.recovered:
        _restart_launcher()
        return True
    return False
