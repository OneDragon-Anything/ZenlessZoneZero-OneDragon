"""
遥测管理器
仅上报日活（app_launched）和应用关闭（app_shutdown），附带版本信息。
"""
import platform
import time
import uuid
from datetime import datetime
from typing import Any

from one_dragon.utils.log_utils import log

from .aliyun_web_tracking import AliyunWebTrackingClient

ALIYUN_WEB_TRACKING_ENDPOINT = (
    "https://zzz-od-1.cn-hangzhou.log.aliyuncs.com/logstores/zzz-od-1/track"
    "?APIVersion=0.6.0"
)


class TelemetryManager:
    """遥测管理器"""

    def __init__(self, context) -> None:
        self.ctx = context
        self._initialized = False
        self._session_id = str(uuid.uuid4())
        self._session_start: float = time.time()

        self._user_id: str = ""
        self._app_version: str = ""
        self._commit_version: str = ""
        self._launcher_version: str = ""
        self._aliyun_client: AliyunWebTrackingClient | None = None

    # ---- 公开接口 ----

    def initialize(self) -> bool:
        """初始化遥测，发送 app_launched"""
        try:
            self._user_id = self._generate_user_id()
            self._app_version = self._get_app_version()
            self._commit_version = self._get_commit_version()
            self._launcher_version = self._get_launcher_version()
            self._aliyun_client = AliyunWebTrackingClient(ALIYUN_WEB_TRACKING_ENDPOINT)
            self._initialized = True

            self._send_event("app_launched", {
                "launch_time_seconds": time.time() - self._session_start,
                "platform": platform.system(),
                "machine_id": f"{platform.node()}-{platform.machine()}",
                "session_start": datetime.now().isoformat(),
            })
            log.debug("Telemetry initialized")
            return True
        except Exception as e:
            log.debug(f"Telemetry init failed: {e}")
            return False

    def shutdown(self) -> None:
        """关闭遥测，发送 app_shutdown"""
        if not self._initialized:
            return
        try:
            self._send_event("app_shutdown", {
                "session_duration_seconds": time.time() - self._session_start,
                "clean_shutdown": True,
            })
            log.debug("Telemetry shutdown")
        except Exception as e:
            log.debug(f"Telemetry shutdown failed: {e}")
        finally:
            self._initialized = False

    def is_enabled(self) -> bool:
        return self._initialized

    # ---- 内部方法 ----

    def _send_event(self, event_name: str, extra: dict[str, Any]) -> None:
        if not self._aliyun_client:
            return
        payload: dict[str, Any] = {
            "session_id": self._session_id,
            "app_version": self._app_version,
            "commit_version": self._commit_version,
            "launcher_version": self._launcher_version,
            "user_id": self._user_id,
            "timestamp": datetime.now().isoformat(),
        }
        payload.update(extra)
        self._aliyun_client.send(event_name, payload)

    @staticmethod
    def _generate_user_id() -> str:
        machine_id = f"{platform.node()}-{platform.machine()}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, machine_id))

    def _get_app_version(self) -> str:
        try:
            version = getattr(self.ctx.project_config, "version", None)
            if version:
                return version
        except Exception:
            pass
        return "unknown"

    def _get_commit_version(self) -> str:
        """通过 git_service 获取当前 HEAD 的短 commit hash"""
        return self.ctx.git_service.get_head_commit_id(short=True) or "unknown"

    @staticmethod
    def _get_launcher_version() -> str:
        try:
            from one_dragon.utils.app_utils import get_launcher_version
            v = get_launcher_version()
            return v if v else "unknown"
        except Exception:
            return "unknown"
