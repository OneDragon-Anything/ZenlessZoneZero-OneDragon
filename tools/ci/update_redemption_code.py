import json
import re
import ssl
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TZ_OFFSET_HOURS = 8

URLS = {
    "activity": "https://bbs-api.miyoushe.com/apihub/api/home/new?gids=8&parts=1%2C3%2C4&device=OnePlus%20IN2025&cpu=placeholder&version=3",
    "index": "https://api-takumi.mihoyo.com/event/miyolive/index",
    "code": "https://api-takumi-static.mihoyo.com/event/miyolive/refreshCode",
}


class GameRedeemCode:
    def __init__(self, proxy: str | None = None) -> None:
        self.act_id: str | None = None
        self.code_ver: str | None = None
        self.deadline: datetime | None = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.proxy = proxy
        self._ssl_context = ssl.create_default_context()

    def _request(self, url: str, headers: dict | None = None, retries: int = 3) -> dict[str, Any]:
        """使用 urllib.request 发送 GET 请求"""
        req_headers = {**self.headers, "Content-Type": "application/json", "Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(url, headers=req_headers, method="GET")

        if self.proxy:
            handler = urllib.request.ProxyHandler({"http": self.proxy, "https": self.proxy})
            opener = urllib.request.build_opener(handler, urllib.request.HTTPSHandler(context=self._ssl_context))
        else:
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=self._ssl_context))

        last_error: Exception | None = None
        for _ in range(retries):
            try:
                with opener.open(req, timeout=10) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as e:
                last_error = e

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"请求失败: {url}")

    def get_act_id(self) -> str | None:
        """从活动列表获取活动ID"""
        try:
            data = self._request(URLS["activity"])
            if data.get("retcode") != 0:
                return None

            keywords = ["前瞻"]
            for nav in data.get("data", {}).get("navigator", []):
                name = nav.get("name", "")
                if name and all(word in name for word in keywords):
                    match = re.search(r"act_id=(.*?)&", nav.get("app_path", ""))
                    if match:
                        return match.group(1)
            return None
        except Exception as e:
            print(f"获取 act_id 失败: {e}")
            return None

    def get_live_data(self, act_id: str) -> dict[str, Any] | None:
        """获取直播数据"""
        try:
            data = self._request(URLS["index"], headers={"x-rpc-act_id": act_id})
            if data.get("retcode") != 0:
                return None

            live_raw = data.get("data", {}).get("live", {})

            live_data = {
                "code_ver": live_raw.get("code_ver"),
                "title": live_raw.get("title", "").replace("特别直播", ""),
                "is_end": live_raw.get("is_end", False),
                "start": live_raw.get("start"),
            }

            # 计算过期时间
            if live_raw.get("start"):
                beijing_tz = timezone(timedelta(hours=TZ_OFFSET_HOURS))
                try:
                    start_dt = datetime.strptime(live_raw["start"], "%Y-%m-%d %H:%M:%S")
                    start_dt = start_dt.replace(tzinfo=beijing_tz)
                    self.deadline = (start_dt + timedelta(days=1)).replace(hour=23, minute=59, second=59)
                except ValueError:
                    self.deadline = datetime.now(beijing_tz) + timedelta(days=1)

            return live_data
        except Exception as e:
            print(f"获取直播数据失败: {e}")
            return None

    def get_codes(self, version: str, act_id: str) -> list[str] | None:
        """获取兑换码列表"""
        try:
            url = f"{URLS['code']}?version={version}&time={int(time.time())}"
            data = self._request(url, headers={"x-rpc-act_id": act_id})
            if data.get("retcode") != 0:
                return None

            code_list = data.get("data", {}).get("code_list", [])
            return [item["code"] for item in code_list if item.get("code")]
        except Exception as e:
            print(f"获取兑换码失败: {e}")
            return None

    def fetch_redeem_codes(self) -> list[str] | None:
        """获取兑换码完整流程"""
        act_id = self.get_act_id()
        if not act_id:
            print("暂无前瞻直播资讯")
            return None

        self.act_id = act_id
        live_data = self.get_live_data(act_id)
        if not live_data:
            print("获取直播数据失败")
            return None

        self.code_ver = live_data.get("code_ver")
        if not self.code_ver:
            print("未找到 code_ver")
            return None

        codes = self.get_codes(self.code_ver, act_id)
        if not codes:
            print("未获取到兑换码")
            return None

        print(f"获取到 {len(codes)} 个兑换码: {codes}")
        return codes

    def _get_beijing_now(self) -> datetime:
        """获取北京时间的当前时间"""
        beijing_tz = timezone(timedelta(hours=TZ_OFFSET_HOURS))
        return datetime.now(beijing_tz)

    def update_redemption_codes_yml(self) -> bool:
        """更新 config/redemption_codes.sample.yml 文件（一条龙维护的兑换码）"""
        codes = self.fetch_redeem_codes()
        if not codes:
            return False

        beijing_now = self._get_beijing_now()

        # 计算过期时间 YYYYMMDD 格式
        if self.deadline:
            end_dt = int(self.deadline.strftime("%Y%m%d"))
        else:
            # 默认7天后过期（北京时间）
            end_dt = int((beijing_now + timedelta(days=7)).strftime("%Y%m%d"))

        # 添加项目路径到 sys.path 以便导入模块
        _PROJECT_ROOT = Path(__file__).parent.parent.parent
        _SRC_PATH = _PROJECT_ROOT / "src"
        if str(_SRC_PATH) not in sys.path:
            sys.path.insert(0, str(_SRC_PATH))

        from zzz_od.application.redemption_code.redemption_code_config import (
            RedemptionCodeConfig,
        )

        config = RedemptionCodeConfig()

        # 清理过期兑换码（使用北京时间）
        today = int(beijing_now.strftime("%Y%m%d"))
        expired_count = config.clean_expired_sample_codes(today)
        if expired_count > 0:
            print(f"已删除 {expired_count} 个过期兑换码")

        # 添加新兑换码
        existing_codes = config.sample_codes_dict
        new_count = 0
        for code in codes:
            if code not in existing_codes:
                config.add_sample_code(code, end_dt)
                new_count += 1

        print(f"成功添加 {new_count} 个新兑换码，共 {len(config.sample_codes_dict)} 个兑换码")
        return True


if __name__ == "__main__":
    fetcher = GameRedeemCode()
    success = fetcher.update_redemption_codes_yml()
    if not success:
        sys.exit(1)
