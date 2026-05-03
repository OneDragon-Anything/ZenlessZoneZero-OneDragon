from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
from one_dragon.utils import gpu_executor


class ConcurrencyProbe:

    def __init__(self, target_parallelism: int = 2):
        self.target_parallelism = target_parallelism
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()
        self.parallel_event = threading.Event()

    def enter(self) -> None:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            if self.active >= self.target_parallelism:
                self.parallel_event.set()

        self.parallel_event.wait(timeout=0.2)
        time.sleep(0.02)

        with self.lock:
            self.active -= 1


class FakeSession:

    def __init__(
            self,
            probe: ConcurrencyProbe,
            providers: list[str] | None = None,
            fail_provider_lookup: bool = False,
    ):
        self.probe = probe
        self.providers = providers or ["DmlExecutionProvider"]
        self.fail_provider_lookup = fail_provider_lookup

    def get_providers(self) -> list[str]:
        if self.fail_provider_lookup:
            raise RuntimeError("provider lookup failed")
        return self.providers

    def run(self, output_names, input_feed):
        self.probe.enter()
        return [np.zeros((1, 1), dtype=np.float32)]


def test_create_onnx_session_serializes_dml_factories():
    probe = ConcurrencyProbe()

    def create_session():
        probe.enter()
        return object()

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_list = [
            executor.submit(
                gpu_executor.create_onnx_session,
                create_session,
                ["DmlExecutionProvider"],
            )
            for _ in range(2)
        ]
        for future in future_list:
            future.result(timeout=2)

    assert probe.max_active == 1


def test_run_session_serializes_dml_sessions():
    probe = ConcurrencyProbe()
    session = FakeSession(probe)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_list = [
            executor.submit(gpu_executor.run_session, session, ["output"], {"input": 1})
            for _ in range(2)
        ]
        for future in future_list:
            future.result(timeout=2)

    assert probe.max_active == 1


def test_run_session_serializes_when_provider_lookup_fails():
    probe = ConcurrencyProbe()
    session = FakeSession(probe, fail_provider_lookup=True)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_list = [
            executor.submit(gpu_executor.run_session, session, ["output"], {"input": 1})
            for _ in range(2)
        ]
        for future in future_list:
            future.result(timeout=2)

    assert probe.max_active == 1


def test_run_session_does_not_serialize_cpu_sessions():
    probe = ConcurrencyProbe()
    session = FakeSession(probe, providers=["CPUExecutionProvider"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_list = [
            executor.submit(gpu_executor.run_session, session, ["output"], {"input": 1})
            for _ in range(2)
        ]
        for future in future_list:
            future.result(timeout=2)

    assert probe.max_active >= 2


def test_ocr_init_model_uses_lock_for_concurrent_calls(monkeypatch):
    init_count = 0
    download_count = 0
    count_lock = threading.Lock()

    class FakeOcrRuntime:

        def __init__(self, **kwargs):
            nonlocal init_count
            time.sleep(0.05)
            with count_lock:
                init_count += 1

    fake_module = ModuleType("onnxocr.onnx_paddleocr")
    fake_module.ONNXPaddleOcr = FakeOcrRuntime
    monkeypatch.setitem(sys.modules, "onnxocr.onnx_paddleocr", fake_module)

    matcher = object.__new__(OnnxOcrMatcher)
    matcher._ocr_param = SimpleNamespace(to_dict=lambda: {})
    matcher._model = None
    matcher._init_lock = threading.Lock()

    def download(**kwargs):
        nonlocal download_count
        time.sleep(0.05)
        with count_lock:
            download_count += 1
        return True

    matcher.download = download

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_list = [executor.submit(matcher.init_model) for _ in range(2)]
        for future in future_list:
            assert future.result(timeout=2)

    assert download_count == 1
    assert init_count == 1


def test_ocr_init_model_failure_releases_lock(monkeypatch):
    fake_module = ModuleType("onnxocr.onnx_paddleocr")
    fake_module.ONNXPaddleOcr = object
    monkeypatch.setitem(sys.modules, "onnxocr.onnx_paddleocr", fake_module)

    matcher = object.__new__(OnnxOcrMatcher)
    matcher._ocr_param = SimpleNamespace(to_dict=lambda: {})
    matcher._model = None
    matcher._init_lock = threading.Lock()
    matcher.download = lambda **kwargs: False

    assert not matcher.init_model()
    assert matcher._init_lock.acquire(blocking=False)
    matcher._init_lock.release()
