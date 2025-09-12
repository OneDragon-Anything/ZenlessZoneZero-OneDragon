import os
from typing import Optional, Tuple

import cv2
import numpy as np
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox
from qfluentwidgets import (FluentIcon, PushButton, LineEdit, SwitchButton,
                            BodyLabel, ComboBox)

from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils import cv2_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.click_image_label import ClickImageLabel
from one_dragon_qt.widgets.image_viewer_widget import ImageViewerWidget
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class ImageMattingInterface(VerticalScrollInterface):
    """图像扣图界面"""
    
    # 保存上次使用的目录路径
    last_save_directory = ""

    def __init__(self, ctx: OneDragonContext, parent=None):
        self.ctx = ctx
        
        VerticalScrollInterface.__init__(
            self,
            object_name='image_matting_interface',
            content_widget=None, 
            parent=parent,
            nav_text_cn='图像扣图'
        )
        
        # 图像数据
        self.original_image: Optional[np.ndarray] = None
        self.selected_region: Optional[Tuple[int, int, int, int]] = None  # x, y, width, height
        self.mask_image: Optional[np.ndarray] = None
        self.result_image: Optional[np.ndarray] = None
        self.selected_region_image: Optional[np.ndarray] = None  # 选中区域的图像

    def get_content_widget(self) -> QWidget:
        """获取主要内容组件。

        创建并返回包含控制面板和图像显示面板的主要界面组件。

        Returns:
            QWidget: 配置好的主要内容组件
        """
        # 主容器，水平布局
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        main_layout.addWidget(self._init_control_panel())
        main_layout.addWidget(self._init_original_image_display_panel())
        main_layout.addWidget(self._init_processed_image_display_panel(), stretch=1)

        return main_widget

    def _init_control_panel(self) -> QWidget:
        """初始化控制面板。

        创建包含所有控制组件的面板，包括图像加载、颜色过滤、保存等。

        Returns:
            QWidget: 配置好的控制面板组件
        """
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(12)

        # 图像加载
        self.load_btn = PushButton(text='加载图片')
        self.load_btn.clicked.connect(self._load_image)
        
        load_card = MultiPushSettingCard(
            icon=FluentIcon.FOLDER,
            title='图像加载',
            btn_list=[self.load_btn]
        )
        control_layout.addWidget(load_card)

        # 颜色过滤设置 - 颜色空间选择
        self.color_space_combo = ComboBox()
        self.color_space_combo.addItems(["RGB", "HSV"])
        
        color_space_card = MultiPushSettingCard(
            icon=FluentIcon.PALETTE,
            title='颜色空间',
            content='选择颜色过滤的颜色空间',
            btn_list=[self.color_space_combo]
        )
        control_layout.addWidget(color_space_card)

        # 颜色过滤设置 - 下限
        self.color_lower_input = LineEdit()
        self.color_lower_input.setPlaceholderText("0,0,0")
        self.color_lower_input.setText("0,0,0")

        color_lower_card = MultiPushSettingCard(
            icon=FluentIcon.DOWN,
            title='颜色下限',
            content='设置颜色过滤的下限值 (R,G,B 或 H,S,V)',
            btn_list=[self.color_lower_input]
        )
        control_layout.addWidget(color_lower_card)

        # 颜色过滤设置 - 上限
        self.color_upper_input = LineEdit()
        self.color_upper_input.setPlaceholderText("255,255,255")
        self.color_upper_input.setText("255,255,255")

        color_upper_card = MultiPushSettingCard(
            icon=FluentIcon.UP,
            title='颜色上限',
            content='设置颜色过滤的上限值 (R,G,B 或 H,S,V)',
            btn_list=[self.color_upper_input]
        )
        control_layout.addWidget(color_upper_card)

        # 应用颜色过滤按钮
        self.filter_btn = PushButton(text='应用颜色过滤')
        self.filter_btn.clicked.connect(self._apply_color_filter)
        self.filter_btn.setEnabled(False)

        filter_btn_card = MultiPushSettingCard(
            icon=FluentIcon.PLAY,
            title='执行颜色过滤',
            btn_list=[self.filter_btn]
        )
        control_layout.addWidget(filter_btn_card)

        # 处理选项
        self.auto_crop_switch = SwitchButton()
        self.auto_crop_switch.setChecked(True)

        option_card = MultiPushSettingCard(
            icon=FluentIcon.ERASE_TOOL,
            title='处理选项',
            content='自动裁剪到有效区域',
            btn_list=[
                BodyLabel('自动裁剪:'), self.auto_crop_switch
            ]
        )
        control_layout.addWidget(option_card)

        # 保存操作
        self.save_result_btn = PushButton(text='保存扣图结果')
        self.save_result_btn.clicked.connect(self._save_result)
        self.save_result_btn.setEnabled(False)

        self.save_mask_btn = PushButton(text='保存掩码图')
        self.save_mask_btn.clicked.connect(self._save_mask)
        self.save_mask_btn.setEnabled(False)

        self.clear_btn = PushButton(text='清空图像')
        self.clear_btn.clicked.connect(self._clear_images)

        save_card = MultiPushSettingCard(
            icon=FluentIcon.SAVE,
            title='保存操作',
            btn_list=[self.save_result_btn, self.save_mask_btn, self.clear_btn]
        )
        control_layout.addWidget(save_card)

        control_layout.addStretch(1)
        return control_widget

    def _init_original_image_display_panel(self) -> QWidget:
        """初始化原始图像显示面板。

        创建用于显示原始图像和选中区域的面板。

        Returns:
            QWidget: 配置好的原始图像显示面板
        """
        display_widget = QWidget()
        display_layout = QVBoxLayout(display_widget)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(12)

        # 原始图像显示器
        self.original_image_viewer = ImageViewerWidget()
        self.original_image_viewer.set_interaction_mode("select")
        self.original_image_viewer.area_selected.connect(self._on_area_selected)
        display_layout.addWidget(self.original_image_viewer)

        return display_widget

    def _init_processed_image_display_panel(self) -> QWidget:
        """初始化处理后图像显示面板。

        创建用于显示处理后图像的面板。

        Returns:
            QWidget: 配置好的处理后图像显示面板
        """
        display_widget = QWidget()
        display_layout = QVBoxLayout(display_widget)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(12)

        # 处理后图像显示器
        self.processed_image_viewer = ClickImageLabel()
        display_layout.addWidget(self.processed_image_viewer)

        return display_widget

    def _load_image(self):
        """加载图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            gt("选择图片文件"),
            "",
            "Image files (*.png *.jpg *.jpeg *.bmp *.tiff)"
        )
        
        if file_path:
            try:
                # 使用cv2_utils加载图片
                image = cv2_utils.read_image(file_path)
                if image is None:
                    raise ValueError("无法读取图像文件")

                # 确保是RGB格式
                self.original_image = self._ensure_rgb_format(image)
                
                # 显示图片
                self.original_image_viewer.set_image(self.original_image)
                
                # 重置处理状态
                self._reset_processing_state()
                self._update_button_states()
                
            except Exception as e:
                QMessageBox.warning(self, '错误', f'加载图片失败: {str(e)}')

    def _ensure_rgb_format(self, image: np.ndarray) -> np.ndarray:
        """确保图像是RGB格式。

        将输入图像转换为RGB格式，支持灰度图和其他格式的自动转换。

        Args:
            image: 输入图像数组

        Returns:
            np.ndarray: RGB格式的图像数组，如果输入为None则返回None
        """
        if image is None:
            return None

        if image.ndim == 2:
            # 灰度图转RGB
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.ndim == 3:
            # 已经是3通道，直接返回
            return image
        else:
            # 其他格式，尝试转换
            return image

    def _on_area_selected(self, x: int, y: int, width: int, height: int):
        """区域选择回调"""
        self.selected_region = (x, y, width, height)
        self._update_button_states()
        self._reset_processing_state()
        
        # 裁剪并显示选中区域
        if self.original_image is not None:
            selected_area = self.original_image[y:y+height, x:x+width].copy()
            self.selected_region_image = selected_area
            self.processed_image_viewer.set_image(selected_area)

    def _apply_color_filter(self):
        """应用颜色过滤"""
        if self.original_image is None or self.selected_region is None:
            QMessageBox.warning(self, '错误', '请先加载图片并选择区域')
            return
        
        try:
            # 解析颜色值
            lower_color = self._parse_rgb_input(self.color_lower_input.text())
            upper_color = self._parse_rgb_input(self.color_upper_input.text())
            
            if lower_color is None or upper_color is None:
                QMessageBox.warning(self, '错误', '颜色值格式错误，请使用 "R,G,B" 或 "H,S,V" 格式')
                return
            
            # 获取选择的颜色空间
            color_space = self.color_space_combo.currentText()
            
            # 使用选中区域图像进行处理
            selected_area = self.selected_region_image.copy() if self.selected_region_image is not None else None
            
            if selected_area is None:
                # 提取选择区域
                x, y, width, height = self.selected_region
                selected_area = self.original_image[y:y+height, x:x+width].copy()
                self.selected_region_image = selected_area
            
            # 转换颜色空间
            if color_space == "HSV":
                processed_image = cv2.cvtColor(selected_area, cv2.COLOR_RGB2HSV)
            else:
                processed_image = selected_area
            
            # 应用颜色过滤
            self.mask_image = cv2.inRange(processed_image, np.array(lower_color), np.array(upper_color))
            
            # 应用掩码到原图区域
            self.result_image = cv2.bitwise_and(selected_area, selected_area, mask=self.mask_image)
            
            # 如果启用自动裁剪
            if self.auto_crop_switch.isChecked():
                self._auto_crop_to_valid_area()
            
            # 显示结果
            self._display_result()
            self._update_button_states()
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'颜色过滤失败: {str(e)}')

    def _parse_rgb_input(self, text: str) -> Optional[Tuple[int, int, int]]:
        """解析RGB输入"""
        try:
            parts = text.strip().split(',')
            if len(parts) != 3:
                return None
            
            rgb = tuple(int(part.strip()) for part in parts)
            
            # 验证范围
            for val in rgb:
                if not (0 <= val <= 255):
                    return None
            
            return rgb
        except:
            return None

    def _auto_crop_to_valid_area(self):
        """自动裁剪到有效区域"""
        if self.mask_image is None:
            return
        
        # 找到掩码中的有效区域
        coords = np.column_stack(np.where(self.mask_image > 0))
        if len(coords) == 0:
            return
        
        # 计算边界框
        y_min, x_min = coords.min(axis=0)
        y_max, x_max = coords.max(axis=0)
        
        # 裁剪结果图和掩码图
        self.result_image = self.result_image[y_min:y_max+1, x_min:x_max+1]
        self.mask_image = self.mask_image[y_min:y_max+1, x_min:x_max+1]

    def _display_result(self):
        """显示处理结果"""
        if self.result_image is not None:
            # 在处理后图像查看器中显示结果
            self.processed_image_viewer.set_image(self.result_image)

    def _save_result(self):
        """保存扣图结果"""
        if self.result_image is None:
            return
        
        # 使用上次保存的目录作为默认目录
        default_dir = ImageMattingInterface.last_save_directory if ImageMattingInterface.last_save_directory else ""
        default_path = os.path.join(default_dir, "matting_result.png") if default_dir else "matting_result.png"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            '保存扣图结果',
            default_path,
            "PNG files (*.png);;JPEG files (*.jpg);;All files (*.*)"
        )
        
        if file_path:
            try:
                # 记录保存目录
                ImageMattingInterface.last_save_directory = os.path.dirname(file_path)
                
                # 转换为BGR格式保存
                result_bgr = cv2.cvtColor(self.result_image, cv2.COLOR_RGB2BGR)
                cv2.imwrite(file_path, result_bgr)
                QMessageBox.information(self, '成功', '扣图结果已保存')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    def _save_mask(self):
        """保存掩码图"""
        if self.mask_image is None:
            return
        
        # 使用上次保存的目录作为默认目录
        default_dir = ImageMattingInterface.last_save_directory if ImageMattingInterface.last_save_directory else ""
        default_path = os.path.join(default_dir, "mask.png") if default_dir else "mask.png"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            '保存掩码图',
            default_path,
            "PNG files (*.png);;All files (*.*)"
        )
        
        if file_path:
            try:
                # 记录保存目录
                ImageMattingInterface.last_save_directory = os.path.dirname(file_path)
                
                cv2.imwrite(file_path, self.mask_image)
                QMessageBox.information(self, '成功', '掩码图已保存')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'保存失败: {str(e)}')

    def _clear_images(self):
        """清空所有图像"""
        self.original_image = None
        self.selected_region = None
        self.mask_image = None
        self.result_image = None
        self.selected_region_image = None
        
        # 清空图像显示
        empty_image = np.zeros((200, 200, 3), dtype=np.uint8)
        empty_image.fill(240)  # 浅灰色背景
        self.original_image_viewer.set_image(empty_image)
        self.processed_image_viewer.set_image(empty_image)
        
        self._update_button_states()

    def _reset_processing_state(self):
        """重置处理状态"""
        self.mask_image = None
        self.result_image = None
        self.selected_region_image = None

    def _update_button_states(self):
        """更新按钮状态"""
        has_image = self.original_image is not None
        has_region = self.selected_region is not None
        has_result = self.result_image is not None
        has_mask = self.mask_image is not None
        
        self.filter_btn.setEnabled(has_image and has_region)
        self.save_result_btn.setEnabled(has_result)
        self.save_mask_btn.setEnabled(has_mask)