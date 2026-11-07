"""读取打包时的模块清单，检查新增导入能否由当前运行时满足。"""

import ast
import importlib
import sys
from pathlib import Path

from one_dragon.utils.log_utils import log


def load_runtime_manifest() -> bytes | None:
    """读取冻结运行时的打包清单；源码模式、清单缺失或读取失败时返回 None。"""
    if not getattr(sys, 'frozen', False):
        return None

    runtime_dir = Path(getattr(sys, '_MEIPASS', ''))
    manifest_path = runtime_dir / 'module_manifest.py'
    if not manifest_path.is_file():
        return None

    try:
        return manifest_path.read_bytes()
    except Exception:
        log.warning('读取本地模块清单失败，跳过检查', exc_info=True)
        return None


def _parse_manifest_imports(manifest: bytes) -> set[tuple[str, str]]:
    """解析清单中的导入要求，不执行清单代码。

    Args:
        manifest: 本地或目标版本中的清单内容。

    Returns:
        (模块名, 导入名称) 集合；导入名称为空表示只要求模块可导入。
    """
    imports: set[tuple[str, str]] = set()
    for node in ast.walk(ast.parse(manifest)):
        if isinstance(node, ast.Import):
            imports.update((alias.name, '') for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module is None or any(alias.name == '*' for alias in node.names):
                raise ValueError('模块清单不支持相对导入或通配符导入')
            imports.add((node.module, ''))
            imports.update((node.module, alias.name) for alias in node.names)
    return imports


def check_manifest_compatible(local_manifest: bytes, target_manifest: bytes) -> bool:
    """检查目标清单相对打包基准新增的导入，不改变模块搜索路径。

    Args:
        local_manifest: 打包时的清单内容。
        target_manifest: 目标版本的清单内容。

    Returns:
        新增导入均可用时返回 True；清单无法解析或依赖加载失败时返回 False。
    """
    if local_manifest == target_manifest:
        return True

    try:
        added_imports = _parse_manifest_imports(target_manifest) - _parse_manifest_imports(local_manifest)
    except (SyntaxError, UnicodeError, ValueError):
        log.warning('无法解析模块清单', exc_info=True)
        return False

    for module_name, import_name in sorted(added_imports):
        try:
            # 使用当前解释器的导入机制，覆盖 PYZ、标准库和 .pyd 等依赖。
            module = importlib.import_module(module_name)
            if import_name and not hasattr(module, import_name):
                # from package import name 中的 name 也可能是未加载的子模块。
                importlib.import_module(f'{module_name}.{import_name}')
        except Exception:
            dependency = f'{module_name}.{import_name}' if import_name else module_name
            log.warning(f'当前运行时无法导入 {dependency}', exc_info=True)
            return False

    return True
