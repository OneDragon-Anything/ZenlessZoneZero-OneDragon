from typing import Union


class Point:

    def __init__(self, x: Union[int, float], y: Union[int, float]):
        """
        一个点 坐标会转化成整数
        :param x: 横坐标
        :param y: 纵坐标
        """

        self.x: int = int(x)
        """横坐标"""
        self.y: int = int(y)
        """纵坐标"""

    def tuple(self):
        return self.x, self.y

    def __repr__(self):
        return '(%d, %d)' % (self.x, self.y)

    def __add__(self, other):
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Point(self.x - other.x, self.y - other.y)

    def __eq__(self, other):
        if isinstance(other, Point):
            return self.x == other.x and self.y == other.y
        if isinstance(other, (tuple, list)) and len(other) == 2:
            return self.x == other[0] and self.y == other[1]
        return False

    def __hash__(self):
        # 定义 __eq__ 后需显式定义 否则 Point 无法放入 set 或作为 dict 的键
        return hash((self.x, self.y))
