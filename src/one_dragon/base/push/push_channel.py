import base64
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
        proxy_url: str | None = None,
    ) -> tuple[bool, str]:
        """
        推送消息

        Args:
            config: 配置
            title: 标题
            content: 内容
            image: 图片
            proxy_url: 代理地址 暂不支持验证

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

    def image_to_bytes(self, image: MatLike, max_bytes: int | None = None) -> BytesIO | None:
        """
        将图片转换为字节数组

        Args:
            image: 图片 RGB格式
            max_bytes: 图片最大字节数 超过时压缩

        Returns:
            BytesIO: 图片数据 统一jpeg格式
        """
        bgr_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        retval, buffer = cv2.imencode('.jpg', bgr_image)

        if retval:
            image_bytes = BytesIO(buffer.tobytes())
            if max_bytes is not None:
                img_bytes = image_bytes.getvalue()
                orig_size = len(img_bytes)
                if orig_size > max_bytes:
                    return self._compress_image_bytes(bgr_image, max_bytes)

            return image_bytes
        else:
            return None

    def _compress_image_bytes(self, bgr_image: MatLike, max_bytes: int) -> BytesIO | None:
        """
        自动将图片压缩为渐进式 JPG,使用二分搜索质量,尽量贴近 2MB 上限

        Args:
            bgr_image: 图片数据
            max_bytes: 最大字节数

        Returns:
            BytesIO: 压缩后的图片数据 统一jpeg格式
        """

        import cv2
        best: BytesIO | None = None

        # 二分搜索质量，尽量贴近 2MB
        lo, hi = 30, 90
        while lo <= hi:
            q = (lo + hi) // 2
            params = [
                int(cv2.IMWRITE_JPEG_QUALITY), int(q),
                int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,
                int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1,
            ]
            ok, enc = cv2.imencode('.jpg', bgr_image, params)
            if not ok:
                break
            size = enc.nbytes
            if size <= max_bytes:
                best = BytesIO(enc.tobytes())
                lo = q + 1  # 尝试更高质量
            else:
                hi = q - 1  # 降低质量

        return best

    def image_to_base64(self, image: MatLike, max_bytes: int | None = None) -> str | None:
        """
        将图片转换为 base64 字符串

        Args:
            image: 图片
            max_bytes: 图片最大字节数 超过时压缩

        Returns:
            str: 图片 base64 字符串
        """
        image_bytes = self.image_to_bytes(image, max_bytes=max_bytes)
        if image_bytes is None:
            return None
        image_bytes.seek(0)
        return base64.b64encode(image_bytes.getvalue()).decode('utf-8')

    def get_proxy(self, proxy_url: str) -> dict | None:
        """
        获取代理配置

        Args:
            proxy_url: 代理地址

        Returns:
            dict | None: 代理配置
        """
        if proxy_url is not None and proxy_url != "":
            return {"http": proxy_url, "https": proxy_url}
        else:
            return None
