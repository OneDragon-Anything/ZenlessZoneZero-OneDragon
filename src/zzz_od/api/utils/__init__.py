"""
API工具模块
"""
from .error_helpers import (
    handle_battle_assistant_errors,
    raise_config_error,
    raise_task_error,
    raise_file_error,
    raise_validation_error,
    raise_gamepad_error,
    raise_task_running_error,
    raise_config_not_found_error,
    raise_template_not_found_error,
    check_task_not_running,
    validate_config_name,
    validate_numeric_range,
    error_context,
    ErrorContext
)
from .validation import (
    ConfigValidator,
    FileOperationHelper,
    validate_battle_assistant_config,
    create_error_context
)

__all__ = [
    # Error helpers
    "handle_battle_assistant_errors",
    "raise_config_error",
    "raise_task_error",
    "raise_file_error",
    "raise_validation_error",
    "raise_gamepad_error",
    "raise_task_running_error",
    "raise_config_not_found_error",
    "raise_template_not_found_error",
    "check_task_not_running",
    "validate_config_name",
    "validate_numeric_range",
    "error_context",
    "ErrorContext",

    # Validation
    "ConfigValidator",
    "FileOperationHelper",
    "validate_battle_assistant_config",
    "create_error_context"
]