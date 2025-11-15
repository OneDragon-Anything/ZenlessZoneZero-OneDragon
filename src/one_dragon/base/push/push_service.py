from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from typing import TYPE_CHECKING

from cv2.typing import MatLike

from one_dragon.base.push.channel.ai_botk import AiBotK
from one_dragon.base.push.channel.bark import Bark
from one_dragon.base.push.channel.chronocat import Chronocat
from one_dragon.base.push.channel.dingding import DingDingBot
from one_dragon.base.push.channel.discord import Discord
from one_dragon.base.push.channel.fake import FakePushChannel
from one_dragon.base.push.channel.feishu import FeiShu
from one_dragon.base.push.channel.gotify import Gotify
from one_dragon.base.push.channel.i_got import IGot
from one_dragon.base.push.channel.ntfy import Ntfy
from one_dragon.base.push.channel.one_bot import OneBot
from one_dragon.base.push.channel.push_deer import PushDeer
from one_dragon.base.push.channel.push_me import PushMe
from one_dragon.base.push.channel.push_plus import PushPlus
from one_dragon.base.push.channel.q_msg import QMsg
from one_dragon.base.push.channel.server_chan import ServerChan
from one_dragon.base.push.channel.smtp import Smtp
from one_dragon.base.push.channel.synology_chat import SynologyChat
from one_dragon.base.push.channel.telegram import Telegram
from one_dragon.base.push.channel.we_plus_bot import WePlusBot
from one_dragon.base.push.channel.webhook import Webhook
from one_dragon.base.push.channel.work_weixin_bot import WorkWeixinBot
from one_dragon.base.push.channel.work_weixin_app import WorkWeixinApp
from one_dragon.base.push.channel.wx_pusher import WxPusher
from one_dragon.base.push.push_channel import PushChannel
from one_dragon.base.push.push_channel_config import PushChannelConfigField
from one_dragon.base.push.push_config import PushConfig, PushProxy
from one_dragon.utils import thread_utils
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class PushService:

    def __init__(self, ctx: OneDragonContext):
        self.ctx: OneDragonContext = ctx

        self._executor = ThreadPoolExecutor(
            thread_name_prefix="one_dragon_push_service", max_workers=1
        )

        self._init_lock = threading.Lock()
        self._inited: bool = False
        self.channels: list[PushChannel] = []
        self._id_2_channels: dict[str, PushChannel] = {}
        self._id_2_channel_schemas: dict[str, list[PushChannelConfigField]] = {}

    def init_push_channels(self) -> None:
        """
        初始化推送渠道 由上层决定什么时候初始化
        """
        if not self._init_lock.acquire(blocking=False):
            return

        try:
            if self._inited:
                return

            self._add_channel(Smtp())
            self._add_channel(Webhook())
            self._add_channel(DingDingBot())
            self._add_channel(FeiShu())
            self._add_channel(WorkWeixinBot())
            self._add_channel(WorkWeixinApp())
            self._add_channel(OneBot())
            self._add_channel(Bark())
            self._add_channel(ServerChan())
            self._add_channel(PushPlus())
            self._add_channel(Discord())
            self._add_channel(Telegram())
            self._add_channel(Ntfy())
            self._add_channel(FakePushChannel())
            self._add_channel(Gotify())
            self._add_channel(AiBotK())
            self._add_channel(WxPusher())
            self._add_channel(WePlusBot())
            self._add_channel(QMsg())
            self._add_channel(PushMe())
            self._add_channel(Chronocat())
            self._add_channel(PushDeer())
            self._add_channel(IGot())
            self._add_channel(SynologyChat())

            self._inited = True
        finally:
            self._init_lock.release()

    def _add_channel(self, channel: PushChannel) -> None:
        """
        添加一个推送渠道
        Args:
            channel: 推送渠道

        """
        self.channels.append(channel)
        self._id_2_channels[channel.channel_id] = channel
        self._id_2_channel_schemas[channel.channel_id] = channel.config_schema

    @cached_property
    def push_config(self) -> PushConfig:
        self.init_push_channels()
        start_time = time.time()
        while not self._inited:
            time.sleep(1)
            if time.time() - start_time > 5:
                raise Exception('推送服务初始化超时')

        config = PushConfig()
        config.generate_channel_fields(self._id_2_channel_schemas)

        return config

    def push(
        self,
        title: str,
        content: str,
        image: MatLike | None = None,
        channel_id: str | None = None,
    ) -> tuple[bool, str]:
        """
        推送消息

        Args:
            title: 标题
            content: 内容
            image: 图片
            channel_id: 推送渠道ID 未传入时使用所有能通过配置校验的渠道

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        if not self.push_config.send_image:
            image = None

        any_ok: bool = False
        err_msg: str = ''
        if channel_id is None:
            any_push = False
            for channel_id, channel in self._id_2_channels.items():
                channel_config = self.get_channel_config(channel_id)
                ok, msg = channel.validate_config(channel_config)
                if not ok:
                    continue

                any_push = True

                ok, msg = channel.push(
                    config=channel_config,
                    title=title,
                    content=content,
                    image=image,
                    proxy_url=self.get_proxy(),
                )
                if not ok:
                    log.error(f'推送失败: {channel_id} {msg}')
                    err_msg += f'{channel_id} {msg}\n'
                    continue

                any_ok = True
                log.info(f'推送成功: {channel_id}')

            if not any_push:
                return False, '没有可用的推送渠道'
        else:
            channel = self._id_2_channels.get(channel_id)
            if channel is None:
                return False, f'推送渠道不存在: {channel_id}'
            channel_config = self.get_channel_config(channel_id)
            ok, msg = channel.validate_config(channel_config)
            if not ok:
                return False, msg
            any_ok, err_msg = channel.push(
                config=channel_config,
                title=title,
                content=content,
                image=image,
                proxy_url=self.get_proxy(),
            )

        return any_ok, err_msg

    def get_channel_config(self, channel_id: str) -> dict[str, str]:
        """
        提取推送渠道配置

        Args:
            channel_id: 推送渠道ID

        Returns:
            dict[str, str]: 推送渠道配置 key是schema中定义的var_suffix
        """
        config: dict[str, str] = {}

        if channel_id not in self._id_2_channel_schemas:
            return config

        push_config = self.push_config
        fields = self._id_2_channel_schemas[channel_id]
        for field in fields:
            value = push_config.get_channel_config_value(
                channel_id=channel_id,
                field_name=field.var_suffix,
                default_value=field.default,
            )
            config[field.var_suffix] = value

        return config

    def push_async(
        self,
        title: str,
        content: str,
        image: MatLike | None = None,
        channel_id: str | None = None,
    ) -> None:
        """
        异步推送消息

        Args:
            title: 标题
            content: 内容
            image: 图片
            channel_id: 推送渠道ID 未传入时使用所有能通过配置校验的渠道
        """
        future = self._executor.submit(
            self.push,
            title,
            content,
            image,
            channel_id,
        )
        future.add_done_callback(thread_utils.handle_future_result)

    def get_proxy(self) -> str | None:
        """
        Returns:
            获取配置使用的代理地址
        """
        config = self.push_config
        if (config.proxy == PushProxy.PERSONAL.value.value
            and self.ctx.env_config.is_personal_proxy):
            return self.ctx.env_config.personal_proxy

        return None
