"""backend 层共享的 docstring 摘要工具。

op 侧(``operation_registry.describe_operation``)与 app 侧(``app_registry._app_description``)
都需要从 class docstring 取「用途摘要」并去掉 ``:param``/``:return`` 等 Sphinx 标记块。
本模块是这两处的单一源,避免口径漂移。
"""


def _doc_summary(cls: type) -> str:
    """取 class 或其 ``__init__`` 的 docstring 用途摘要:去掉 ``:param``/``:return`` 等 Sphinx 标记块。

    operation / application 的 ``__init__`` docstring 常含 ``:param ctx: 上下文`` 这类 Sphinx 标记,
    原样透传给 MCP 消费者是噪音;只留标记块之前的用途描述。

    Args:
        cls: 待取摘要的类。

    Returns:
        摘要文本;无 docstring 时返空串。
    """
    doc = cls.__doc__ or cls.__init__.__doc__ or ''
    if not doc:
        return ''
    for marker in (':param', ':return', ':arg', ':returns'):
        idx = doc.find(marker)
        if idx >= 0:
            doc = doc[:idx]
    return doc.strip()
