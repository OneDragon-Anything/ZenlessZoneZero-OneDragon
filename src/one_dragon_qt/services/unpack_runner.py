import contextlib
import hashlib
import json
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal


class UnpackResourceRunner(QThread):
    """资源解包线程：读取安装清单，将安装器目录中的文件逐一校验后搬运至工作目录。"""

    unpack_done = Signal(bool)        # 搬运完成信号，参数为是否成功
    log_message = Signal(str)       # 当前文件名日志信号
    progress_changed = Signal(int, int)  # (current, total) 复制进度信号

    def __init__(self, installer_dir: str, work_dir: str, parent=None) -> None:
        """
        Args:
            installer_dir: 安装器所在目录（含 install_manifest.json）
            work_dir: 目标工作目录
        """
        super().__init__(parent)
        self.installer_dir = installer_dir
        self.work_dir = work_dir
        self.is_done: bool = False
        self.is_success: bool = False

    @staticmethod
    def _copy_and_hash(src: Path, dst: Path) -> tuple[int, str]:
        """流式复制并计算哈希，返回 (大小, sha256)"""
        hasher = hashlib.sha256()
        size = 0
        with src.open('rb') as fsrc, dst.open('wb') as fdst:
            while True:
                buf = fsrc.read(1024 * 1024)  # 1MB chunk
                if not buf:
                    break
                fdst.write(buf)
                hasher.update(buf)
                size += len(buf)
        # 复制元数据（如修改时间），保持与 copy2 行为一致
        shutil.copystat(src, dst)
        return size, hasher.hexdigest().upper()

    def _copy_by_manifest_then_cleanup(self, src_root: Path, dst_root: Path) -> bool:
        """
        按照安装清单将 src_root 下的文件复制到 dst_root，校验通过后删除源文件。

        流程：
        1. 读取并解析 install_manifest.json
        2. 预检磁盘空间（留20%余量）
        3. 逐文件流式复制，校验 size / sha256
        4. 删除已复制的源文件（跳过正在运行的安装器 exe）
        5. 清理因搬运变空的目录
        6. 单独搬运清单文件本身
        """
        manifest_path = src_root / 'install_manifest.json'
        if not manifest_path.exists():
            return False

        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        except Exception as e:
            self.log_message.emit(f"读取安装清单失败: {e}")
            return False

        # 清单格式: {"version": "...", "generated_at": "...", "files": [...]}
        # 其中 files 为文件条目列表，每项包含 path / size / sha256
        if not isinstance(manifest, dict) or not isinstance(manifest.get('files'), list):
            self.log_message.emit("安装清单格式不正确")
            return False

        files: list[dict] = manifest['files']
        total = len(files)

        # 尝试获取正在运行的安装器 exe 路径，避免搬运过程中删除自己
        running_exe: Path | None = None
        try:
            running_exe = Path(sys.executable).resolve()
        except Exception:
            running_exe = None

        # 预计算总大小并检查磁盘空间（留20%余量），避免搬运过程中途失败导致残留
        # 沿父路径向上查找第一个存在的目录（防御 dst_root 尚未创建的边缘情况）
        total_size = sum(item.get('size', 0) for item in files if isinstance(item, dict))
        _check_path = dst_root
        while not _check_path.exists() and _check_path != _check_path.parent:
            _check_path = _check_path.parent
        try:
            free_space = shutil.disk_usage(_check_path).free
        except Exception:
            free_space = None
        if free_space is not None and free_space < total_size * 1.2:  # 留20%余量
            msg = f"磁盘空间不足: 需要 {total_size/(1024**3):.2f}GB, 可用 {free_space/(1024**3):.2f}GB"
            self.log_message.emit(msg)
            return False

        copied_files: list[tuple[Path, Path, dict]] = []
        for idx, item in enumerate(files, 1):
            if not isinstance(item, dict):
                continue
            rel = item.get('path')
            if not rel or not isinstance(rel, str):
                continue
            rel_norm = rel.replace('\\', '/')
            src_path = (src_root / rel_norm)
            dst_path = (dst_root / rel_norm)

            # 安全：只允许搬运 src_root 下的内容
            try:
                if not src_path.resolve().is_relative_to(src_root.resolve()):
                    continue
            except Exception:
                continue

            if src_path.is_dir():
                dst_path.mkdir(parents=True, exist_ok=True)
                continue

            if not src_path.exists():
                # 允许清单中包含不存在项（例如不同包型差异），跳过即可
                continue

            dst_path.parent.mkdir(parents=True, exist_ok=True)

            self.log_message.emit(rel_norm)
            self.progress_changed.emit(idx, total)

            try:
                actual_size, actual_sha = self._copy_and_hash(src_path, dst_path)
            except Exception as e:
                self.log_message.emit(f"复制文件失败，跳过: {rel} err={e}")
                with contextlib.suppress(Exception):
                    dst_path.unlink(missing_ok=True)
                continue

            expected_size = item.get('size')
            if isinstance(expected_size, int) and expected_size >= 0:
                if actual_size != expected_size:
                    self.log_message.emit(f"文件大小校验失败，跳过: {rel}")
                    with contextlib.suppress(Exception):
                        dst_path.unlink(missing_ok=True)
                    continue

            expected_sha = item.get('sha256')
            if isinstance(expected_sha, str) and expected_sha:
                if actual_sha != expected_sha.upper():
                    self.log_message.emit(f"文件哈希校验失败，跳过: {rel}")
                    with contextlib.suppress(Exception):
                        dst_path.unlink(missing_ok=True)
                    continue

            copied_files.append((src_path, dst_path, item))

        # 进入清理阶段：emit (-1, -1) 当清理阶段的双行状态标志
        self.progress_changed.emit(-1, -1)

        # 复制成功后删除源文件（跳过正在运行的安装器 exe）
        for src_path, _, _ in copied_files:
            with contextlib.suppress(Exception):
                if running_exe is not None:
                    try:
                        if src_path.resolve() == running_exe:
                            continue
                    except Exception:
                        if str(src_path).lower() == str(running_exe).lower():
                            continue
                src_path.unlink(missing_ok=True)

        # 尝试清理空目录：仅清理本次搬运涉及到的路径链，避免误删用户原本存在但为空的目录
        dirs_to_try: set[Path] = set()
        for src_path, _, _ in copied_files:
            parent = src_path.parent
            while True:
                if parent == src_root:
                    break
                # 只处理 src_root 下的目录
                try:
                    if not parent.resolve().is_relative_to(src_root.resolve()):
                        break
                except Exception:
                    # resolve 失败时，退化为字符串前缀判断
                    if not str(parent).lower().startswith(str(src_root).lower()):
                        break

                dirs_to_try.add(parent)
                if parent.parent == parent:
                    break
                parent = parent.parent

        for p in sorted(dirs_to_try, key=lambda x: len(str(x)), reverse=True):
            with contextlib.suppress(Exception):
                p.rmdir()

        # 清单文件本身不在清单列表中（避免自引用 sha 问题），这里单独搬运
        manifest_src = src_root / 'install_manifest.json'
        manifest_dst = dst_root / 'install_manifest.json'
        if manifest_src.exists():
            try:
                manifest_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(manifest_src, manifest_dst)
                with contextlib.suppress(Exception):
                    manifest_src.unlink(missing_ok=True)
            except Exception as e:
                self.log_message.emit(f"搬运清单文件失败: {e}")

        return True

    def run(self) -> None:
        """线程入口：若安装器目录与工作目录相同则视为已就位，否则执行清单搬运。"""
        src_root = Path(self.installer_dir)
        dst_root = Path(self.work_dir)

        # 安装器目录与工作目录相同，无需搬运，直接视为成功
        if self._is_same_dir(src_root, dst_root):
            self._finish(True)
            return

        # 无清单说明安装目录不含待搬运资源（开发环境 / 在线安装等），视为无需解包
        if not (src_root / 'install_manifest.json').exists():
            self._finish(True)
            return

        self.log_message.emit("正在读取安装清单...")

        # 逐文件复制+校验，成功后删除源文件；异常视为失败
        try:
            ok = self._copy_by_manifest_then_cleanup(src_root, dst_root)
            self._finish(ok)
        except Exception as e:
            self.log_message.emit(f"解包资源失败: {e}")
            self._finish(False)

    def _finish(self, success: bool) -> None:
        """记录结果并发射完成信号。"""
        self.is_done = True
        self.is_success = success
        self.unpack_done.emit(success)

    @staticmethod
    def _is_same_dir(a: Path, b: Path) -> bool:
        """判断两个路径是否指向同一目录（通过 resolve 消除符号链接和相对路径差异）。"""
        try:
            return a.resolve() == b.resolve()
        except Exception:
            # 路径 resolve 失败时降级为字符串比较（不区分大小写）
            return str(a).lower() == str(b).lower()
