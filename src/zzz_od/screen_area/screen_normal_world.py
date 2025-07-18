from enum import Enum

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.screen_area import ScreenArea


class ScreenNormalWorldEnum(Enum):

    UID = ScreenArea(area_name='uid', pc_rect=Rect(1814, 1059, 1919, 1079))

class ScreenNormalWorldEnum_Emulator(Enum):

    UID = ScreenArea(area_name='uid', pc_rect=Rect(1684, 1059, 1819, 1079))
