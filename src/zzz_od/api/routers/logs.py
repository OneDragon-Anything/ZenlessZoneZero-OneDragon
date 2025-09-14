"""
通用日志管理API

提供日志查询、清理等功能，配合WebSocket实时日志使用。
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from zzz_od.api.deps import get_ctx
from zzz_od.api.security import get_api_key_dependency
from one_dragon.utils.log_utils import log


router = APIRouter(
    prefix="/api/v1/logs",
    tags=["日志管理 Logs Management"],
    dependencies=[Depends(get_api_key_dependency())],
)


class LogEntry(BaseModel):
    """日志条目"""
    timestamp: str
    level: str
    message: str
    logger: Optional[str] = None
    module: Optional[str] = None


class LogsResponse(BaseModel):
    """日志响应"""
    logs: List[LogEntry]
    total_count: int
    page: int
    page_size: int
    has_more: bool


class LogsOperationResponse(BaseModel):
    """日志操作响应"""
    success: bool
    message: str
    details: Dict[str, Any] = {}


@router.get("", response_model=LogsResponse, summary="获取历史日志")
def get_logs(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(100, ge=1, le=1000, description="每页条数，最大1000"),
    level: Optional[str] = Query(None, description="日志级别过滤 (DEBUG/INFO/WARNING/ERROR)"),
    start_time: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO格式)"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    ctx = Depends(get_ctx)
):
    """
    获取历史日志记录

    ## 功能描述
    分页获取历史日志记录，支持按级别、时间范围和关键词过滤。

    ## 查询参数
    - **page**: 页码，从1开始
    - **page_size**: 每页条数，最大1000
    - **level**: 日志级别过滤 (DEBUG/INFO/WARNING/ERROR)
    - **start_time**: 开始时间，ISO格式 (如: 2024-01-01T00:00:00)
    - **end_time**: 结束时间，ISO格式
    - **search**: 搜索关键词，在日志消息中查找

    ## 返回数据
    - **logs**: 日志条目列表
    - **total_count**: 总条数
    - **page**: 当前页码
    - **page_size**: 每页条数
    - **has_more**: 是否还有更多数据

    ## 使用示例
    ```python
    import requests

    # 获取最新100条日志
    response = requests.get("http://localhost:8000/api/v1/logs")
    logs = response.json()

    # 获取错误级别的日志
    response = requests.get("http://localhost:8000/api/v1/logs?level=ERROR")

    # 搜索包含"战斗"的日志
    response = requests.get("http://localhost:8000/api/v1/logs?search=战斗")
    ```
    """
    try:
        # 获取日志文件路径
        log_entries = []

        # 尝试从不同可能的日志源获取日志
        log_sources = _get_log_sources()

        for source in log_sources:
            entries = _read_log_file(
                source,
                level_filter=level,
                start_time=start_time,
                end_time=end_time,
                search_keyword=search
            )
            log_entries.extend(entries)

        # 按时间戳排序（最新的在前）
        log_entries.sort(key=lambda x: x.timestamp, reverse=True)

        # 分页处理
        total_count = len(log_entries)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_entries = log_entries[start_idx:end_idx]

        has_more = end_idx < total_count

        return LogsResponse(
            logs=page_entries,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_more=has_more
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "LOGS_READ_FAILED",
                    "message": f"读取日志失败: {str(e)}"
                }
            }
        )


@router.delete("", response_model=LogsOperationResponse, summary="清空日志")
def clear_logs(
    confirm: bool = Query(False, description="确认清空日志"),
    days: Optional[int] = Query(None, ge=1, description="只清空N天前的日志"),
    ctx = Depends(get_ctx)
):
    """
    清空历史日志

    ## 功能描述
    清空或清理历史日志文件。支持全部清空或按时间清理。

    ## 查询参数
    - **confirm**: 必须设为true才能执行清空操作
    - **days**: 可选，只清空N天前的日志，不设置则清空全部

    ## 返回数据
    - **success**: 操作是否成功
    - **message**: 操作结果消息
    - **details**: 包含清理的文件数量等信息

    ## 安全提示
    - 此操作不可逆，请谨慎使用
    - 建议在清空前先备份重要日志

    ## 使用示例
    ```python
    import requests

    # 清空全部日志（需要确认）
    response = requests.delete("http://localhost:8000/api/v1/logs?confirm=true")

    # 只清空7天前的日志
    response = requests.delete("http://localhost:8000/api/v1/logs?confirm=true&days=7")

    result = response.json()
    print(f"清理结果: {result['message']}")
    ```
    """
    try:
        if not confirm:
            return LogsOperationResponse(
                success=False,
                message="需要设置confirm=true参数确认清空操作",
                details={"error_code": "CONFIRMATION_REQUIRED"}
            )

        # 获取日志文件路径
        log_sources = _get_log_sources()
        cleared_files = 0
        cleared_size = 0

        cutoff_time = None
        if days:
            cutoff_time = datetime.now() - timedelta(days=days)

        for log_file in log_sources:
            if os.path.exists(log_file):
                try:
                    # 获取文件大小
                    file_size = os.path.getsize(log_file)

                    if cutoff_time:
                        # 按时间清理：读取文件，只保留最近的日志
                        _clean_log_file_by_time(log_file, cutoff_time)
                    else:
                        # 全部清空：直接删除或清空文件
                        with open(log_file, 'w', encoding='utf-8') as f:
                            f.write('')  # 清空文件内容

                    cleared_files += 1
                    cleared_size += file_size

                except Exception as e:
                    log.warning(f"清理日志文件失败 {log_file}: {e}")

        # 格式化清理大小
        size_mb = cleared_size / (1024 * 1024)

        if days:
            message = f"已清理 {days} 天前的日志，处理了 {cleared_files} 个文件，释放 {size_mb:.2f} MB"
        else:
            message = f"已清空全部日志，处理了 {cleared_files} 个文件，释放 {size_mb:.2f} MB"

        return LogsOperationResponse(
            success=True,
            message=message,
            details={
                "cleared_files": cleared_files,
                "cleared_size_mb": round(size_mb, 2),
                "days_filter": days
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "LOGS_CLEAR_FAILED",
                    "message": f"清空日志失败: {str(e)}"
                }
            }
        )


def _get_log_sources() -> List[str]:
    """获取可能的日志文件路径"""
    log_files = []

    # 常见的日志文件位置
    possible_paths = [
        "logs/app.log",
        "logs/one_dragon.log",
        "logs/zzz_od.log",
        "app.log",
        "one_dragon.log",
        "zzz_od.log"
    ]

    for path in possible_paths:
        if os.path.exists(path):
            log_files.append(path)

    # 如果没找到，尝试从logging配置获取
    if not log_files:
        try:
            # 获取当前logger的handlers
            logger = logging.getLogger()
            for handler in logger.handlers:
                if hasattr(handler, 'baseFilename'):
                    log_files.append(handler.baseFilename)
        except Exception:
            pass

    return log_files


def _read_log_file(
    file_path: str,
    level_filter: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    search_keyword: Optional[str] = None
) -> List[LogEntry]:
    """读取日志文件并应用过滤条件"""
    entries = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # 简单的日志解析（可根据实际日志格式调整）
                entry = _parse_log_line(line)
                if not entry:
                    continue

                # 应用过滤条件
                if level_filter and entry.level != level_filter.upper():
                    continue

                if start_time:
                    try:
                        entry_time = datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
                        filter_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        if entry_time < filter_time:
                            continue
                    except Exception:
                        pass

                if end_time:
                    try:
                        entry_time = datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
                        filter_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                        if entry_time > filter_time:
                            continue
                    except Exception:
                        pass

                if search_keyword and search_keyword.lower() not in entry.message.lower():
                    continue

                entries.append(entry)

    except Exception as e:
        log.warning(f"读取日志文件失败 {file_path}: {e}")

    return entries


def _parse_log_line(line: str) -> Optional[LogEntry]:
    """解析日志行，返回LogEntry对象"""
    try:
        # 这里需要根据实际的日志格式进行解析
        # 假设格式类似: "2024-01-01 12:00:00 [INFO] module: message"

        # 简单的解析逻辑（可根据实际情况调整）
        parts = line.split(' ', 3)
        if len(parts) >= 4:
            date_part = parts[0]
            time_part = parts[1]
            level_part = parts[2].strip('[]')
            message_part = parts[3]

            timestamp = f"{date_part}T{time_part}"

            return LogEntry(
                timestamp=timestamp,
                level=level_part,
                message=message_part,
                logger=None,
                module=None
            )
        else:
            # 如果解析失败，创建一个简单的条目
            return LogEntry(
                timestamp=datetime.now().isoformat(),
                level="INFO",
                message=line,
                logger=None,
                module=None
            )

    except Exception:
        return None


def _clean_log_file_by_time(file_path: str, cutoff_time: datetime) -> None:
    """按时间清理日志文件，只保留cutoff_time之后的日志"""
    try:
        kept_lines = []

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                entry = _parse_log_line(line.strip())
                if entry:
                    try:
                        entry_time = datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
                        if entry_time >= cutoff_time:
                            kept_lines.append(line)
                    except Exception:
                        # 如果解析时间失败，保留这行
                        kept_lines.append(line)

        # 重写文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(kept_lines)

    except Exception as e:
        log.warning(f"按时间清理日志文件失败 {file_path}: {e}")