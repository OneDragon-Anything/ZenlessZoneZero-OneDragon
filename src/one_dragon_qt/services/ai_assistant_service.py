"""AI 助手服务层，封装 OpenAI 兼容 API 的调用逻辑"""

import json
import threading
from collections.abc import Callable

import requests

from one_dragon.utils.log_utils import log


# 绝区零一条龙项目知识的 system prompt 片段
_SYSTEM_PROMPT: str = """\
你是"绝区零一条龙"工具的 AI 助手。这个工具是一个面向 Windows 的绝区零自动化工具，\
使用 Python 3.11 + PySide6 开发，主要功能包括：

- **一条龙运行**：自动执行每日/每周任务（录像店营业、咖啡店、邮件、体力刷本等）
- **体力刷本**：自动消耗游戏内电量（体力）刷副本，包括实战模拟室（20电量/卡）、\
专业挑战室（40电量）、区域巡防（60电量）、恶名狩猎·深度追猎（60电量）
- **迷失之地 / 枯萎之都**：自动化刷取这些特殊副本
- **格挡助手**：自动检测闪光并格挡
- **式舆防卫战 / 锄大地**：自动化战斗
- **刮刮卡 / 卦象集录**：自动化小游戏

用户可能询问如何配置这些功能、解释游戏概念、或寻求使用建议。\
请用简洁的中文回答，必要时给出具体的配置建议。\
如果你不确定某个问题的答案，请坦诚说明。\
"""


class AiAssistantService:
    """AI 助手服务，管理与 OpenAI 兼容 API 的交互"""

    def __init__(self) -> None:
        self._history: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def clear_history(self) -> None:
        """清除对话历史"""
        with self._lock:
            self._history.clear()

    def chat_stream(
        self,
        user_message: str,
        api_key: str,
        base_url: str,
        model: str,
        on_chunk: Callable[[str], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
        context: str = '',
    ) -> None:
        """
        发送消息并以流式方式接收回复，在后台线程中执行。

        :param user_message: 用户消息
        :param api_key: API Key
        :param base_url: API Base URL（不含 /chat/completions）
        :param model: 模型名称
        :param on_chunk: 每收到一个 token 片段时回调
        :param on_done: 完成时回调，传入完整回复文本
        :param on_error: 出错时回调，传入错误信息
        :param context: 运行时上下文信息（日志、配置等），注入到 system prompt
        """
        thread = threading.Thread(
            target=self._do_chat_stream,
            args=(user_message, api_key, base_url, model,
                  on_chunk, on_done, on_error, context),
            daemon=True,
        )
        thread.start()

    def _do_chat_stream(
        self,
        user_message: str,
        api_key: str,
        base_url: str,
        model: str,
        on_chunk: Callable[[str], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
        context: str,
    ) -> None:
        """流式调用 OpenAI 兼容 API"""
        # 拼接 system prompt + 本地上下文
        system_content = _SYSTEM_PROMPT
        if context:
            system_content += (
                '\n\n--- 以下为用户当前运行环境信息 ---\n'
                f'{context}'
            )

        with self._lock:
            self._history.append(
                {'role': 'user', 'content': user_message}
            )
            messages = [
                {'role': 'system', 'content': system_content}
            ]
            messages.extend(self._history)

        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
        payload = {
            'model': model,
            'messages': messages,
            'stream': True,
        }

        full_reply = ''
        try:
            resp = requests.post(
                url, headers=headers, json=payload,
                timeout=60, stream=True,
            )
            resp.raise_for_status()
            resp.encoding = 'utf-8'

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if not line.startswith('data: '):
                    continue
                data = line[6:]
                if data.strip() == '[DONE]':
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk.get('choices', [{}])[0].get('delta', {})
                    content = delta.get('content', '')
                    if content:
                        full_reply += content
                        on_chunk(content)
                except json.JSONDecodeError:
                    continue

            with self._lock:
                self._history.append(
                    {'role': 'assistant', 'content': full_reply}
                )
            on_done(full_reply)

        except requests.exceptions.Timeout:
            on_error('请求超时，请检查网络连接')
        except requests.exceptions.ConnectionError:
            on_error(f'无法连接到 {base_url}，请检查 Base URL')
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 401:
                on_error('API Key 无效，请检查设置')
            elif status == 402:
                on_error('API 余额不足')
            elif status == 429:
                on_error('请求过于频繁，请稍后重试')
            else:
                on_error(f'API 返回错误 ({status}): {e}')
        except Exception as e:
            log.error(f'AI 助手调用失败: {e}')
            on_error(f'调用失败: {e}')
