from __future__ import annotations

from typing import NamedTuple

from cv2.typing import MatLike


class NotifyPoolItem(NamedTuple):
    """通知池中的一条消息"""
    content: str
    image: MatLike | None = None


class NotifyPool:
    """通知池，收集应用运行期间的节点通知消息。

    每个应用实例化时创建，收集节点通知的图片和信息。
    支持合并消息模式，将所有节点消息合并为一个列表送出。
    池中仅保留最近 max_images 张图片以控制内存，文本始终保留。
    """

    def __init__(self):
        self.items: list[NotifyPoolItem] = []
        self._last_image: MatLike | None = None
        self.max_images: int = 10
        self._image_count: int = 0

    def add(self, content: str, image: MatLike | None = None) -> None:
        """添加一条通知到池中"""
        if image is not None:
            self._last_image = image
            self._image_count += 1
            # 超出图片上限时，移除最旧的图片以释放内存
            if self._image_count > self.max_images:
                self._strip_oldest_image()
        self.items.append(NotifyPoolItem(content=content, image=image))

    def _strip_oldest_image(self) -> None:
        """将最旧的一张图片从池中移除（替换为 None），文本保留"""
        for i, item in enumerate(self.items):
            if item.image is not None:
                self.items[i] = NotifyPoolItem(content=item.content)
                self._image_count -= 1
                return

    @property
    def last_image(self) -> MatLike | None:
        """获取最后一张图片（独立追踪，不受池内图片淘汰影响）"""
        return self._last_image

    def __len__(self) -> int:
        return len(self.items)

    def clear(self) -> None:
        self.items.clear()
        self._last_image = None
        self._image_count = 0
