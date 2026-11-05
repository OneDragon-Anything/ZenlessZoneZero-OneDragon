"""控制台编码相关工具。"""

import sys


def ensure_utf8_stdio() -> None:
    """把标准输出 / 标准错误切成 UTF-8，编码失败时用替换字符而不是抛异常。

    启动器在非中文的 Windows 上运行（CP1252 / CP932 / CP949 等）时，控制台编码
    表示不了中文。启动器打印中文进度、错误提示会抛 UnicodeEncodeError 直接退出，
    看起来就是"启动器报错"。这里统一按 UTF-8 输出，控制台显示不了时替换成问号，
    不会中断流程。

    已经被重定向到不支持 reconfigure 的对象（例如测试里的 StringIO）时直接跳过。
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue

        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is None:
            continue

        try:
            reconfigure(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            continue
