import numpy as np

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect


class ScreenArea:

    def __init__(
        self,
        area_name: str = '',
        pc_rect: Rect | None = None,
        text: str = '',
        lcs_percent: float = 0.5,
        template_id: str = '',
        template_sub_dir: str = '',
        template_match_threshold: float = 0.7,
        pc_alt: bool = False,
        id_mark: bool = False,
        goto_list: list[str] | None = None,
        color_range: list[list[int]] | None = None,
    ):
        self.area_name: str = area_name or ''
        self.pc_rect: Rect = pc_rect if pc_rect is not None else Rect(0, 0, 0, 0)
        self.text: str = text or ''
        self.lcs_percent: float = lcs_percent
        self.template_id: str = template_id or ''
        self.template_sub_dir: str = template_sub_dir or ''
        self.template_match_threshold: float = template_match_threshold
        self.pc_alt: bool = pc_alt  # PC端需要使用ALT后才能点击
        self.id_mark: bool = id_mark  # 是否用于画面的唯一标识
        self.goto_list: list[str] = [] if goto_list is None else goto_list  # 交互后 可能会跳转的画面名称列表
        self.color_range: list[list[int]] | None = color_range  # 识别时候的筛选的颜色范围 文本时候有效

    @property
    def rect(self) -> Rect:
        return self.pc_rect

    @property
    def center(self) -> Point:
        return self.rect.center

    @property
    def left_top(self) -> Point:
        return self.rect.left_top

    @property
    def right_bottom(self) -> Point:
        return self.rect.right_bottom

    @property
    def x1(self) -> int:
        return self.rect.x1

    @property
    def x2(self) -> int:
        return self.rect.x2

    @property
    def y1(self) -> int:
        return self.rect.y1

    @property
    def y2(self) -> int:
        return self.rect.y2

    @property
    def width(self) -> int:
        return self.rect.width

    @property
    def height(self) -> int:
        return self.rect.height

    @property
    def is_text_area(self) -> bool:
        """
        是否文本区域
        :return:
        """
        return len(self.text) > 0

    @property
    def is_template_area(self) -> bool:
        """
        是否模板区域
        :return:
        """
        return len(self.template_id) > 0

    @property
    def color_range_lower(self) -> np.ndarray:
        if self.color_range is None or len(self.color_range) < 1:
            return np.array([0, 0, 0], dtype=np.uint8)
        else:
            return np.array(self.color_range[0], dtype=np.uint8)

    @property
    def color_range_upper(self) -> np.ndarray:
        if self.color_range is None or len(self.color_range) < 2:
            return np.array([255, 255, 255], dtype=np.uint8)
        else:
            return np.array(self.color_range[1], dtype=np.uint8)

    def to_dict(self) -> dict:
        order_dict = dict()
        order_dict['area_name'] = self.area_name
        order_dict['id_mark'] = self.id_mark
        order_dict['pc_rect'] = [self.pc_rect.x1, self.pc_rect.y1, self.pc_rect.x2, self.pc_rect.y2]
        order_dict['text'] = self.text
        order_dict['lcs_percent'] = self.lcs_percent
        order_dict['template_sub_dir'] = self.template_sub_dir
        order_dict['template_id'] = self.template_id
        order_dict['template_match_threshold'] = self.template_match_threshold
        order_dict['color_range'] = self.color_range
        order_dict['goto_list'] = self.goto_list

        return order_dict
