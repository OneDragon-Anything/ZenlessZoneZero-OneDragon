from typing import List, Optional, Any

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect


class MatchResult:

    def __init__(self, c, x, y, w, h, template_scale: float = 1, data: Any = None):
        """
        识别结果 用于cv2和ocr
        """
        self.confidence: float = float(c)
        self.x: int = int(x)
        self.y: int = int(y)
        self.w: int = int(w)
        self.h: int = int(h)
        self.template_scale: float = template_scale
        self.data: Any = data

    def __repr__(self):
        return '(%.2f, %d, %d, %d, %d, %.2f)' % (self.confidence, self.x, self.y, self.w, self.h, self.template_scale)

    @property
    def left_top(self) -> Point:
        return Point(self.x, self.y)

    @property
    def center(self) -> Point:
        return Point(self.x + self.w // 2, self.y + self.h // 2)

    @property
    def right_bottom(self) -> Point:
        return Point(self.x + self.w, self.y + self.h)

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.x + self.w, self.y + self.h)

    def add_offset(self, p: Point):
        self.x += p.x
        self.y += p.y


class MatchResultList:
    def __init__(self, only_best: bool = True):
        """
        多个识别结果的组合 适用于一张图中有多个目标结果
        """
        self.only_best: bool = only_best
        self.arr: List[MatchResult] = []
        self.max: Optional[MatchResult] = None

    def __repr__(self):
        return '[%s]' % ', '.join(str(i) for i in self.arr)

    def __iter__(self):
        self.index = 0
        return self

    def __next__(self):
        if self.index < len(self.arr):
            value = self.arr[self.index]
            self.index += 1
            return value
        else:
            raise StopIteration

    def __len__(self):
        return len(self.arr)

    def append(self, a: MatchResult, auto_merge: bool = True, merge_distance: float = 10):
        """
        添加匹配结果，如果开启合并，则保留置信度更高的结果
        :param a: 需要添加的结构
        :param auto_merge: 是否与之前结果进行合并
        :param merge_distance: 多少距离内的
        :return:
        """
        if self.only_best:
            if self.max is None:
                self.max = a
                self.arr.append(a)
            elif a.confidence > self.max.confidence:
                self.max = a
                self.arr[0] = a
        else:
            if auto_merge:
                for i in self.arr:
                    if (i.x - a.x) ** 2 + (i.y - a.y) ** 2 <= merge_distance ** 2:
                        if a.confidence > i.confidence:
                            i.x = a.x
                            i.y = a.y
                            i.confidence = a.confidence
                        return

            self.arr.append(a)
            if self.max is None or a.confidence > self.max.confidence:
                self.max = a

    def extend(self, mrl: "MatchResultList", auto_merge: bool = True, merge_distance: float = 10) -> None:
        """
        加入将另一个列表的所有元素
        :param mrl: 另一个列表
        :param auto_merge: 是否合并
        :param merge_distance: 合并距离
        :return:
        """
        for mr in mrl.arr:
            self.append(mr, auto_merge=auto_merge, merge_distance=merge_distance)

    def __getitem__(self, item):
        return self.arr[item]

    def add_offset(self, lt: Point) -> None:
        """
        给所有结果增加一个左上角的偏移
        用于截取区域后
        """
        for mr in self.arr:
            mr.add_offset(lt)
