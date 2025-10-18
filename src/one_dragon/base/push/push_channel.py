from abc import abstractmethod, ABC
from io import BytesIO

import cv2
from cv2.typing import MatLike

from one_dragon.base.push.push_channel_config import PushChannelConfigField


class PushChannel(ABC):

    def __init__(
        self,
        channel_id: str,
        channel_name: str,
        config_schema: list[PushChannelConfigField]
    ):
        self.channel_id: str = channel_id  # 渠道唯一标识
        self.channel_name: str = channel_name  # 渠道显示名称
        self.config_schema: list[PushChannelConfigField] = config_schema  # 所需的配置字段

    @abstractmethod
    def push(
        self,
        config: dict[str, str],
        title: str,
        content: str,
        image: MatLike | None = None,
    ) -> tuple[bool, str]:
        """
        推送消息

        Args:
            config: 配置
            title: 标题
            content: 内容
            image: 图片

        Returns:
            tuple[bool, str]: 是否成功、错误信息
        """
        pass

    @abstractmethod
    def validate_config(self, config: dict[str, str]) -> tuple[bool, str]:
        """
        验证配置

        Args:
            config: 配置

        Returns:
            tuple[bool, str]: 验证是否通过、错误信息
        """
        pass

    def image_to_bytes(self, image: MatLike) -> BytesIO | None:
        """
        将图片转换为字节数组

        Args:
            image: 图片

        Returns:
            bytes: 图片字节数组
        """
        retval, buffer = cv2.imencode('.png', cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        if retval:
            return BytesIO(buffer.tobytes())
        else:
            return None
