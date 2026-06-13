import os
import platform
from collections.abc import Sequence
from enum import Enum
from typing import Any

import onnxruntime

from onnxocr.logger import get_logger

log = get_logger("inference_engine")


Provider = str | tuple[str, dict[str, Any]]


InferenceSession = onnxruntime.InferenceSession
SessionOptions = onnxruntime.SessionOptions
GraphOptimizationLevel = onnxruntime.GraphOptimizationLevel


class EP(Enum):
    CPU = "CPUExecutionProvider"
    CUDA = "CUDAExecutionProvider"
    DIRECTML = "DmlExecutionProvider"
    CANN = "CANNExecutionProvider"


DEFAULT_CPU_EP_CFG: dict[str, Any] = {}
DEFAULT_CUDA_EP_CFG: dict[str, Any] = {
    "cudnn_conv_algo_search": "DEFAULT",
    "device_id": 0,
}
DEFAULT_DML_EP_CFG: dict[str, Any] = {}
DEFAULT_CANN_EP_CFG: dict[str, Any] = {}


def get_available_providers() -> list[str]:
    return onnxruntime.get_available_providers()


def get_device() -> str:
    return onnxruntime.get_device()


def is_session(value: Any) -> bool:
    return isinstance(value, InferenceSession)


def build_providers(
    use_gpu: bool = False,
    gpu_id: int = 0,
    providers: Sequence[Provider] | None = None,
) -> list[Provider]:
    if providers is not None:
        return list(providers)

    if use_gpu:
        available = get_available_providers()
        if EP.CUDA.value in available:
            cuda_cfg = dict(DEFAULT_CUDA_EP_CFG)
            cuda_cfg["device_id"] = gpu_id
            return [(EP.CUDA.value, cuda_cfg), EP.CPU.value]
        elif EP.DIRECTML.value in available:
            return [EP.DIRECTML.value, EP.CPU.value]
        elif EP.CANN.value in available:
            return [EP.CANN.value, EP.CPU.value]
    return [EP.CPU.value]


def build_providers_from_engine_cfg(engine_cfg: Any) -> list[Provider]:
    """Build ONNXRuntime execution providers from the common engine_cfg shape.

    RapidTable, RapidLayout and RapidDoc use slightly different vendored copies of
    an ``engine_cfg`` object. This function is the single compatibility point so
    downstream vendors only need to customize provider behavior here.
    """

    available = get_available_providers()
    providers: list[Provider] = [(EP.CPU.value, _cfg_dict(engine_cfg, "cpu_ep_cfg", DEFAULT_CPU_EP_CFG))]

    if _cfg_bool(engine_cfg, "use_cuda") and EP.CUDA.value in available:
        providers.insert(0, (EP.CUDA.value, _cfg_dict(engine_cfg, "cuda_ep_cfg", DEFAULT_CUDA_EP_CFG)))

    if _cfg_bool(engine_cfg, "use_dml") and _is_windows() and EP.DIRECTML.value in available:
        providers.insert(0, (EP.DIRECTML.value, _cfg_dict(engine_cfg, "dm_ep_cfg", DEFAULT_DML_EP_CFG)))

    if _cfg_bool(engine_cfg, "use_cann") and EP.CANN.value in available:
        providers.insert(0, (EP.CANN.value, _cfg_dict(engine_cfg, "cann_ep_cfg", DEFAULT_CANN_EP_CFG)))

    return providers


class ProviderConfig:
    """Compatibility wrapper used by vendored RapidAI modules."""

    def __init__(self, engine_cfg: Any):
        self.engine_cfg = engine_cfg

    def get_ep_list(self) -> list[Provider]:
        return build_providers_from_engine_cfg(self.engine_cfg)

    def verify_providers(self, session_providers: Sequence[str]) -> None:
        if not session_providers:
            raise ValueError("Session providers is empty.")


def _cfg_bool(engine_cfg: Any, key: str, default: bool = False) -> bool:
    value = _cfg_get(engine_cfg, key, default)
    return bool(value)


def _cfg_dict(engine_cfg: Any, key: str, default: dict[str, Any]) -> dict[str, Any]:
    result = dict(default)
    value = _cfg_get(engine_cfg, key, default)
    if value is not None:
        result.update(dict(value))

    prefix = f"{key}."
    if hasattr(engine_cfg, "items"):
        for cfg_key, cfg_value in engine_cfg.items():
            if isinstance(cfg_key, str) and cfg_key.startswith(prefix):
                result[cfg_key[len(prefix) :]] = cfg_value
    return result


def _cfg_get(engine_cfg: Any, key: str, default: Any = None) -> Any:
    if engine_cfg is None:
        return default
    if hasattr(engine_cfg, "get"):
        return engine_cfg.get(key, default)
    return getattr(engine_cfg, key, default)


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _default_session_options() -> SessionOptions:
    """Build a SessionOptions with graph optimization and memory pattern enabled.

    These settings provide 10-30% CPU inference speedup with no accuracy impact.
    """
    opts = SessionOptions()
    opts.graph_optimization_level = GraphOptimizationLevel.ORT_ENABLE_ALL
    opts.enable_mem_pattern = True
    return opts


def create_session(
    model_path: str,
    providers: Sequence[Provider] | None = None,
    use_gpu: bool = False,
    gpu_id: int = 0,
    sess_options: SessionOptions | None = None,
) -> InferenceSession:
    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Model file not found: {model_path}. "
            f"Please download models first: python scripts/download_models.py"
        )
    if sess_options is None:
        sess_options = _default_session_options()
    session_providers = build_providers(
        use_gpu=use_gpu,
        gpu_id=gpu_id,
        providers=providers,
    )
    log.info("Creating ONNX session: {}, providers={}", model_path, session_providers)
    try:
        return InferenceSession(
            model_path,
            sess_options=sess_options,
            providers=session_providers,
        )
    except Exception as e:
        log.error("Failed to load model: {}, error: {}", model_path, e)
        raise
