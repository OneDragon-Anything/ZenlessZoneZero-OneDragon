import io
import sys

import pytest

from one_dragon.launcher.exe_launcher import ExeLauncher


def test_show_version_writes_ascii_version_under_legacy_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = io.BytesIO()
    stdout = io.TextIOWrapper(buffer, encoding='cp1252', errors='strict')

    try:
        monkeypatch.setattr(sys, 'stdout', stdout)
        with pytest.raises(SystemExit) as exc_info:
            ExeLauncher('绝区零 一条龙 启动器', 'v2.3.3').show_version()
        stdout.flush()
        output = buffer.getvalue().decode('cp1252').strip()
    finally:
        stdout.close()

    assert exc_info.value.code == 0
    assert output == 'v2.3.3'
