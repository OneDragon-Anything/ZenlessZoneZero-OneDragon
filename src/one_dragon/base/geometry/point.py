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
