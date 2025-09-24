import cv2
import numpy as np
import os
import shutil
from cv2.typing import MatLike
from enum import Enum
from functools import lru_cache
from typing import List, Optional, Tuple

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import os_utils, cal_utils, cv2_utils

TEMPLATE_RAW_FILE_NAME = 'raw.png'
TEMPLATE_MASK_FILE_NAME = 'mask.png'
TEMPLATE_CONFIG_FILE_NAME = 'config.yml'
TEMPLATE_FEATURES_FILE_NAME = 'features.xml'


class TemplateShapeEnum(Enum):

    RECTANGLE = ConfigItem(label='矩形', value='rectangle')
    CIRCLE = ConfigItem(label='圆形', value='circle')
    QUADRILATERAL = ConfigItem(label='四边形', value='quadrilateral')
    POLYGON = ConfigItem(label='多边形', value='polygon')
    MULTI_RECT = ConfigItem(label='多个矩形', value='multi_rect')


class TemplateInfo(YamlOperator):

    def __init__(self, sub_dir: str, template_id: str):
        # 旧的模板ID 在开发工具中使用 方便更改后迁移文件
        self.old_sub_dir: str = sub_dir
        self.old_template_id: str = template_id

        self.sub_dir: str = sub_dir
        self.template_id: str = template_id

        self.screen_image: Optional[MatLike] = None

        YamlOperator.__init__(self, file_path=self.get_yml_file_path())

        self.template_name: str = self.get('template_name', '')
        self.template_shape: str = self.get('template_shape', TemplateShapeEnum.RECTANGLE.value.value)
        self.point_list: List[Point] = []
        point_data: List[str] = self.get('point_list', [])
        for point_str in point_data:
            point_arr = point_str.split(',')
            self.point_list.append(Point(int(point_arr[0]), int(point_arr[1])))
        self.auto_mask: bool = self.get('auto_mask', True)
        self.point_updated: bool = False  # 点位是否更改过 开发工具中用

        self.raw: MatLike = cv2_utils.read_image(get_template_raw_path(self.sub_dir, self.template_id))  # 原图
        self.mask: MatLike = cv2_utils.read_image(get_template_mask_path(self.sub_dir, self.template_id))  # 掩码

        # 运算后保存在内存的
        self._gray: MatLike = None  # 灰度图
        self._kps: List[cv2.KeyPoint] = None  # 关键点
        self._desc: MatLike = None  # 描述

    def get_yml_file_path(self) -> str:
        return get_template_config_path(self.sub_dir, self.template_id)

    def remove_point_by_idx(self, idx: int) -> None:
        """
        移除坐标
        :param idx:
        :return:
        """
        if idx < 0 or idx >= len(self.point_list):
            return
        self.point_list.pop(idx)

    def add_point(self, point: Point) -> None:
        """
        增加一个点 会根据图形不一样替换
        :param point:
        :return:
        """
        self.point_updated = True
        if self.template_shape == TemplateShapeEnum.RECTANGLE.value.value:
            if len(self.point_list) < 2:
                self.point_list.append(point)
            elif len(self.point_list) == 2:
                if (cal_utils.distance_between(point, self.point_list[0]) <
                        cal_utils.distance_between(point, self.point_list[1])):
                    self.point_list[0] = point
                else:
                    self.point_list[1] = point

            if len(self.point_list) == 2:
                min_x = min(self.point_list[0].x, self.point_list[1].x)
                min_y = min(self.point_list[0].y, self.point_list[1].y)
                max_x = max(self.point_list[0].x, self.point_list[1].x)
                max_y = max(self.point_list[0].y, self.point_list[1].y)

                self.point_list[0] = Point(min_x, min_y)
                self.point_list[1] = Point(max_x, max_y)
        elif self.template_shape == TemplateShapeEnum.QUADRILATERAL.value.value:
            if len(self.point_list) < 4:
                self.point_list.append(point)
        elif self.template_shape == TemplateShapeEnum.CIRCLE.value.value:
            if len(self.point_list) < 2:
                self.point_list.append(point)
        elif self.template_shape == TemplateShapeEnum.POLYGON.value.value:
            self.point_list.append(point)
        elif self.template_shape == TemplateShapeEnum.MULTI_RECT.value.value:
            self.point_list.append(point)

    def get_image(self, t: Optional[str]) -> MatLike:
        if t is None or t == 'raw':
            return self.raw
        if t == 'gray':
            return self.gray
        if t == 'mask':
            return self.mask

    @property
    def gray(self) -> MatLike:
        if self._gray is not None:
            return self._gray
        if self.raw is None:
            return None
        self._gray = cv2.cvtColor(self.raw, cv2.COLOR_RGB2GRAY)
        return self._gray

    @property
    def features(self) -> Tuple[List[cv2.KeyPoint], MatLike]:
        if self._kps is not None:
            return self._kps, self._desc
        if self.raw is not None:
            self._kps, self._desc = cv2_utils.feature_detect_and_compute(self.raw, self.mask)
        return self._kps, self._desc

    def make_template_dir(self) -> None:
        """
        创建模板的文件夹
        如果模板分类或者id变了 移动文件夹
        :return:
        """
        move_old: bool = True
        if self.old_sub_dir is None or len(self.old_sub_dir) == 0:
            move_old = False
        elif self.old_template_id is None or len(self.old_template_id) == 0:
            move_old = False
        elif self.sub_dir == self.old_sub_dir and self.template_id == self.old_template_id:
            move_old = False

        new_dir_path = get_template_dir_path(self.sub_dir, self.template_id, make_dir=True)

        if move_old:
            old_dir_path = get_template_dir_path(self.old_sub_dir, self.old_template_id)
            if os.path.exists(old_dir_path):
                for file_name in os.listdir(old_dir_path):
                    old_file_path = os.path.join(old_dir_path, file_name)
                    if os.path.isdir(old_file_path):
                        continue
                    new_file_path = os.path.join(new_dir_path, file_name)
                    shutil.move(old_file_path, new_file_path)
                shutil.rmtree(old_dir_path)

        self.old_sub_dir = self.sub_dir
        self.old_template_id = self.template_id

    def save_config(self) -> None:
        """
        保存模板配置
        :return:
        """
        self.make_template_dir()

        data = {}
        data['sub_dir'] = self.sub_dir
        data['template_id'] = self.template_id
        data['template_name'] = self.template_name
        data['template_shape'] = self.template_shape
        data['auto_mask'] = self.auto_mask
        data['point_list'] = [f'{p.x}, {p.y}' for p in self.point_list]

        self.file_path = self.get_yml_file_path()  # 更新路径
        self.data = data
        YamlOperator.save(self)

    def save_raw(self) -> None:
        """
        保存模板原图
        :return:
        """
        self.make_template_dir()
        raw = self.get_template_raw_by_screen_point()
        if raw is not None:
            cv2_utils.save_image(raw, get_template_raw_path(self.sub_dir, self.template_id))

    def save_mask(self) -> None:
        """
        保存模板掩码
        :return:
        """
        self.make_template_dir()
        mask = self.get_template_mask_by_screen_point() if self.auto_mask else None
        if mask is not None:
            cv2_utils.save_image(mask, get_template_mask_path(self.sub_dir, self.template_id))

    def delete(self) -> None:
        pass

    def get_template_rect_by_point(self) -> Optional[Rect]:
        """
        根据点位 得到模板在游戏画面的位置矩阵
        :return:
        """
        point_list: List[Point] = []
        if self.template_shape == TemplateShapeEnum.RECTANGLE.value.value:
            if len(self.point_list) != 2:
                return None
            point_list = self.point_list
        elif self.template_shape == TemplateShapeEnum.CIRCLE.value.value:
            if len(self.point_list) != 2:
                return None
            center = self.point_list[0]
            r = int(cal_utils.distance_between(self.point_list[0], self.point_list[1]))
            point_list.append(center - Point(r, r))
            point_list.append(center + Point(r, r))
        elif self.template_shape == TemplateShapeEnum.QUADRILATERAL.value.value:
            if len(self.point_list) != 4:
                return None
            point_list = self.point_list
        elif self.template_shape == TemplateShapeEnum.POLYGON.value.value:
            if len(self.point_list) < 3:
                return None
            point_list = self.point_list
        elif self.template_shape == TemplateShapeEnum.MULTI_RECT.value.value:
            if len(self.point_list) < 2:
                return None
            point_list = self.point_list

        if len(point_list) == 0:
            return None

        min_x = min([p.x for p in point_list])
        min_y = min([p.y for p in point_list])
        max_x = max([p.x for p in point_list])
        max_y = max([p.y for p in point_list])

        return Rect(min_x, min_y, max_x, max_y)

    def get_template_raw_by_screen_point(self) -> Optional[MatLike]:
        """
        根据配置和画面 扣出模板原图
        :return:
        """
        if self.screen_image is None:
            return None
        rect = self.get_template_rect_by_point()
        return cv2_utils.crop_image_only(self.screen_image, rect, copy=True) if rect is not None else None

    def get_template_raw_to_display(self) -> Optional[MatLike]:
        """
        获取用于开发工具显示的模板原图
        :return:
        """
        if self.point_updated or self.raw is None:
            return self.get_template_raw_by_screen_point()
        else:
            return self.raw

    def get_template_mask_by_screen_point(self) -> Optional[MatLike]:
        """
        根据配置和画面 扣出模板掩码
        :return:
        """
        if self.screen_image is None:
            return None

        rect = self.get_template_rect_by_point()
        if rect is None:
            return None

        mask = np.zeros(self.screen_image.shape[:2], dtype=np.uint8)

        if (self.template_shape == TemplateShapeEnum.RECTANGLE.value.value
                and len(self.point_list) == 2):
            left_top = self.point_list[0]
            right_bottom = self.point_list[1]

            cv2.rectangle(mask, (left_top.x, left_top.y), (right_bottom.x, right_bottom.y), color=(255, 255, 255), thickness=-1)
        elif (self.template_shape == TemplateShapeEnum.CIRCLE.value.value
              and len(self.point_list) == 2):
            center = self.point_list[0]
            r = cal_utils.distance_between(center, self.point_list[1])
            cv2.circle(mask, (center.x, center.y), int(r), color=(255, 255, 255), thickness=-1)
        elif (self.template_shape == TemplateShapeEnum.QUADRILATERAL.value.value
              and len(self.point_list) == 4):
            points = np.array([[p.x, p.y] for p in self.point_list], dtype=np.int32)
            cv2.fillPoly(mask, [points], color=(255, 255, 255))
        elif (self.template_shape == TemplateShapeEnum.POLYGON.value.value
              and len(self.point_list) > 2):
            points = np.array([[p.x, p.y] for p in self.point_list], dtype=np.int32)
            cv2.fillPoly(mask, [points], color=(255, 255, 255))
        elif self.template_shape == TemplateShapeEnum.MULTI_RECT.value.value:
            for i in range(0, len(self.point_list), 2):
                if i + 1 >= len(self.point_list):
                    break
                left_top = self.point_list[i]
                right_bottom = self.point_list[i + 1]
                cv2.rectangle(mask, (left_top.x, left_top.y), (right_bottom.x, right_bottom.y), color=(255, 255, 255), thickness=-1)
        else:
            return None

        return cv2_utils.crop_image_only(mask, rect)

    def get_template_mask_to_display(self) -> Optional[MatLike]:
        """
        获取用于开发工具显示的模板掩码
        :return:
        """
        if not self.point_updated and self.mask is not None:
            return self.mask
        else:
            return self.get_template_mask_by_screen_point()

    def get_template_merge_to_display(self) -> Optional[MatLike]:
        """
        获取用于开发工具显示的模板抠图
        :return:
        """
        raw = self.get_template_raw_to_display()
        mask = self.get_template_mask_to_display()
        return cv2.bitwise_and(raw, raw, mask=mask)

    def get_template_reversed_merge_to_display(self) -> Optional[MatLike]:
        """
        获取用于开发工具显示的反向抠图
        :return:
        """
        raw = self.get_template_raw_to_display()
        mask = self.get_template_mask_to_display()
        if mask is not None:
            mask = 255 - mask
        return cv2.bitwise_and(raw, raw, mask=mask)

    def get_screen_image_to_display(self) -> Optional[MatLike]:
        """
        获取用于开发工具显示的图片
        :return:
        """
        if self.screen_image is None:
            return None

        image_to_show = self.screen_image.copy()
        if (self.template_shape == TemplateShapeEnum.RECTANGLE.value.value
                and len(self.point_list) == 2):
            left_top = self.point_list[0]
            right_bottom = self.point_list[1]

            # 将框绘制在区域外侧，避免遮挡内容
            thickness = 2
            half_thickness = thickness // 2
            outer_x1 = left_top.x - half_thickness
            outer_y1 = left_top.y - half_thickness
            outer_x2 = right_bottom.x + half_thickness
            outer_y2 = right_bottom.y + half_thickness

            # 确保调整后的坐标在图像范围内
            img_height, img_width = image_to_show.shape[:2]
            outer_x1 = max(0, outer_x1)
            outer_y1 = max(0, outer_y1)
            outer_x2 = min(img_width - 1, outer_x2)
            outer_y2 = min(img_height - 1, outer_y2)

            if outer_x2 > outer_x1 and outer_y2 > outer_y1:
                cv2.rectangle(image_to_show,
                              (outer_x1, outer_y1),
                              (outer_x2, outer_y2),
                              (255, 0, 0), thickness)
        elif (self.template_shape == TemplateShapeEnum.CIRCLE.value.value
                and len(self.point_list) == 2):
            center = self.point_list[0]
            r = cal_utils.distance_between(center, self.point_list[1])
            cv2.circle(image_to_show, (center.x, center.y), int(r), (255, 0, 0), 2)
        elif (self.template_shape == TemplateShapeEnum.QUADRILATERAL.value.value
                and len(self.point_list) == 4):
            points = np.array([[p.x, p.y] for p in self.point_list], dtype=np.int32)
            cv2.polylines(image_to_show, [points], isClosed=True, color=(255, 0, 0), thickness=2)
        elif (self.template_shape == TemplateShapeEnum.POLYGON.value.value
                and len(self.point_list) > 2):
            points = np.array([[p.x, p.y] for p in self.point_list], dtype=np.int32)
            cv2.polylines(image_to_show, [points], isClosed=True, color=(255, 0, 0), thickness=2)
        elif self.template_shape == TemplateShapeEnum.MULTI_RECT.value.value:
            for i in range(0, len(self.point_list), 2):
                if i + 1 >= len(self.point_list):
                    break
                left_top = self.point_list[i]
                right_bottom = self.point_list[i + 1]

                # 将框绘制在区域外侧，避免遮挡内容
                thickness = 2
                half_thickness = thickness // 2
                outer_x1 = left_top.x - half_thickness
                outer_y1 = left_top.y - half_thickness
                outer_x2 = right_bottom.x + half_thickness
                outer_y2 = right_bottom.y + half_thickness

                # 确保调整后的坐标在图像范围内
                img_height, img_width = image_to_show.shape[:2]
                outer_x1 = max(0, outer_x1)
                outer_y1 = max(0, outer_y1)
                outer_x2 = min(img_width - 1, outer_x2)
                outer_y2 = min(img_height - 1, outer_y2)

                if outer_x2 > outer_x1 and outer_y2 > outer_y1:
                    cv2.rectangle(image_to_show,
                                  (outer_x1, outer_y1),
                                  (outer_x2, outer_y2),
                                  (255, 0, 0), thickness)

        return image_to_show

    def update_template_shape(self, new_value: str) -> None:
        """
        更改模板形状 会尽量做一些转化
        :param new_value:
        :return:
        """
        if new_value == self.template_shape:
            return

        if new_value == TemplateShapeEnum.RECTANGLE.value.value:  # 矩形
            if self.template_shape == TemplateShapeEnum.CIRCLE.value.value:  # 圆形 -> 矩形
                self._update_points_circle_2_rect()
            else:  # 其它 -> 矩形
                self._update_points_polygon_2_rect()
        elif new_value == TemplateShapeEnum.QUADRILATERAL.value.value:  # 四边形
            if self.template_shape == TemplateShapeEnum.CIRCLE.value.value:  # 圆形 -> 四边形
                self._update_points_circle_2_rect()  # 先转矩形
                self._update_points_rect_2_polygon()  # 再转多边形
            elif self.template_shape == TemplateShapeEnum.RECTANGLE.value.value:  # 矩形 -> 四边形
                self._update_points_rect_2_polygon()
        elif new_value == TemplateShapeEnum.CIRCLE.value.value:  # 圆形
            self._update_points_polygon_2_circle()
        elif new_value == TemplateShapeEnum.POLYGON.value.value:  # 多边形
            if self.template_shape == TemplateShapeEnum.CIRCLE.value.value:  # 圆形 -> 多边形
                self._update_points_circle_2_rect()  # 先转矩形
                self._update_points_rect_2_polygon()  # 再转多边形
            elif self.template_shape == TemplateShapeEnum.RECTANGLE.value.value:  # 矩形 -> 多边形
                self._update_points_rect_2_polygon()

        self.template_shape = new_value

    def _update_points_polygon_2_circle(self) -> None:
        """
        多边形转成圆形
        :return:
        """
        if len(self.point_list) >= 2:
            # 圆心
            avg_x = int(sum([p.x for p in self.point_list]) * 1.0 / len(self.point_list))
            avg_y = int(sum([p.y for p in self.point_list]) * 1.0 / len(self.point_list))
            center = Point(avg_x, avg_y)

            # 最远的点
            farthest = None
            for p in self.point_list:
                if (farthest is None or
                        cal_utils.distance_between(farthest, center) < cal_utils.distance_between(p, center)):
                    farthest = p
            self.point_list = [center, farthest]

            self.point_updated = True

    def _update_points_polygon_2_rect(self) -> None:
        """
        多边形转成矩形
        :return:
        """
        if len(self.point_list) >= 2:
            min_x = min([p.x for p in self.point_list])
            min_y = min([p.y for p in self.point_list])
            max_x = max([p.x for p in self.point_list])
            max_y = max([p.y for p in self.point_list])
            self.point_list = [
                Point(min_x, min_y),
                Point(max_x, max_y)
            ]

            self.point_updated = True

    def _update_points_circle_2_rect(self) -> None:
        """
        圆形转成矩形
        :return:
        """
        if len(self.point_list) >= 2:
            r = int(cal_utils.distance_between(self.point_list[0], self.point_list[1]))
            self.point_list = [
                (self.point_list[0] - Point(r, r)),
                (self.point_list[0] + Point(r, r))
            ]
            self.point_updated = True

    def _update_points_rect_2_polygon(self) -> None:
        """
        矩形换成多边形
        :return:
        """
        min_x = min([p.x for p in self.point_list])
        min_y = min([p.y for p in self.point_list])
        max_x = max([p.x for p in self.point_list])
        max_y = max([p.y for p in self.point_list])
        self.point_list = [
            Point(min_x, min_y),
            Point(min_x, max_y),
            Point(max_x, max_y),
            Point(max_x, min_y)
        ]
        self.point_updated = True

    @lru_cache
    def get_template_features(self):
        """
        获取特征
        :return:
        """
        return cv2_utils.feature_detect_and_compute(self.raw, self.mask)

    def copy_new(self) -> None:
        """
        复制变成一个新的
        :return:
        """
        self.template_id = self.template_id + '_copy'

        self.old_sub_dir = self.sub_dir  # 无需删除
        self.old_template_id = self.template_id

        self.file_path = self.get_yml_file_path()

    def update_all_points(self, dx: int, dy: int) -> None:
        """
        所有坐标移动
        """
        for point in self.point_list:
            point.x = point.x + dx
            point.y = point.y + dy
        self.point_updated = True


@lru_cache
def get_template_root_dir_path() -> str:
    """
    模板文件夹的根目录
    :return:
    """
    return os_utils.get_path_under_work_dir('assets', 'template')


@lru_cache
def get_template_sub_dir_path(sub_dir: str) -> str:
    """
    模板文件夹的分类目录
    :return:
    """
    return os.path.join(os_utils.get_path_under_work_dir('assets', 'template'), sub_dir)


def get_template_dir_path(sub_dir: str, template_id: str, make_dir: bool = False) -> str:
    """
    获取具体的模板文件夹位置
    :param sub_dir: 分类文件夹
    :param template_id: 模板ID
    :param make_dir: 创建文件夹
    :return:
    """
    if make_dir:
        return os_utils.get_path_under_work_dir('assets', 'template', sub_dir, template_id)
    else:
        return os.path.join(
            os_utils.get_path_under_work_dir('assets', 'template'),
            sub_dir, template_id
        )


def is_template_existed(sub_dir: str, template_id: str, need_raw: bool = True, need_config: bool = False) -> bool:
    """
    模板是否存在
    :param sub_dir:
    :param template_id:
    :param need_raw: 需要原图
    :param need_config: 需要配置文件
    :return:
    """
    template_dir = get_template_dir_path(sub_dir, template_id)
    if not os.path.exists(template_dir) or not os.path.isdir(template_dir):
        return False
    if need_raw and not os.path.exists(os.path.join(template_dir, TEMPLATE_RAW_FILE_NAME)):
        return False
    if need_config and not os.path.exists(os.path.join(template_dir, TEMPLATE_CONFIG_FILE_NAME)):
        return False
    return True


@lru_cache
def get_template_raw_path(sub_dir: str, template_id: str) -> str:
    """
    模板原图的路径
    :param sub_dir: 模板分类
    :param template_id: 模板id
    :return:
    """
    return os.path.join(get_template_dir_path(sub_dir, template_id), TEMPLATE_RAW_FILE_NAME)


@lru_cache
def get_template_mask_path(sub_dir: str, template_id: str) -> str:
    """
    模板掩码的路径
    :param sub_dir: 模板分类
    :param template_id: 模板id
    :return:
    """
    return os.path.join(get_template_dir_path(sub_dir, template_id), TEMPLATE_MASK_FILE_NAME)


@lru_cache
def get_template_config_path(sub_dir: str, template_id: str) -> str:
    """
    模板配置文件的路径
    :param sub_dir: 模板分类
    :param template_id: 模板id
    :return:
    """
    return os.path.join(get_template_dir_path(sub_dir, template_id), TEMPLATE_CONFIG_FILE_NAME)


def is_template_config_existed(sub_dir: str, template_id: str) -> bool:
    """
    模板是否存在
    :param sub_dir: 模板分类
    :param template_id: 模板id
    :return:
    """
    template_dir = get_template_dir_path(sub_dir, template_id)
    return os.path.exists(os.path.join(template_dir, TEMPLATE_CONFIG_FILE_NAME))


@lru_cache
def get_template_features_path(sub_dir: str, template_id: str) -> str:
    """
    模板特征文件的路径
    :param sub_dir: 模板分类
    :param template_id: 模板id
    :return:
    """
    return os.path.join(get_template_dir_path(sub_dir, template_id), TEMPLATE_FEATURES_FILE_NAME)
