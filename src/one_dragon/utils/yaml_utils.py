import yaml
from typing import Any, IO

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader


def safe_load(stream: str | bytes | IO[str] | IO[bytes]) -> Any:
    return yaml.load(stream, Loader=SafeLoader)

