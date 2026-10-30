"""app description 发现:从 factory 所属模块反射 Application 子类的 class docstring。

为 ``list_applications`` / ``ApplicationInfo.description`` 提供「源码盲 MCP 受众」可读的
应用用途描述,无需在 one_dragon 框架 factory 层手写 app 类引用样板。

设计要点(详见 ``.debug/temp/app-description-backend-refactor-proposal.md`` v1 评审结论):
- 仅排除 ``Application`` 基类;``ZApplication`` 等中间基类靠 **leaf 选择** 自动排除,
  勿硬编码排除集。
- ⚠️ **不能用 ``__module__`` 守卫**(与 ``operation_registry`` 不同):App 类是 import 进
  factory 模块的,定义在 ``xxx_app.py``,其 ``__module__`` 是 ``xxx.xxx_app`` 而非
  factory 模块 → 加 ``__module__`` 守卫会把所有 App 类排除(扫到 0 个)。改用 leaf 选择。
"""
import importlib
import inspect

from one_dragon.base.operation.application_base import Application
from zzz_od.backend._doc_utils import _doc_summary

# 仅排除 Application 基类;ZApplication 等中间基类靠 leaf 选择自动排除,勿硬编码
_ABSTRACT_APP_BASES: set[type] = {Application}


def _app_description(factory: object) -> str:
    """扫 factory 所属模块 namespace 找 Application 子类 → docstring 摘要(去 ``:param``)。

    经 factory 所属模块取 ``vars(mod)``,过滤出 ``Application`` 子类(排除 ``Application``
    基类本身),再做 **leaf 选择**(排除被其它候选类继承的,防 import 进来的中间基类如
    ``ZApplication`` 干扰)。恰好 1 个 leaf 时返回其 ``_doc_summary``;否则返空串。

    ⚠️ **不能用 ``__module__`` 守卫**:App 类是 import 进 factory 模块的,定义在
    ``xxx_app.py``,其 ``__module__`` 是 ``xxx.xxx_app`` 而非 factory 模块 → 加守卫会把
    所有 App 类排除(扫到 0 个)。leaf 选择是这里的正确口径。

    Args:
        factory: ``ApplicationFactory`` 实例(取 ``type(factory).__module__`` 定位其模块)。

    Returns:
        应用用途描述;factory 未 import App 类(0 个)或歧义(>1 个 leaf)时返空串。
        契约测试硬卡每个注册 app 恰好扫到 1 个非空 docstring 的 App 类。
    """
    mod = importlib.import_module(type(factory).__module__)
    candidates = [
        obj for obj in vars(mod).values()
        if inspect.isclass(obj)
        and issubclass(obj, Application)
        and obj not in _ABSTRACT_APP_BASES
    ]
    # leaf 选择:排除被其它候选类继承的(防 import 进来的中间基类如 ZApplication 干扰)
    leaves = [
        c for c in candidates
        if not any(issubclass(o, c) and o is not c for o in candidates)
    ]
    if len(leaves) != 1:
        return ''  # 0:factory 未 import App 类;>1:多 App 类歧义。契约测试硬卡 ==1
    return _doc_summary(leaves[0])
