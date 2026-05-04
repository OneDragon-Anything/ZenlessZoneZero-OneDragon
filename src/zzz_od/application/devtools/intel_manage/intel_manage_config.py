# -*- coding: utf-8 -*-
"""
信息管理系统配置类
统一管理所有硬编码配置，便于维护和扩展
"""

from typing import List


class IntelManageConfig:
    """信息管理系统配置类"""

    # ==================== 目录配置 ====================
    AGENT_DIR_NAME: str = 'agent'
    DRIVE_DISK_DIR_NAME: str = 'drive_disk'
    ENGINE_WEAPON_DIR_NAME: str = 'engine_weapon'

    # ==================== 文件配置 ====================
    MERGED_FILE_NAME: str = '_od_merged.yml'
    YAML_INDENT: int = 2

    # ==================== 权重计算配置 ====================
    MIN_WEIGHT: float = 0.1
    MAX_WEIGHT: float = 1.0
    WEIGHT_DECREMENT: float = 0.05

    # ==================== 表格配置 ====================
    TABLE_COL_NAMES: List[str] = ['技能/属性', '权重值', '优先级', '操作']
    TABLE_COL_WIDTHS: List[int] = [180, 80, 80, 100]

    # ==================== UI 文本配置 ====================
    BTN_MERGE_TEXT: str = '更新合并配置文件'
    BTN_SAVE_TEXT: str = '保存'
    BTN_DELETE_TEXT: str = '删除'
    BTN_ADD_TEXT: str = '添加'

    # ==================== 对话框消息配置 ====================
    MSG_WARN_SELECT_ROW: str = '请先选择要删除的行'
    MSG_WARN_SELECT_AGENT: str = '请先选择代理人'
    MSG_INFO_SAVE_SUCCESS: str = '保存成功'
    MSG_INFO_MERGE_SUCCESS: str = '合并配置更新成功'
    MSG_ERROR_SAVE_FAILED: str = '保存失败'
    MSG_ERROR_MERGE_FAILED: str = '合并配置更新失败'

    # ==================== 日志消息模板 ====================
    LOG_LOADED_AGENTS: str = 'Loaded {} agents | Cache: {} hits, {} misses, {}% hit rate'
    LOG_LOADED_DRIVE_DISK: str = 'Loaded {} drive disks'
    LOG_LOADED_ENGINE_WEAPON: str = 'Loaded {} engine weapons'
    LOG_SAVED_AGENT: str = 'Saved agent data to: {}'
    LOG_ERROR_SAVE_AGENT: str = 'Failed to save agent data: {}'

    # ==================== 缓存配置 ====================
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 300

    # ==================== 并发配置 ====================
    MAX_CONCURRENT_WRITES: int = 5
