"""自定义 operation 运行入口的底层能力:扫描 / op_id 解析 / args 校验。

本模块仅做纯反射(扫描 + ``inspect.signature``),不实例化任何 operation
(``ZOperation.__init__`` 会构造 ``OpenAndEnterGame`` 等有副作用的依赖)。
供 ``list_operations`` / ``describe_operation`` / ``run_operation`` 复用。

详见设计 spec §4.4(扫描根 operation/+hollow_zero/、三重过滤、op_id 拆分、纯反射)。
"""
import importlib
import inspect
import json
import types
import typing
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from one_dragon.utils import os_utils
from zzz_od.backend.schemas import (
    OperationInfo,
    OperationListResult,
    OperationParam,
)

if TYPE_CHECKING:
    from typing import Any

    from zzz_od.context.zzz_context import ZContext


# 扫描根(枚举 operation 承载包;application/ 全是 Application 子类会被过滤,不纳入)
_SCAN_ROOTS: list[str] = ['zzz_od.operation', 'zzz_od.hollow_zero']
# 显式排除的抽象/中间基类(HollowRunner 是具体可运行 op,不排除)
_ABSTRACT_BASES: set[str] = {
    'Operation', 'Application', 'ZOperation', 'ZApplication',
    'OneDragonApp', 'GroupApplication', 'DropResoniumBase',
}
# JSON 可序列化的标量/容器类型
_JSON_SCALAR_TYPES: tuple[type, ...] = (str, int, float, bool, list, dict, tuple)

# 扫描结果缓存(refresh=True 强制重扫)
_CACHE: OperationListResult | None = None


def _is_runnable_op(module_name: str, cls: object) -> bool:
    """三重过滤:issubclass(Operation) + 排除 Application/基类 + __module__ 守卫 + *Base 兜底。

    Args:
        module_name: 当前扫描的模块名(用于 ``__module__`` 守卫,排除 import 进来的类)。
        cls: 待判定的对象。

    Returns:
        是否为可运行的裸 operation(非 Application 子类、非抽象基类)。
    """
    from one_dragon.base.operation.application_base import Application
    from one_dragon.base.operation.operation import Operation

    if not inspect.isclass(cls) or not issubclass(cls, Operation):
        return False
    # __module__ 守卫:排除 from ... import SomeOp re-export 与基类
    if getattr(cls, '__module__', None) != module_name:
        return False
    # 口径是 issubclass(Operation),必须显式排除 Application 子类
    if issubclass(cls, Application):
        return False
    if cls.__name__ in _ABSTRACT_BASES:
        return False
    return not cls.__name__.endswith('Base')


def _iter_py_modules(pkg: str) -> Iterator[str]:
    """遍历扫描根包下所有 .py(跳过 ``__init__.py``),产出 dotted module path。

    Args:
        pkg: 扫描根包名(如 ``zzz_od.operation``)。
    """
    src_root = Path(os_utils.get_work_dir()) / 'src'
    pkg_dir = src_root.joinpath(*pkg.split('.'))
    if not pkg_dir.is_dir():
        return
    for f in pkg_dir.rglob('*.py'):
        if f.name == '__init__.py':
            continue
        rel = f.relative_to(pkg_dir).with_suffix('')
        module = f'{pkg}.{".".join(rel.parts)}'
        yield module


def _annotation_display(annotation: 'Any') -> str:
    """把类型注解转成可读字符串(``str`` → ``'str'``、``ChargePlanItem`` → ``'ChargePlanItem'``)。"""
    if annotation is inspect.Parameter.empty:
        return 'Any'
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation)


def _annotation_json_serializable(annotation: 'Any') -> bool:
    """判断类型注解是否 JSON 可序列化(标量/list/dict/Optional/Union;自定义类 → False)。

    无注解按可序列化处理(调用方经 JSON 传值,运行时再校验)。
    """
    if annotation is inspect.Parameter.empty:
        return True
    if isinstance(annotation, str):
        # 字符串形式注解:仅匹配已知标量/容器名
        return annotation.strip() in ('str', 'int', 'float', 'bool', 'list', 'dict', 'tuple')
    origin = typing.get_origin(annotation)
    if origin is None:
        # 简单类型:标量/容器 → True;其它自定义类(ChargePlanItem 等) → False
        if isinstance(annotation, type):
            return issubclass(annotation, _JSON_SCALAR_TYPES) or annotation is type(None)
        return False
    # 泛型:list[int]、dict[str, str]、tuple[...] → True
    if origin in (list, dict, tuple, set):
        return True
    # Optional/Union(PEP 604 ``X | Y`` 或 typing.Union):任一非 None 分支可序列化即可
    if origin is types.UnionType or origin is typing.Union:
        return any(_annotation_json_serializable(a) for a in typing.get_args(annotation))
    return False


def _annotation_coercible(annotation: 'Any') -> bool:
    """判断类型注解是否可从 dict 反序列化(``@dataclass`` + 有可调用 ``from_dict``)。

    这类参数 ``run_operation`` 接受 dict 值,实例化前用 ``from_dict`` 转成实例
    (如 ``ChargePlanItem``)。非 dataclass / 无 ``from_dict`` → False(仍需走 application)。
    """
    if not isinstance(annotation, type):
        return False
    if not hasattr(annotation, '__dataclass_fields__'):
        return False
    return callable(getattr(annotation, 'from_dict', None))


def coerce_dataclass_params(cls: type, args: dict) -> dict:
    """实例化前,把 ``@dataclass + from_dict`` 参数的 dict 值反序列化为实例。

    仅处理「注解是 dataclass 且有 ``from_dict``」且当前值为 dict 的参数;
    其余参数原样保留。返回新 dict(不就地改调用方传入的 args)。
    """
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return args
    coerced = dict(args)
    for p in sig.parameters.values():
        if p.name in ('self', 'ctx'):
            continue
        if p.name not in coerced:
            continue
        if _annotation_coercible(p.annotation) and isinstance(coerced[p.name], dict):
            coerced[p.name] = p.annotation.from_dict(coerced[p.name])
    return coerced


def _reflect_params(cls: type) -> list[OperationParam]:
    """纯反射 ``cls.__init__`` 参数 schema(不实例化),剔除 self/ctx 与 *args/**kwargs。"""
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return []
    params: list[OperationParam] = []
    for p in sig.parameters.values():
        if p.name in ('self', 'ctx'):
            continue
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue  # 跳过 *args / **kwargs
        required = p.default is inspect.Parameter.empty
        params.append(OperationParam(
            name=p.name,
            annotation=_annotation_display(p.annotation),
            required=required,
            default=None if required else repr(p.default),
            json_serializable=_annotation_json_serializable(p.annotation),
            coercible=_annotation_coercible(p.annotation),
        ))
    return params


def scan_operations(ctx: 'ZContext', refresh: bool = False) -> OperationListResult:
    """扫描 operation 承载包,返回可运行 operation 的反射信息。

    三重过滤(``__module__`` 守卫 + 显式抽象基类集 + ``*Base`` 兜底 + 排除 Application 子类);
    纯反射 ``__init__`` 参数(不实例化);单模块 import 失败容错(记 failures 不中断)。
    结果缓存,``refresh=True`` 强制重扫。

    Args:
        ctx: ZContext(扫描纯反射,占位;保持与其它 backend 接口一致)。
        refresh: 是否强制重新扫描(忽略缓存)。

    Returns:
        扫描结果(operations + failures)。
    """
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE

    operations: list[OperationInfo] = []
    failures: list[str] = []
    seen: set[str] = set()

    for pkg in _SCAN_ROOTS:
        for module in _iter_py_modules(pkg):
            try:
                mod = importlib.import_module(module)
            except Exception as e:  # noqa: BLE001 单模块失败不中断
                failures.append(f'{module}: {e}')
                continue
            for _name, attr in vars(mod).items():
                if not _is_runnable_op(module, attr):
                    continue
                cls: type = attr  # type: ignore[assignment]
                op_id = f'{module}.{cls.__name__}'
                if op_id in seen:
                    continue
                seen.add(op_id)
                operations.append(OperationInfo(
                    op_id=op_id,
                    class_name=cls.__name__,
                    module=module,
                    params=_reflect_params(cls),
                ))

    operations.sort(key=lambda o: o.op_id)
    result = OperationListResult(operations=operations, failures=failures)
    _CACHE = result
    return result


def resolve_op_class(op_id: str) -> type:
    """按 ``<dotted module path>.<ClassName>`` 解析出 operation 类。

    拆分(最后一个 ``.``)→ ``import_module`` + ``getattr`` → ``__module__`` 守卫
    (防 re-export)→ ``issubclass(cls, Operation)``。

    Args:
        op_id: 定位标识,如 ``zzz_od.operation.map_transport.MapTransport``。

    Returns:
        解析出的 Operation 子类。

    Raises:
        ValueError: op_id 格式非法 / 模块无该类 / ``__module__`` 不匹配(re-export) /
            非 Operation 子类。
    """
    from one_dragon.base.operation.operation import Operation

    idx = op_id.rfind('.')
    if idx < 0:
        raise ValueError(f'op_id 格式非法(应含 module.ClassName): {op_id}')
    module_name = op_id[:idx]
    class_name = op_id[idx + 1:]

    try:
        mod = importlib.import_module(module_name)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f'无法导入模块 {module_name}: {e}') from e

    cls = getattr(mod, class_name, None)
    if cls is None:
        raise ValueError(f'模块 {module_name} 无属性 {class_name}')
    if not inspect.isclass(cls):
        raise ValueError(f'{op_id} 不是类')
    if getattr(cls, '__module__', None) != module_name:
        raise ValueError(
            f'{op_id} 不指向定义模块(定义于 {getattr(cls, "__module__", "?")}),疑似 re-export'
        )
    if not issubclass(cls, Operation):
        raise ValueError(f'{op_id} 不是 Operation 子类')
    return cls


def validate_args(cls: type, args: dict) -> str | None:
    """校验 ``cls(ctx, **args)`` 的参数:必填齐全 + 无复杂数据类参数 + 值可 JSON 序列化。

    Args:
        cls: 已解析的 operation 类。
        args: 调用方传入的参数字典(不含 ctx)。

    Returns:
        错误描述(校验失败)或 None(通过)。
    """
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError) as e:
        return f'无法反射 __init__ 签名: {e}'

    for p in sig.parameters.values():
        if p.name in ('self', 'ctx'):
            continue
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        required = p.default is inspect.Parameter.empty
        if required and p.name not in args:
            return f'缺少必填参数: {p.name}'
        if p.name in args and not _annotation_json_serializable(p.annotation) and not _annotation_coercible(p.annotation):
            return f'参数 {p.name} 为不支持的数据类型({_annotation_display(p.annotation)}),请走 application'

    # 校验提供的值本身可 JSON 序列化(防御:调用方传入非 JSON 原生对象)
    for name, value in args.items():
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            return f'参数 {name} 的值不可 JSON 序列化'

    return None


def describe_operation(ctx: 'ZContext', op_id: str) -> dict:
    """描述单个 operation 的反射参数 schema(纯反射,不实例化)。

    Args:
        ctx: ZContext(占位)。
        op_id: 定位标识。

    Returns:
        含 op_id/class_name/module/params(各 param 标 json_serializable)/debuggable 的字典。
    """
    cls = resolve_op_class(op_id)
    params = _reflect_params(cls)
    # 所有必填参数 json_serializable 或 coercible(可从 dict 反序列化) → debuggable=True
    debuggable = all(
        p.json_serializable or p.coercible for p in params if p.required
    )
    return {
        'op_id': op_id,
        'class_name': cls.__name__,
        'module': cls.__module__,
        'params': [
            {
                'name': p.name,
                'annotation': p.annotation,
                'required': p.required,
                'default': p.default,
                'json_serializable': p.json_serializable,
                'coercible': p.coercible,
            }
            for p in params
        ],
        'debuggable': debuggable,
    }
