from __future__ import annotations


def compose_gamepad_key(modifier: str, button: str) -> str:
    """将修饰键值和按钮值组合为存储字符串。

    Args:
        modifier: 修饰键值, '' 表示无修饰
        button: 按钮值, 如 'xbox_a'

    Returns:
        如 'xbox_lb+xbox_a' 或 'xbox_a'
    """
    if modifier:
        return f'{modifier}+{button}'
    return button


def decompose_gamepad_key(key: str) -> tuple[str, str]:
    """将存储字符串分解为 (modifier, button)。

    Args:
        key: 如 'xbox_lb+xbox_a' 或 'xbox_a' 或 ''

    Returns:
        (modifier_value, button_value)
    """
    if not key:
        return '', ''
    parts = key.split('+')
    if len(parts) == 2:
        return parts[0], parts[1]
    return '', parts[0]
