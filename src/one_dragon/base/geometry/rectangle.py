from typing import Union

from one_dragon.base.geometry.point import Point


class Rect:

    def __init__(self, x1: Union[int, float], y1: Union[int, float], x2: Union[int, float], y2: Union[int, float]):
        """
        一个矩形 坐标会转化成整数
        :param x1: 左上角 横坐标
        :param y1: 左上角 纵坐标
        :param x2: 右下角 横坐标
        :param y2: 右下角 纵坐标
        """

        self.x1: int = int(x1)
        self.y1: int = int(y1)
        self.x2: int = int(x2)
        self.y2: int = int(y2)

    @property
    def center(self) -> Point:
        return Point((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    def __repr__(self):
        return '(%d, %d, %d, %d)' % (self.x1, self.y1, self.x2, self.y2)

    @property
    def left_top(self) -> Point:
        return Point(self.x1, self.y1)

    @property
    def right_bottom(self) -> Point:
        return Point(self.x2, self.y2)

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    def add_offset(self, p: Point):
        self.x1 += p.x
        self.y1 += p.y
        self.x2 += p.x
        self.y2 += p.y

    @property
    def area(self) -> float:
        """
        Returns:
            area: 面积
        """
        return self.height * self.width
