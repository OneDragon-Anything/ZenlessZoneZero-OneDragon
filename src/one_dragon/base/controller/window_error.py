class WindowAmbiguousError(RuntimeError):
    """同一候选标题对应多个窗口，不能安全选择控制目标。"""
