import zipfile
from pathlib import Path


def find_src_dir(file_path: Path | str) -> Path | None:
    """从文件路径中查找最后一个 'src' 目录

    反向查找路径中最后一个名为 'src' 的目录，返回该目录的完整路径。

    Args:
        file_path: 文件或目录的路径

    Returns:
        Path | None: src 目录路径（含 src 本身），找不到返回 None
    """
    parts = Path(file_path).parts
    try:
        src_index = len(parts) - parts[::-1].index('src') - 1
        return Path(*parts[:src_index + 1])
    except ValueError:
        return None


def unzip_file(zip_file_path: str, unzip_dir_path: str) -> bool:
    """
    解压一个压缩包
    :param zip_file_path: 压缩包文件的路径。
    :param unzip_dir_path: 解压位置的文件夹
    :return: 是否解压成功
    """
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(unzip_dir_path)
        return True
    except Exception:
        return False
