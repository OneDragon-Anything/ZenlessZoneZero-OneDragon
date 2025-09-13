"""
战斗助手API数据模型定义

包含配置模型、状态模型、响应模型和异常类定义
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# 异常类定义
# ============================================================================

class BattleAssistantError(Exception):
    """战斗助手基础异常"""
    def __init__(self, message: str, code: str = "BATTLE_ASSISTANT_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class ConfigurationError(BattleAssistantError):
    """配置错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIGURATION_ERROR", details)


class TaskExecutionError(BattleAssistantError):
    """任务执行错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "TASK_EXECUTION_ERROR", details)


class FileOperationError(BattleAssistantError):
    """文件操作错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "FILE_OPERATION_ERROR", details)


class GamepadError(BattleAssistantError):
    """手柄相关错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "GAMEPAD_ERROR", details)


class ValidationError(BattleAssistantError):
    """验证错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", details)


class TaskAlreadyRunningError(BattleAssistantError):
    """任务已在运行错误"""
    def __init__(self, message: str = "任务已在运行", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "TASK_ALREADY_RUNNING", details)


class ConfigNotFoundError(BattleAssistantError):
    """配置未找到错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIG_NOT_FOUND", details)


class TemplateNotFoundError(BattleAssistantError):
    """模板未找到错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "TEMPLATE_NOT_FOUND", details)


class PermissionError(BattleAssistantError):
    """权限错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "PERMISSION_ERROR", details)


# ============================================================================
# 枚举定义
# ============================================================================

class TaskStatusEnum(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BattleEventType(str, Enum):
    """战斗事件类型"""
    BATTLE_STATE_CHANGED = "battle_state_changed"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    CONFIG_UPDATED = "config_updated"
    ERROR_OCCURRED = "error_occurred"


# ============================================================================
# 配置模型
# ============================================================================

class DodgeAssistantConfig(BaseModel):
    """闪避助手配置"""
    enabled: bool = True
    dodge_method: str = Field(default="闪避", description="闪避方式")
    sensitivity: float = Field(default=0.8, ge=0.0, le=1.0, description="敏感度")
    reaction_time: float = Field(default=0.1, ge=0.0, le=1.0, description="反应时间(秒)")


class AutoBattleConfig(BaseModel):
    """自动战斗配置"""
    config_name: str = Field(default="全配队通用", description="配置名称")
    enabled: bool = True
    use_gpu: bool = Field(default=True, description="是否使用GPU")
    screenshot_interval: float = Field(default=0.02, ge=0.01, le=1.0, description="截图间隔(秒)")
    gamepad_type: str = Field(default="none", description="手柄类型")


class OperationDebugConfig(BaseModel):
    """指令调试配置"""
    template_name: str = Field(default="安比-3A特殊攻击", description="模板名称")
    repeat_mode: bool = Field(default=True, description="重复模式")
    gamepad_type: str = Field(default="none", description="手柄类型")


class BattleAssistantSettings(BaseModel):
    """战斗助手设置"""
    use_gpu: bool = Field(default=True, description="是否使用GPU")
    screenshot_interval: float = Field(default=0.02, ge=0.01, le=1.0, description="截图间隔(秒)")
    gamepad_type: str = Field(default="none", description="手柄类型")


# ============================================================================
# 状态模型
# ============================================================================

class BattleState(BaseModel):
    """战斗状态"""
    is_in_battle: bool = Field(default=False, description="是否在战斗中")
    current_action: Optional[str] = Field(default=None, description="当前动作")
    enemies_detected: int = Field(default=0, ge=0, description="检测到的敌人数量")
    last_update: datetime = Field(default_factory=datetime.now, description="最后更新时间")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="性能指标")


class TaskState(BaseModel):
    """任务状态"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatusEnum = Field(default=TaskStatusEnum.PENDING, description="任务状态")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="任务进度")
    message: str = Field(default="", description="状态消息")
    started_at: datetime = Field(default_factory=datetime.now, description="开始时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


# ============================================================================
# 响应模型
# ============================================================================

class ConfigInfo(BaseModel):
    """配置信息"""
    name: str = Field(..., description="配置名称")
    description: Optional[str] = Field(default=None, description="配置描述")
    last_modified: datetime = Field(..., description="最后修改时间")
    file_size: int = Field(..., ge=0, description="文件大小(字节)")


class ConfigListResponse(BaseModel):
    """配置列表响应"""
    configs: List[ConfigInfo] = Field(default_factory=list, description="配置列表")
    current_config: Optional[str] = Field(default=None, description="当前配置名称")


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str = Field(..., description="任务ID")
    message: str = Field(default="任务已启动", description="响应消息")


class GamepadTypeInfo(BaseModel):
    """手柄类型信息"""
    value: str = Field(..., description="手柄类型值")
    display_name: str = Field(..., description="显示名称")
    description: str = Field(..., description="描述")
    supported: bool = Field(default=True, description="是否支持")


class GamepadTypesResponse(BaseModel):
    """手柄类型列表响应"""
    gamepad_types: List[GamepadTypeInfo] = Field(default_factory=list, description="手柄类型列表")


class TemplateInfo(BaseModel):
    """模板信息"""
    name: str = Field(..., description="模板名称")
    path: str = Field(..., description="模板路径")
    description: Optional[str] = Field(default=None, description="模板描述")
    last_modified: datetime = Field(..., description="最后修改时间")
    file_size: int = Field(..., ge=0, description="文件大小(字节)")


class TemplateListResponse(BaseModel):
    """模板列表响应"""
    templates: List[TemplateInfo] = Field(default_factory=list, description="模板列表")


# ============================================================================
# WebSocket消息模型
# ============================================================================

class WebSocketMessage(BaseModel):
    """WebSocket消息格式"""
    type: str = Field(..., description="消息类型")
    data: Dict[str, Any] = Field(default_factory=dict, description="消息数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    task_id: Optional[str] = Field(default=None, description="关联任务ID")


# ============================================================================
# 请求模型
# ============================================================================

class DodgeAssistantConfigUpdate(BaseModel):
    """闪避助手配置更新请求"""
    enabled: Optional[bool] = None
    dodge_method: Optional[str] = None
    sensitivity: Optional[float] = Field(None, ge=0.0, le=1.0)
    reaction_time: Optional[float] = Field(None, ge=0.0, le=1.0)


class AutoBattleConfigUpdate(BaseModel):
    """自动战斗配置更新请求"""
    config_name: Optional[str] = None
    enabled: Optional[bool] = None
    use_gpu: Optional[bool] = None
    screenshot_interval: Optional[float] = Field(None, ge=0.01, le=1.0)
    gamepad_type: Optional[str] = None


class OperationDebugConfigUpdate(BaseModel):
    """指令调试配置更新请求"""
    template_name: Optional[str] = None
    repeat_mode: Optional[bool] = None
    gamepad_type: Optional[str] = None


class BattleAssistantSettingsUpdate(BaseModel):
    """战斗助手设置更新请求"""
    use_gpu: Optional[bool] = None
    screenshot_interval: Optional[float] = Field(None, ge=0.01, le=1.0)
    gamepad_type: Optional[str] = None


class TaskRunRequest(BaseModel):
    """任务运行请求"""
    config_name: Optional[str] = Field(default=None, description="配置名称")
    debug_mode: bool = Field(default=False, description="调试模式")
    repeat_mode: bool = Field(default=False, description="重复模式")


# ============================================================================
# 错误响应模型
# ============================================================================

class ErrorDetail(BaseModel):
    """错误详情"""
    code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: Optional[Dict[str, Any]] = Field(default=None, description="错误详细信息")


class ErrorResponse(BaseModel):
    """标准错误响应"""
    error: ErrorDetail = Field(..., description="错误信息")


class SuccessResponse(BaseModel):
    """标准成功响应"""
    message: str = Field(..., description="成功消息")
    data: Optional[Dict[str, Any]] = Field(default=None, description="响应数据")