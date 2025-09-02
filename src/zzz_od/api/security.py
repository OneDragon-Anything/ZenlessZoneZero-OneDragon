from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException, status


def get_api_key_dependency():
    """
    返回一个依赖函数：当设置环境变量 OD_API_KEY 时，要求请求头携带 `X-Api-Key` 且匹配；
    未设置时，不进行鉴权。
    用法：dependencies=[Depends(get_api_key_dependency())]
    """

    expected = os.getenv("OD_API_KEY")
    if not expected:
        async def _noop(x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key")) -> None:  # noqa: ARG001
            return None

        return _noop

    async def _require(x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key")) -> None:
        if not x_api_key or x_api_key != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")

    return _require






