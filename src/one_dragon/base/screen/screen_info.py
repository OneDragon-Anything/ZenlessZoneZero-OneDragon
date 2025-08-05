import cv2
import os
from cv2.typing import MatLike
from typing import List, Optional

from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.utils import os_utils, cv2_utils


class ScreenInfo(YamlOperator):

    def __init__(self, screen_id: Optional[str] = None, create_new: bool = False):
        self.old_screen_id: str = screen_id  # 旧的画面ID 用于保存时删掉旧文件
        self.screen_id: str = screen_id  # 画面ID 用于加载文件
        self.screen_name: str = ''  # 画面名称 用于显示

        self.screen_image: Optional[MatLike] = None

        self.pc_alt: bool = False  # PC端点击是否需要使用ALT键
        self.area_list: List[ScreenArea] = []  # 画面中包含的区域

        if create_new:
            YamlOperator.__init__(self)
        else:
            YamlOperator.__init__(self, self.get_yml_file_path())
            self._init_from_data()

    @staticmethod
    def get_dir_path() -> str:
        """
        文件夹位置
        :return:
        """
        return os_utils.get_path_under_work_dir('assets', 'game_data', 'screen_info')

    def get_yml_file_path(self, old: bool = False) -> str:
        """
        配置文件位置
        :param old: 是否取旧文件的路径
        :return:
        """
        if old and self.old_screen_id is not None:
            return os.path.join(self.get_dir_path(), f'{self.old_screen_id}.yml')
        else:
            return os.path.join(self.get_dir_path(), f'{self.screen_id}.yml')

    def get_image_file_path(self) -> str:
        """
        图片位置
        :return:
        """
        return os.path.join(self.get_dir_path(), f'{self.screen_id}.png')

    def _init_from_data(self) -> None:
        """
        从文本中初始化
        :return:
        """
        self.screen_name = self.get('screen_name', '')
        screen_image_path = self.get_image_file_path()
        if os.path.exists(screen_image_path):
            self.screen_image = cv2_utils.read_image(screen_image_path)
        self.pc_alt = self.get('pc_alt', False)

        data_area_list = self.get('area_list', [])
        for data_area in data_area_list:
            pc_rect = data_area.get('pc_rect')
            area = ScreenArea(
                area_name=data_area.get('area_name'),
                pc_rect=Rect(pc_rect[0], pc_rect[1], pc_rect[2], pc_rect[3]),
                text=data_area.get('text'),
                lcs_percent=data_area.get('lcs_percent'),
                template_id=data_area.get('template_id'),
                template_sub_dir=data_area.get('template_sub_dir'),
                template_match_threshold=data_area.get('template_match_threshold'),
                color_range=data_area.get('color_range'),
                pc_alt=self.pc_alt,
                id_mark=data_area.get('id_mark', False),
                goto_list=data_area.get('goto_list', [])
            )
            self.area_list.append(area)

    def get_image_to_show(self, highlight_area_idx: Optional[int] = None) -> MatLike:
        """
        用于显示的图片
        :param highlight_area_idx: 高亮区域索引
        :return:
        """
        if self.screen_image is None:
            return None

        image = self.screen_image.copy()
        for idx, area in enumerate(self.area_list):
            if highlight_area_idx is not None and idx == highlight_area_idx:
                color = (0, 0, 255)
                thickness = 4
            else:
                color = (255, 0, 0)
                thickness = 2

            # 将框绘制在区域外侧，避免遮挡内容
            # 通过调整坐标，让框的边缘位于区域外部
            half_thickness = thickness // 2
            outer_x1 = area.pc_rect.x1 - half_thickness
            outer_y1 = area.pc_rect.y1 - half_thickness
            outer_x2 = area.pc_rect.x2 + half_thickness
            outer_y2 = area.pc_rect.y2 + half_thickness

            # 确保调整后的坐标在图像范围内
            img_height, img_width = image.shape[:2]
            outer_x1 = max(0, outer_x1)
            outer_y1 = max(0, outer_y1)
            outer_x2 = min(img_width - 1, outer_x2)
            outer_y2 = min(img_height - 1, outer_y2)

            if outer_x2 > outer_x1 and outer_y2 > outer_y1:
                cv2.rectangle(image,
                              (outer_x1, outer_y1),
                              (outer_x2, outer_y2),
                              color, thickness)

        return image

    def remove_area_by_idx(self, idx: int) -> None:
        """
        删除某行数据
        :param idx:
        :return:
        """
        if self.area_list is None:
            return
        length = len(self.area_list)
        if idx < 0 or idx >= length:
            return
        self.area_list.pop(idx)

    def save(self):
        """
        保存 覆写了基类的方法
        :return:
        """
        order_dict = dict()
        order_dict['screen_id'] = self.screen_id
        order_dict['screen_name'] = self.screen_name
        order_dict['pc_alt'] = self.pc_alt
        order_dict['area_list'] = [i.to_order_dict() for i in self.area_list]

        self.file_path = self.get_yml_file_path(old=False)  # screen_id 有修改 更新路径
        self.data = order_dict
        YamlOperator.save(self)

        # screen_id 有修改 删除旧的文件
        if self.old_screen_id is not None and len(self.old_screen_id) > 0 and self.old_screen_id != self.screen_id:
            old_yml_file_path = self.get_yml_file_path(old=True)
            if os.path.exists(old_yml_file_path):
                os.remove(old_yml_file_path)

    def delete(self):
        """
        删除 覆写了基类的方法
        :return:
        """
        self.file_path = self.get_yml_file_path(old=False)  # screen_id 有修改 更新路径
        YamlOperator.delete(self)
