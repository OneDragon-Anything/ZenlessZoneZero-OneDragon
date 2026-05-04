from __future__ import annotations

from typing import NamedTuple

from cv2.typing import MatLike


class NotifyPoolItem(NamedTuple):
    """通知池中的一条消息"""
    content: str
    image: MatLike | None = None


class NotifyPool:
    """通知池，收集应用运行期间的节点通知消息。

    在 ApplicationRunContext 中创建，每次应用开始运行时清空重用。
    支持合并消息模式，将所有节点消息合并为一个列表送出。
    池中仅保留最近 max_images 张图片以控制内存，文本始终保留。

    last_image 属性从 items 尾部遍历获取，用于 APP 级别结束通知附带截图。
    """

    def __init__(self) -> None:
        self.items: list[NotifyPoolItem] = []
        self.max_items: int = 200
        self.max_images: int = 10
        self._image_count: int = 0

    def add(self, content: str, image: MatLike | None = None) -> None:
        """添加一条通知到池中"""
        # 超出条目上限时，丢弃最旧的条目
        if len(self.items) >= self.max_items:
            removed = self.items.pop(0)
            if removed.image is not None:
                self._image_count -= 1
        self.items.append(NotifyPoolItem(content=content, image=image))
        if image is not None:
            self._image_count += 1
            # 超出图片上限时，移除最旧的图片以释放内存
            if self._image_count > self.max_images:
                self._strip_oldest_image()

    def _strip_oldest_image(self) -> None:
        """将最旧的一张图片从池中移除（替换为 None），文本保留"""
        for i, item in enumerate(self.items):
            if item.image is not None:
                self.items[i] = NotifyPoolItem(content=item.content)
                self._image_count -= 1
                return

    def __len__(self) -> int:
        return len(self.items)

    @property
    def last_image(self) -> MatLike | None:
        """从池中获取最后一张图片"""
        for item in reversed(self.items):
            if item.image is not None:
                return item.image
        return None

    def clear(self) -> None:
        self.items.clear()
        self._image_count = 0
