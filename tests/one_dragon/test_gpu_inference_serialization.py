from __future__ import annotations

import threading
import time
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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
