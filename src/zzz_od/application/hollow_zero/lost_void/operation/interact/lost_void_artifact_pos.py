from typing import Optional

from one_dragon.base.geometry.rectangle import Rect
from zzz_od.application.hollow_zero.lost_void.context.lost_void_artifact import LostVoidArtifact


class LostVoidArtifactPos:

    def __init__(self, art: LostVoidArtifact, rect: Rect):
        self.artifact: LostVoidArtifact = art
        self.rect: Rect = rect

        self.can_choose: bool = True
        self.chosen: bool = False  # 已经被选择了
        self.store_price: Optional[int] = None
        self.store_buy_rect: Optional[Rect] = None
        self.is_new: bool = False

    def add_price(self, price: int, rect: Rect) -> bool:
        """
        添加价格
        @return:
        """
        x_dis = abs(self.rect.center.x - rect.center.x)
        if x_dis >= self.rect.width:
            return False

        self.store_price = price
        return True

    def add_buy(self, rect: Rect) -> bool:
        """
        添加购买按钮
        @return:
        """
        x_dis = abs(self.rect.center.x - rect.center.x)
        if x_dis >= self.rect.width:
            return False

        self.store_buy_rect = rect
        return True