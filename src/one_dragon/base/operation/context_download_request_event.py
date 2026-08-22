from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(slots=True)
class ContextDownloadRequestEvent:
    """后端请求前端确认资源下载的事件体。

    后端 dispatch 后调用 wait() 等待前端应答；
    前端展示确认对话框后调用 respond() 回传结果。
    无前端监听或等待超时时 由调用方自行决定默认行为。
    """

    EVENT_ID: ClassVar[str] = 'context_download_request'

    title: str
    note: str = ''
    _response_event: threading.Event = field(default_factory=threading.Event)
    _confirmed: bool = False
    _remember: bool = False

    def respond(self, confirmed: bool, remember: bool = False) -> None:
        """前端回传用户的选择。

        :param confirmed: 是否确认下载
        :param remember: 是否记住选择 之后不再询问
        """
        self._confirmed = confirmed
        self._remember = remember
        self._response_event.set()

    def wait(self, timeout: float | None = None) -> bool:
        """等待前端应答。

        :param timeout: 超时时间(秒)
        :return: 是否在超时前收到应答
        """
        return self._response_event.wait(timeout=timeout)

    @property
    def confirmed(self) -> bool:
        """用户是否确认下载。"""
        return self._confirmed

    @property
    def remember(self) -> bool:
        """用户是否勾选了记住选择。"""
        return self._remember
